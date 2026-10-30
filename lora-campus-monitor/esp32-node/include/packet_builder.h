// Binary LoRa packet format, protocol version 1 (33 bytes, little-endian).
// Must match raspberry-pi/app/protocol.py and docs/packet_protocol.md.
//
//  off size field
//   0   1   magic            0x4C ('L')
//   1   1   protocol_version 1
//   2   1   node_id
//   3   4   sequence_number
//   7   4   uptime_seconds
//  11   2   temperature      int16, degC x100      (INT16_MIN = invalid)
//  13   2   humidity         uint16, %RH x100      (0xFFFF = invalid)
//  15   2   pressure         uint16, hPa x10       (0xFFFF = invalid)
//  17   4   light            uint32, lux x100      (0xFFFFFFFF = invalid)
//  21   2   air_quality_raw  uint16, ADC 0..4095   (0xFFFF = invalid)
//  23   2   sound_avg        uint16, mean deviation(0xFFFF = invalid)
//  25   2   sound_peak       uint16, peak-to-peak  (0xFFFF = invalid)
//  27   2   supply_mv        uint16, millivolts    (0xFFFF = not monitored)
//  29   2   status_flags     uint16, see StatusFlag
//  31   2   crc16            CRC-16/CCITT-FALSE over bytes 0..30
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace packet {

constexpr uint8_t MAGIC = 0x4C;
constexpr uint8_t PROTOCOL_VERSION = 1;
constexpr size_t PACKET_SIZE = 33;

constexpr int16_t INVALID_I16 = INT16_MIN;
constexpr uint16_t INVALID_U16 = 0xFFFF;
constexpr uint32_t INVALID_U32 = 0xFFFFFFFFUL;

enum StatusFlag : uint16_t {
    FLAG_BME280_ERROR = 1u << 0,
    FLAG_BH1750_ERROR = 1u << 1,
    FLAG_MQ135_WARMUP = 1u << 2,
    FLAG_MQ135_SATURATED = 1u << 3,
    FLAG_SOUND_SATURATED = 1u << 4,
    FLAG_SUPPLY_LOW = 1u << 5,
    FLAG_SUPPLY_NOT_MONITORED = 1u << 6,
    FLAG_BME280_OUT_OF_RANGE = 1u << 7,
    FLAG_BH1750_OUT_OF_RANGE = 1u << 8,
    FLAG_LAST_TX_FAILED = 1u << 9,
    FLAG_BOOT = 1u << 10,
};

// Values in engineering units. Use NAN (floats) or the INVALID_* constants
// (integers) for missing readings; encode() maps them to the wire sentinels.
struct Fields {
    uint8_t node_id;
    uint32_t sequence_number;
    uint32_t uptime_seconds;
    float temperature_c;
    float humidity_percent;
    float pressure_hpa;
    float light_lux;
    uint16_t air_quality_raw;
    uint16_t sound_avg;
    uint16_t sound_peak;
    uint16_t supply_mv;
    uint16_t status_flags;
};

uint16_t crc16Ccitt(const uint8_t* data, size_t length);

// Writes PACKET_SIZE bytes into out. Returns bytes written, or 0 if
// capacity is too small.
size_t encode(const Fields& fields, uint8_t* out, size_t capacity);

}  // namespace packet
