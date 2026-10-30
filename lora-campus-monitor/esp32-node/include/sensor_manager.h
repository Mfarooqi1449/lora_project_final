// Reads BME280, BH1750 (I2C), MQ-135 and sound sensor (ADC) and the
// optional 5 V supply monitor. Missing sensors are re-detected periodically.
#pragma once

#include <Adafruit_BME280.h>
#include <BH1750.h>
#include <stdint.h>

#include "board_config.h"

struct SensorSnapshot {
    float temperature_c;
    float humidity_percent;
    float pressure_hpa;
    float light_lux;
    uint16_t air_quality_raw;
    uint16_t sound_avg;
    uint16_t sound_peak;
    uint16_t supply_mv;
    uint16_t flags;  // packet::StatusFlag bits
};

class SensorManager {
public:
    SensorManager();

    void begin();
    SensorSnapshot read(uint32_t uptime_seconds);

    bool bme280Present() const { return bme_ok_; }
    bool bh1750Present() const { return bh_ok_; }

private:
    static constexpr size_t SOUND_BUFFER_SIZE =
        timing::SOUND_WINDOW_MS * 1000UL / timing::SOUND_SAMPLE_US;

    bool i2cDevicePresent(uint8_t address);
    void initBme280();
    void initBh1750();
    void retryMissingSensors();
    void readBme280(SensorSnapshot& s);
    void readBh1750(SensorSnapshot& s);
    void readMq135(SensorSnapshot& s, uint32_t uptime_seconds);
    void readSound(SensorSnapshot& s);
    void readSupply(SensorSnapshot& s);

    Adafruit_BME280 bme_;
    BH1750 bh_;
    bool bme_ok_ = false;
    bool bh_ok_ = false;
    uint32_t last_retry_ms_ = 0;
    uint16_t sound_buffer_[SOUND_BUFFER_SIZE];
};
