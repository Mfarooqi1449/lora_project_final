#include "data_filter.h"

#include <math.h>

namespace filter {

bool inRange(float value, float minimum, float maximum) {
    return !isnan(value) && value >= minimum && value <= maximum;
}

uint16_t trimmedMean(uint16_t* samples, size_t n) {
    if (samples == nullptr || n == 0) return 0;

    // Insertion sort: n is small (<= 64).
    for (size_t i = 1; i < n; ++i) {
        uint16_t key = samples[i];
        size_t j = i;
        while (j > 0 && samples[j - 1] > key) {
            samples[j] = samples[j - 1];
            --j;
        }
        samples[j] = key;
    }

    size_t start = n / 4;
    size_t end = n - n / 4;
    uint32_t sum = 0;
    for (size_t i = start; i < end; ++i) sum += samples[i];
    return static_cast<uint16_t>((sum + (end - start) / 2) / (end - start));
}

SoundStats computeSoundStats(const uint16_t* samples, size_t n) {
    SoundStats stats{0, 0, 0};
    if (samples == nullptr || n == 0) return stats;

    uint32_t sum = 0;
    uint16_t minimum = 0xFFFF;
    uint16_t maximum = 0;
    for (size_t i = 0; i < n; ++i) {
        sum += samples[i];
        if (samples[i] < minimum) minimum = samples[i];
        if (samples[i] > maximum) maximum = samples[i];
    }
    float mean = static_cast<float>(sum) / static_cast<float>(n);

    float deviation = 0.0f;
    for (size_t i = 0; i < n; ++i) {
        deviation += fabsf(static_cast<float>(samples[i]) - mean);
    }

    stats.average_deviation = static_cast<uint16_t>(lroundf(deviation / static_cast<float>(n)));
    stats.peak_to_peak = static_cast<uint16_t>(maximum - minimum);
    stats.maximum = maximum;
    return stats;
}

}  // namespace filter
