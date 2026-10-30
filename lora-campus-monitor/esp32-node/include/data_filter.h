// Pure (hardware-independent) filtering and validation helpers.
// Compiled both on the ESP32 and on the host for unit tests.
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace filter {

// Physical ranges supported by the sensors (datasheet operating limits).
constexpr float TEMP_MIN_C = -40.0f;
constexpr float TEMP_MAX_C = 85.0f;
constexpr float HUMIDITY_MIN = 0.0f;
constexpr float HUMIDITY_MAX = 100.0f;
constexpr float PRESSURE_MIN_HPA = 300.0f;
constexpr float PRESSURE_MAX_HPA = 1100.0f;
constexpr float LUX_MIN = 0.0f;
constexpr float LUX_MAX = 120000.0f;

constexpr uint16_t ADC_MAX = 4095;
constexpr uint16_t ADC_SATURATION_LEVEL = 4080;

bool inRange(float value, float minimum, float maximum);

// Sorts samples in place and returns the mean of the middle 50 %.
// Rejects spikes from ADC noise. Returns 0 for n == 0.
uint16_t trimmedMean(uint16_t* samples, size_t n);

struct SoundStats {
    uint16_t average_deviation;  // mean |x - mean|, proportional to loudness
    uint16_t peak_to_peak;       // max - min inside the window
    uint16_t maximum;
};

SoundStats computeSoundStats(const uint16_t* samples, size_t n);

}  // namespace filter
