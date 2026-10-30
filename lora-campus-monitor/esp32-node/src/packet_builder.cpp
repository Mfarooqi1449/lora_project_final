#include "packet_builder.h"

#include <math.h>

namespace packet {
namespace {

void putU16(uint8_t* p, uint16_t v) {
    p[0] = static_cast<uint8_t>(v & 0xFF);
    p[1] = static_cast<uint8_t>(v >> 8);
}

void putU32(uint8_t* p, uint32_t v) {
    for (int i = 0; i < 4; ++i) {
        p[i] = static_cast<uint8_t>((v >> (8 * i)) & 0xFF);
    }
}

int16_t scaleI16(float value, float scale) {
    if (isnan(value)) return INVALID_I16;
    float scaled = roundf(value * scale);
    if (scaled < -32767.0f || scaled > 32767.0f) return INVALID_I16;
    return static_cast<int16_t>(scaled);
}

uint16_t scaleU16(float value, float scale) {
    if (isnan(value) || value < 0.0f) return INVALID_U16;
    float scaled = roundf(value * scale);
    if (scaled >= 65535.0f) return INVALID_U16;
    return static_cast<uint16_t>(scaled);
}

uint32_t scaleU32(float value, float scale) {
    if (isnan(value) || value < 0.0f) return INVALID_U32;
    double scaled = round(static_cast<double>(value) * scale);
    if (scaled >= 4294967295.0) return INVALID_U32;
    return static_cast<uint32_t>(scaled);
}

}  // namespace

uint16_t crc16Ccitt(const uint8_t* data, size_t length) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < length; ++i) {
        crc ^= static_cast<uint16_t>(data[i]) << 8;
        for (int bit = 0; bit < 8; ++bit) {
            crc = (crc & 0x8000) ? static_cast<uint16_t>((crc << 1) ^ 0x1021)
                                 : static_cast<uint16_t>(crc << 1);
        }
    }
    return crc;
}

size_t encode(const Fields& f, uint8_t* out, size_t capacity) {
    if (out == nullptr || capacity < PACKET_SIZE) return 0;

    out[0] = MAGIC;
    out[1] = PROTOCOL_VERSION;
    out[2] = f.node_id;
    putU32(out + 3, f.sequence_number);
    putU32(out + 7, f.uptime_seconds);
    putU16(out + 11, static_cast<uint16_t>(scaleI16(f.temperature_c, 100.0f)));
    putU16(out + 13, scaleU16(f.humidity_percent, 100.0f));
    putU16(out + 15, scaleU16(f.pressure_hpa, 10.0f));
    putU32(out + 17, scaleU32(f.light_lux, 100.0f));
    putU16(out + 21, f.air_quality_raw);
    putU16(out + 23, f.sound_avg);
    putU16(out + 25, f.sound_peak);
    putU16(out + 27, f.supply_mv);
    putU16(out + 29, f.status_flags);
    putU16(out + 31, crc16Ccitt(out, PACKET_SIZE - 2));
    return PACKET_SIZE;
}

}  // namespace packet
