// Fixed-period transmission scheduler with per-cycle random jitter.
// Slots are computed from the boot time, so jitter never accumulates as drift.
// Hardware-independent: the caller supplies millis() and a random value.
#pragma once

#include <stdint.h>

class Scheduler {
public:
    Scheduler(uint32_t period_ms, uint32_t slot_offset_ms, uint32_t max_jitter_ms);

    // Call once at boot. random_value is any 32-bit random number.
    void start(uint32_t now_ms, uint32_t random_value);

    // True when the current slot is due (handles millis() wrap-around).
    bool isDue(uint32_t now_ms) const;

    // Move to the next slot. If transmissions were missed (e.g. long blocking
    // operation), skips to the next future slot. Returns slots skipped.
    uint32_t advance(uint32_t now_ms, uint32_t random_value);

    uint32_t nextDueMs() const { return next_due_ms_; }
    uint32_t msUntilDue(uint32_t now_ms) const;

private:
    uint32_t jitter(uint32_t random_value) const;

    uint32_t period_ms_;
    uint32_t slot_offset_ms_;
    uint32_t max_jitter_ms_;
    uint32_t slot_base_ms_ = 0;  // slot start without jitter
    uint32_t next_due_ms_ = 0;   // slot start + jitter
};
