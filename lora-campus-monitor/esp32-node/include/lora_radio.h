// SX1278 / Ra-02 transmitter wrapper around the sandeepmistry LoRa library.
#pragma once

#include <stddef.h>
#include <stdint.h>

class LoraRadio {
public:
    // Configures SPI, resets the module and applies the radio settings from
    // board_config.h. Returns false if the SX1278 does not respond.
    bool begin();

    bool ready() const { return ready_; }

    // Blocking transmit; puts the radio to sleep afterwards.
    bool send(const uint8_t* data, size_t length);

    uint32_t lastAirtimeMs() const { return last_airtime_ms_; }

private:
    bool ready_ = false;
    uint32_t last_airtime_ms_ = 0;
};
