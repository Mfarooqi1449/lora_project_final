#include "diagnostics.h"

#include <Arduino.h>
#include <math.h>

#include "board_config.h"
#include "node_identity.h"
#include "packet_builder.h"

namespace diagnostics {
namespace {

void printFloat(const char* label, float value, const char* unit, int decimals) {
    Serial.print(label);
    if (isnan(value)) {
        Serial.print("--");
    } else {
        Serial.print(value, decimals);
    }
    Serial.print(unit);
}

void printU16(const char* label, uint16_t value) {
    Serial.print(label);
    if (value == packet::INVALID_U16) {
        Serial.print("--");
    } else {
        Serial.print(value);
    }
}

}  // namespace

void begin() {
    Serial.begin(115200);
    uint32_t start = millis();
    while (!Serial && millis() - start < 2000) {
        delay(10);
    }
}

void printBanner() {
    Serial.println();
    Serial.println(F("=== LoRa Campus Monitor - ESP32 field node ==="));
    Serial.printf("Firmware : %s\n", identity::FIRMWARE_VERSION);
    Serial.printf("Node ID  : %u\n", identity::NODE);
    Serial.printf("Slot     : %lu ms offset, period %lu ms, jitter <= %lu ms\n",
                  static_cast<unsigned long>(identity::SLOT_OFFSET_MS),
                  static_cast<unsigned long>(timing::TX_PERIOD_MS),
                  static_cast<unsigned long>(timing::MAX_JITTER_MS));
    Serial.printf("Radio    : %ld Hz, BW %ld, SF%d, CR 4/%d, preamble %ld, sync 0x%02X, %d dBm, CRC on\n",
                  radio::FREQUENCY_HZ, radio::BANDWIDTH_HZ, radio::SPREADING_FACTOR,
                  radio::CODING_RATE_DENOM, radio::PREAMBLE_LENGTH, radio::SYNC_WORD,
                  radio::TX_POWER_DBM);
}

void printInitResult(const char* component, bool ok) {
    Serial.printf("[init] %-8s %s\n", component, ok ? "OK" : "FAILED");
}

void printReading(uint32_t sequence, const SensorSnapshot& s) {
    Serial.printf("[seq %lu] ", static_cast<unsigned long>(sequence));
    printFloat("T=", s.temperature_c, "C ", 2);
    printFloat("RH=", s.humidity_percent, "% ", 1);
    printFloat("P=", s.pressure_hpa, "hPa ", 1);
    printFloat("L=", s.light_lux, "lx ", 1);
    printU16("MQ135=", s.air_quality_raw);
    printU16(" SndAvg=", s.sound_avg);
    printU16(" SndPk=", s.sound_peak);
    if (s.supply_mv != packet::INVALID_U16) {
        Serial.printf(" Vs=%.2fV", s.supply_mv / 1000.0f);
    }
    Serial.printf(" flags=0x%04X\n", s.flags);

    if (s.flags & packet::FLAG_BME280_ERROR) Serial.println(F("  ! BME280 not responding"));
    if (s.flags & packet::FLAG_BME280_OUT_OF_RANGE) Serial.println(F("  ! BME280 value out of range"));
    if (s.flags & packet::FLAG_BH1750_ERROR) Serial.println(F("  ! BH1750 not responding"));
    if (s.flags & packet::FLAG_BH1750_OUT_OF_RANGE) Serial.println(F("  ! BH1750 value out of range"));
    if (s.flags & packet::FLAG_MQ135_WARMUP) Serial.println(F("  - MQ-135 warming up"));
    if (s.flags & packet::FLAG_MQ135_SATURATED) Serial.println(F("  ! MQ-135 ADC saturated"));
    if (s.flags & packet::FLAG_SOUND_SATURATED) Serial.println(F("  ! Sound ADC saturated"));
    if (s.flags & packet::FLAG_SUPPLY_LOW) Serial.println(F("  ! Supply voltage low"));
}

void printTxResult(uint32_t sequence, bool ok, uint32_t airtime_ms, const uint8_t* packet, size_t length) {
    Serial.printf("[tx  %lu] %s, %u bytes, %lu ms airtime | ",
                  static_cast<unsigned long>(sequence), ok ? "SENT" : "FAILED",
                  static_cast<unsigned>(length), static_cast<unsigned long>(airtime_ms));
    for (size_t i = 0; i < length; ++i) Serial.printf("%02X", packet[i]);
    Serial.println();
}

void printSkippedSlots(uint32_t skipped) {
    if (skipped > 0) {
        Serial.printf("[sched] skipped %lu slot(s)\n", static_cast<unsigned long>(skipped));
    }
}

}  // namespace diagnostics
