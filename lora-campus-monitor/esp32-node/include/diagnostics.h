// Serial diagnostics (115200 baud).
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "sensor_manager.h"

namespace diagnostics {

void begin();
void printBanner();
void printInitResult(const char* component, bool ok);
void printReading(uint32_t sequence, const SensorSnapshot& snapshot);
void printTxResult(uint32_t sequence, bool ok, uint32_t airtime_ms, const uint8_t* packet, size_t length);
void printSkippedSlots(uint32_t skipped);

}  // namespace diagnostics
