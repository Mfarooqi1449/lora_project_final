// Host unit tests for the hardware-independent firmware modules.
//   make -C test_host        (builds and runs)
//   ./test_host/run_tests --vector   prints a reference packet as hex
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "data_filter.h"
#include "packet_builder.h"
#include "scheduler.h"

static int failures = 0;

#define CHECK(cond)                                                     \
    do {                                                                \
        if (!(cond)) {                                                  \
            fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); \
            ++failures;                                                 \
        }                                                               \
    } while (0)

static packet::Fields referenceFields() {
    packet::Fields f;
    f.node_id = 2;
    f.sequence_number = 123456;
    f.uptime_seconds = 7890;
    f.temperature_c = -12.34f;
    f.humidity_percent = 56.78f;
    f.pressure_hpa = 1013.2f;
    f.light_lux = 345.67f;
    f.air_quality_raw = 1500;
    f.sound_avg = 42;
    f.sound_peak = 900;
    f.supply_mv = 4987;
    f.status_flags = packet::FLAG_MQ135_WARMUP | packet::FLAG_BOOT;
    return f;
}

static void testCrc() {
    const uint8_t text[] = "123456789";
    CHECK(packet::crc16Ccitt(text, 9) == 0x29B1);  // CRC-16/CCITT-FALSE check value
}

static void testEncode() {
    uint8_t buf[packet::PACKET_SIZE];
    CHECK(packet::encode(referenceFields(), buf, sizeof(buf)) == packet::PACKET_SIZE);
    CHECK(buf[0] == packet::MAGIC);
    CHECK(buf[1] == packet::PROTOCOL_VERSION);
    CHECK(buf[2] == 2);
    CHECK((buf[3] | buf[4] << 8 | buf[5] << 16 | buf[6] << 24) == 123456);
    int16_t t = static_cast<int16_t>(buf[11] | buf[12] << 8);
    CHECK(t == -1234);
    uint16_t crc = static_cast<uint16_t>(buf[31] | buf[32] << 8);
    CHECK(crc == packet::crc16Ccitt(buf, 31));

    uint8_t small[10];
    CHECK(packet::encode(referenceFields(), small, sizeof(small)) == 0);
}

static void testInvalidValues() {
    packet::Fields f = referenceFields();
    f.temperature_c = NAN;
    f.humidity_percent = NAN;
    f.pressure_hpa = -5.0f;
    f.light_lux = NAN;
    uint8_t buf[packet::PACKET_SIZE];
    packet::encode(f, buf, sizeof(buf));
    CHECK(static_cast<int16_t>(buf[11] | buf[12] << 8) == packet::INVALID_I16);
    CHECK((buf[13] | buf[14] << 8) == packet::INVALID_U16);
    CHECK((buf[15] | buf[16] << 8) == packet::INVALID_U16);
    CHECK(buf[17] == 0xFF && buf[18] == 0xFF && buf[19] == 0xFF && buf[20] == 0xFF);
}

static void testTrimmedMean() {
    uint16_t samples[8] = {100, 4095, 102, 98, 0, 101, 99, 100};
    CHECK(filter::trimmedMean(samples, 8) == 100);
    CHECK(filter::trimmedMean(nullptr, 0) == 0);
    uint16_t one[1] = {7};
    CHECK(filter::trimmedMean(one, 1) == 7);
}

static void testSoundStats() {
    uint16_t flat[4] = {2000, 2000, 2000, 2000};
    filter::SoundStats s = filter::computeSoundStats(flat, 4);
    CHECK(s.average_deviation == 0 && s.peak_to_peak == 0 && s.maximum == 2000);

    uint16_t wave[4] = {1900, 2100, 1900, 2100};
    s = filter::computeSoundStats(wave, 4);
    CHECK(s.average_deviation == 100);
    CHECK(s.peak_to_peak == 200);
    CHECK(s.maximum == 2100);
}

static void testInRange() {
    CHECK(filter::inRange(25.0f, -40.0f, 85.0f));
    CHECK(!filter::inRange(90.0f, -40.0f, 85.0f));
    CHECK(!filter::inRange(NAN, -40.0f, 85.0f));
}

static void testScheduler() {
    Scheduler s(60000, 10000, 2000);
    s.start(0, 500);
    CHECK(s.nextDueMs() == 10500);
    CHECK(!s.isDue(10499));
    CHECK(s.isDue(10500));
    CHECK(s.advance(11000, 0) == 0);
    CHECK(s.nextDueMs() == 70000);  // fixed grid, jitter does not accumulate
    CHECK(s.advance(200000, 2000) == 2);  // 130000 and 190000 missed
    CHECK(s.nextDueMs() == 252000);

    // millis() wrap-around
    Scheduler w(60000, 10000, 0);
    w.start(0xFFFFFF00UL, 0);
    CHECK(!w.isDue(0xFFFFFFF0UL));
    CHECK(w.isDue(static_cast<uint32_t>(0xFFFFFF00UL + 10000UL)));
}

int main(int argc, char** argv) {
    if (argc > 1 && strcmp(argv[1], "--vector") == 0) {
        uint8_t buf[packet::PACKET_SIZE];
        packet::encode(referenceFields(), buf, sizeof(buf));
        for (size_t i = 0; i < sizeof(buf); ++i) printf("%02X", buf[i]);
        printf("\n");
        return 0;
    }

    testCrc();
    testEncode();
    testInvalidValues();
    testTrimmedMean();
    testSoundStats();
    testInRange();
    testScheduler();

    if (failures == 0) {
        printf("All firmware host tests passed.\n");
        return 0;
    }
    printf("%d check(s) failed.\n", failures);
    return 1;
}
