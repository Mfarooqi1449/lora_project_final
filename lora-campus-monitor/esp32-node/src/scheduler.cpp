#include "scheduler.h"

Scheduler::Scheduler(uint32_t period_ms, uint32_t slot_offset_ms, uint32_t max_jitter_ms)
    : period_ms_(period_ms == 0 ? 1 : period_ms),
      slot_offset_ms_(slot_offset_ms),
      max_jitter_ms_(max_jitter_ms) {}

uint32_t Scheduler::jitter(uint32_t random_value) const {
    return max_jitter_ms_ == 0 ? 0 : random_value % (max_jitter_ms_ + 1);
}

void Scheduler::start(uint32_t now_ms, uint32_t random_value) {
    slot_base_ms_ = now_ms + slot_offset_ms_;
    next_due_ms_ = slot_base_ms_ + jitter(random_value);
}

bool Scheduler::isDue(uint32_t now_ms) const {
    return static_cast<int32_t>(now_ms - next_due_ms_) >= 0;
}

uint32_t Scheduler::msUntilDue(uint32_t now_ms) const {
    int32_t remaining = static_cast<int32_t>(next_due_ms_ - now_ms);
    return remaining > 0 ? static_cast<uint32_t>(remaining) : 0;
}

uint32_t Scheduler::advance(uint32_t now_ms, uint32_t random_value) {
    uint32_t skipped = 0;
    slot_base_ms_ += period_ms_;
    while (static_cast<int32_t>(now_ms - slot_base_ms_) >= 0) {
        slot_base_ms_ += period_ms_;
        ++skipped;
    }
    next_due_ms_ = slot_base_ms_ + jitter(random_value);
    return skipped;
}
