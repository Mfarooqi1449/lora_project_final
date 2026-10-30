// Node identity. NODE_ID is supplied by the PlatformIO environment
// (env:node1 -> 1, env:node2 -> 2). Never flash two nodes with the same ID.
#pragma once

#include <stdint.h>

#ifndef NODE_ID
#error "NODE_ID is not defined. Build with 'pio run -e node1' or 'pio run -e node2'."
#endif

static_assert(NODE_ID >= 1 && NODE_ID <= 254, "NODE_ID must be between 1 and 254");

namespace identity {

constexpr uint8_t NODE = NODE_ID;
constexpr const char* FIRMWARE_VERSION = "1.0.0";

// Transmission slot inside the 60 s period: Node 1 -> 10 s, Node 2 -> 40 s.
constexpr uint32_t SLOT_OFFSET_MS = (10000UL + (NODE_ID - 1) * 30000UL) % 60000UL;

}  // namespace identity
