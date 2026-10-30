#include "lora_radio.h"

#include <Arduino.h>
#include <LoRa.h>
#include <SPI.h>

#include "board_config.h"

bool LoraRadio::begin() {
    SPI.begin(board::PIN_LORA_SCK, board::PIN_LORA_MISO, board::PIN_LORA_MOSI, board::PIN_LORA_NSS);
    LoRa.setSPI(SPI);
    LoRa.setPins(board::PIN_LORA_NSS, board::PIN_LORA_RESET, board::PIN_LORA_DIO0);

    // LoRa.begin() resets the module and checks the SX127x version register.
    if (!LoRa.begin(radio::FREQUENCY_HZ)) {
        ready_ = false;
        return false;
    }

    LoRa.setSignalBandwidth(radio::BANDWIDTH_HZ);
    LoRa.setSpreadingFactor(radio::SPREADING_FACTOR);  // also sets low-data-rate optimize
    LoRa.setCodingRate4(radio::CODING_RATE_DENOM);
    LoRa.setPreambleLength(radio::PREAMBLE_LENGTH);
    LoRa.setSyncWord(radio::SYNC_WORD);
    LoRa.enableCrc();
    LoRa.setTxPower(radio::TX_POWER_DBM);  // PA_BOOST output (Ra-02)
    LoRa.sleep();

    ready_ = true;
    return true;
}

bool LoraRadio::send(const uint8_t* data, size_t length) {
    if (!ready_) return false;

    LoRa.idle();
    if (!LoRa.beginPacket(false)) {  // explicit header mode
        LoRa.sleep();
        return false;
    }
    LoRa.write(data, length);
    uint32_t start = millis();
    // Blocking; a hung radio is recovered by the task watchdog.
    bool ok = LoRa.endPacket(false) == 1;
    last_airtime_ms_ = millis() - start;
    LoRa.sleep();
    return ok;
}
