#include "sensor_manager.h"

#include <Arduino.h>
#include <Wire.h>
#include <math.h>

#include "data_filter.h"
#include "packet_builder.h"

SensorManager::SensorManager() : bh_(board::BH1750_I2C_ADDR) {}

void SensorManager::begin() {
    Wire.begin(board::PIN_I2C_SDA, board::PIN_I2C_SCL, board::I2C_FREQUENCY_HZ);

    analogReadResolution(12);
    analogSetPinAttenuation(board::PIN_MQ135, ADC_11db);
    analogSetPinAttenuation(board::PIN_SOUND, ADC_11db);
    if (board::SUPPLY_MONITOR_ENABLED) {
        analogSetPinAttenuation(board::PIN_SUPPLY, ADC_11db);
    }

    initBme280();
    initBh1750();
    last_retry_ms_ = millis();
}

bool SensorManager::i2cDevicePresent(uint8_t address) {
    Wire.beginTransmission(address);
    return Wire.endTransmission() == 0;
}

void SensorManager::initBme280() {
    bme_ok_ = bme_.begin(board::BME280_I2C_ADDR, &Wire);
    if (bme_ok_) {
        // Forced mode: one measurement per cycle, minimal self-heating.
        bme_.setSampling(Adafruit_BME280::MODE_FORCED,
                         Adafruit_BME280::SAMPLING_X1,
                         Adafruit_BME280::SAMPLING_X1,
                         Adafruit_BME280::SAMPLING_X1,
                         Adafruit_BME280::FILTER_OFF);
    }
}

void SensorManager::initBh1750() {
    bh_ok_ = bh_.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, board::BH1750_I2C_ADDR, &Wire);
}

void SensorManager::retryMissingSensors() {
    if (bme_ok_ && bh_ok_) return;
    uint32_t now = millis();
    if (now - last_retry_ms_ < timing::SENSOR_RETRY_MS) return;
    last_retry_ms_ = now;
    if (!bme_ok_) initBme280();
    if (!bh_ok_) initBh1750();
}

SensorSnapshot SensorManager::read(uint32_t uptime_seconds) {
    retryMissingSensors();

    SensorSnapshot s;
    s.temperature_c = NAN;
    s.humidity_percent = NAN;
    s.pressure_hpa = NAN;
    s.light_lux = NAN;
    s.air_quality_raw = packet::INVALID_U16;
    s.sound_avg = packet::INVALID_U16;
    s.sound_peak = packet::INVALID_U16;
    s.supply_mv = packet::INVALID_U16;
    s.flags = 0;

    readBme280(s);
    readBh1750(s);
    readMq135(s, uptime_seconds);
    readSound(s);
    readSupply(s);
    return s;
}

void SensorManager::readBme280(SensorSnapshot& s) {
    if (!bme_ok_ || !i2cDevicePresent(board::BME280_I2C_ADDR)) {
        bme_ok_ = false;
        s.flags |= packet::FLAG_BME280_ERROR;
        return;
    }
    if (!bme_.takeForcedMeasurement()) {
        s.flags |= packet::FLAG_BME280_ERROR;
        return;
    }

    float t = bme_.readTemperature();
    float h = bme_.readHumidity();
    float p = bme_.readPressure() / 100.0f;

    bool ok = filter::inRange(t, filter::TEMP_MIN_C, filter::TEMP_MAX_C) &&
              filter::inRange(h, filter::HUMIDITY_MIN, filter::HUMIDITY_MAX) &&
              filter::inRange(p, filter::PRESSURE_MIN_HPA, filter::PRESSURE_MAX_HPA);
    if (!ok) {
        s.flags |= packet::FLAG_BME280_OUT_OF_RANGE;
        return;
    }
    s.temperature_c = t;
    s.humidity_percent = h;
    s.pressure_hpa = p;
}

void SensorManager::readBh1750(SensorSnapshot& s) {
    if (!bh_ok_ || !i2cDevicePresent(board::BH1750_I2C_ADDR)) {
        bh_ok_ = false;
        s.flags |= packet::FLAG_BH1750_ERROR;
        return;
    }
    float lux = bh_.readLightLevel();  // -1 = not configured, -2 = I2C error
    if (lux < 0.0f) {
        s.flags |= packet::FLAG_BH1750_ERROR;
        return;
    }
    if (!filter::inRange(lux, filter::LUX_MIN, filter::LUX_MAX)) {
        s.flags |= packet::FLAG_BH1750_OUT_OF_RANGE;
        return;
    }
    s.light_lux = lux;
}

void SensorManager::readMq135(SensorSnapshot& s, uint32_t uptime_seconds) {
    uint16_t samples[timing::ADC_SAMPLES];
    for (uint8_t i = 0; i < timing::ADC_SAMPLES; ++i) {
        samples[i] = static_cast<uint16_t>(analogRead(board::PIN_MQ135));
        delayMicroseconds(200);
    }
    s.air_quality_raw = filter::trimmedMean(samples, timing::ADC_SAMPLES);

    if (uptime_seconds < timing::MQ135_WARMUP_S) s.flags |= packet::FLAG_MQ135_WARMUP;
    if (s.air_quality_raw >= filter::ADC_SATURATION_LEVEL) s.flags |= packet::FLAG_MQ135_SATURATED;
}

void SensorManager::readSound(SensorSnapshot& s) {
    size_t count = 0;
    uint32_t start_us = micros();
    uint32_t next_us = start_us;
    while (count < SOUND_BUFFER_SIZE &&
           micros() - start_us < timing::SOUND_WINDOW_MS * 1000UL) {
        while (static_cast<int32_t>(micros() - next_us) < 0) {
        }
        sound_buffer_[count++] = static_cast<uint16_t>(analogRead(board::PIN_SOUND));
        next_us += timing::SOUND_SAMPLE_US;
    }

    filter::SoundStats stats = filter::computeSoundStats(sound_buffer_, count);
    s.sound_avg = stats.average_deviation;
    s.sound_peak = stats.peak_to_peak;
    if (stats.maximum >= filter::ADC_SATURATION_LEVEL) s.flags |= packet::FLAG_SOUND_SATURATED;
}

void SensorManager::readSupply(SensorSnapshot& s) {
    if (!board::SUPPLY_MONITOR_ENABLED) {
        s.flags |= packet::FLAG_SUPPLY_NOT_MONITORED;
        return;
    }
    uint16_t samples[timing::ADC_SAMPLES];
    for (uint8_t i = 0; i < timing::ADC_SAMPLES; ++i) {
        samples[i] = static_cast<uint16_t>(analogReadMilliVolts(board::PIN_SUPPLY));
        delayMicroseconds(200);
    }
    float supply = filter::trimmedMean(samples, timing::ADC_SAMPLES) * board::SUPPLY_DIVIDER_RATIO;
    s.supply_mv = static_cast<uint16_t>(lroundf(supply));
    if (s.supply_mv < board::SUPPLY_LOW_THRESHOLD_MV) s.flags |= packet::FLAG_SUPPLY_LOW;
}
