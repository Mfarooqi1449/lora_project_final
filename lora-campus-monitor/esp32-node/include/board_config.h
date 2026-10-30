// Hardware pin map, radio settings and timing for the ESP32 field node.
// Pin map matches "FILE 2: HARDWARE DESIGN AND CONNECTIONS" (A8).
#pragma once

#include <stdint.h>

namespace board {

// SX1278 / Ra-02 (VSPI). Ra-02 VCC must be 3.3 V only.
constexpr uint8_t PIN_LORA_SCK = 18;
constexpr uint8_t PIN_LORA_MISO = 19;
constexpr uint8_t PIN_LORA_MOSI = 23;
constexpr uint8_t PIN_LORA_NSS = 5;
constexpr uint8_t PIN_LORA_RESET = 14;
constexpr uint8_t PIN_LORA_DIO0 = 26;

// Shared I2C bus: BME280 (0x76) + BH1750 (0x23).
constexpr uint8_t PIN_I2C_SDA = 21;
constexpr uint8_t PIN_I2C_SCL = 22;
constexpr uint32_t I2C_FREQUENCY_HZ = 100000;
constexpr uint8_t BME280_I2C_ADDR = 0x76;  // SDO -> GND. Use 0x77 if SDO -> 3.3 V.
constexpr uint8_t BH1750_I2C_ADDR = 0x23;  // ADDR -> GND.

// Protected analog inputs (ADC1 only, so they keep working with Wi-Fi/radio).
constexpr uint8_t PIN_MQ135 = 34;   // through 10k/20k divider
constexpr uint8_t PIN_SOUND = 35;   // 3.3 V module or divider
constexpr uint8_t PIN_SUPPLY = 32;  // 100k/100k divider from 5 V rail

constexpr bool SUPPLY_MONITOR_ENABLED = true;
constexpr float SUPPLY_DIVIDER_RATIO = 2.0f;        // (100k + 100k) / 100k
constexpr uint16_t SUPPLY_LOW_THRESHOLD_MV = 4600;  // sets SUPPLY_LOW flag

}  // namespace board

namespace radio {

// All three LoRa modules (Node 1, Node 2, Raspberry Pi) must use identical
// settings. 433 MHz band: check local regulations (India: 433-434.79 MHz,
// low power). Ra-02 uses the PA_BOOST output.
constexpr long FREQUENCY_HZ = 433000000L;
constexpr long BANDWIDTH_HZ = 125000L;
constexpr int SPREADING_FACTOR = 7;    // SF7 for bench tests; raise for range
constexpr int CODING_RATE_DENOM = 5;   // 4/5
constexpr long PREAMBLE_LENGTH = 8;
constexpr int SYNC_WORD = 0x12;        // private network sync word
constexpr int TX_POWER_DBM = 10;       // conservative (10 mW)

}  // namespace radio

namespace timing {

constexpr uint32_t TX_PERIOD_MS = 60000;      // one packet per minute
constexpr uint32_t MAX_JITTER_MS = 2000;      // random delay to avoid repeat collisions
constexpr uint32_t MQ135_WARMUP_S = 180;      // readings flagged during warm-up
constexpr uint32_t SOUND_WINDOW_MS = 1000;    // sound sampling window
constexpr uint32_t SOUND_SAMPLE_US = 500;     // 2 kHz sampling inside the window
constexpr uint8_t ADC_SAMPLES = 32;           // samples per MQ-135/supply reading
constexpr uint32_t WATCHDOG_TIMEOUT_S = 30;
constexpr uint32_t SENSOR_RETRY_MS = 30000;   // re-detect missing sensors

}  // namespace timing
