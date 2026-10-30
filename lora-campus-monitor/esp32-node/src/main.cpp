// ESP32 field node: read sensors -> build packet -> LoRa transmit, once per slot.
#include <Arduino.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <esp_task_wdt.h>

#include "board_config.h"
#include "diagnostics.h"
#include "lora_radio.h"
#include "node_identity.h"
#include "packet_builder.h"
#include "scheduler.h"
#include "sensor_manager.h"

namespace {

SensorManager sensors;
LoraRadio lora;
Scheduler scheduler(timing::TX_PERIOD_MS, identity::SLOT_OFFSET_MS, timing::MAX_JITTER_MS);

uint32_t sequence_number = 0;  // restarts at 0 after reboot; Pi detects via FLAG_BOOT
bool last_tx_failed = false;

void transmitCycle() {
    // 64-bit timer: no wrap-around after 49 days like millis().
    uint32_t uptime_s = static_cast<uint32_t>(esp_timer_get_time() / 1000000LL);
    SensorSnapshot s = sensors.read(uptime_s);

    if (!lora.ready()) {
        bool ok = lora.begin();
        diagnostics::printInitResult("LoRa", ok);
    }

    packet::Fields fields;
    fields.node_id = identity::NODE;
    fields.sequence_number = sequence_number;
    fields.uptime_seconds = uptime_s;
    fields.temperature_c = s.temperature_c;
    fields.humidity_percent = s.humidity_percent;
    fields.pressure_hpa = s.pressure_hpa;
    fields.light_lux = s.light_lux;
    fields.air_quality_raw = s.air_quality_raw;
    fields.sound_avg = s.sound_avg;
    fields.sound_peak = s.sound_peak;
    fields.supply_mv = s.supply_mv;
    fields.status_flags = s.flags;
    if (last_tx_failed) fields.status_flags |= packet::FLAG_LAST_TX_FAILED;
    if (sequence_number == 0) fields.status_flags |= packet::FLAG_BOOT;

    s.flags = fields.status_flags;
    diagnostics::printReading(sequence_number, s);

    uint8_t buffer[packet::PACKET_SIZE];
    size_t length = packet::encode(fields, buffer, sizeof(buffer));
    bool ok = length > 0 && lora.send(buffer, length);
    diagnostics::printTxResult(sequence_number, ok, lora.lastAirtimeMs(), buffer, length);

    last_tx_failed = !ok;
    ++sequence_number;  // increments even on failure so the Pi can count the loss
}

}  // namespace

void setup() {
    diagnostics::begin();
    diagnostics::printBanner();

    esp_task_wdt_init(timing::WATCHDOG_TIMEOUT_S, true);
    esp_task_wdt_add(nullptr);

    sensors.begin();
    diagnostics::printInitResult("BME280", sensors.bme280Present());
    diagnostics::printInitResult("BH1750", sensors.bh1750Present());

    bool radio_ok = lora.begin();
    diagnostics::printInitResult("LoRa", radio_ok);

    scheduler.start(millis(), esp_random());
    Serial.printf("[sched] first transmission in %lu ms\n",
                  static_cast<unsigned long>(scheduler.msUntilDue(millis())));
}

void loop() {
    esp_task_wdt_reset();

    if (scheduler.isDue(millis())) {
        transmitCycle();
        uint32_t skipped = scheduler.advance(millis(), esp_random());
        diagnostics::printSkippedSlots(skipped);
        sequence_number += skipped;  // skipped slots count as lost packets
    }

    delay(20);
}
