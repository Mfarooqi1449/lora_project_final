# LoRa Packet Protocol — version 1

Used between the ESP32 field nodes and the Raspberry Pi main node.
Implemented in [`esp32-node/src/packet_builder.cpp`](../esp32-node/src/packet_builder.cpp)
(C++) and [`raspberry-pi/app/protocol.py`](../raspberry-pi/app/protocol.py) (Python).
A test (`raspberry-pi/tests/test_protocol.py::test_matches_firmware_encoder`) compiles
the C++ encoder on the host and checks that Python decodes it byte-for-byte.

## Radio layer

| Setting          | Value                         |
|------------------|-------------------------------|
| Frequency        | 433.000 MHz (check local rules) |
| Bandwidth        | 125 kHz                       |
| Spreading factor | SF7 (bench); raise for range  |
| Coding rate      | 4/5                           |
| Preamble         | 8 symbols                     |
| Sync word        | 0x12 (private)                |
| Header           | explicit                      |
| LoRa CRC         | enabled                       |
| TX power         | 10 dBm                        |

Airtime of one 33-byte packet at SF7/125 kHz is about 72 ms. At SF12 it is about 1.8 s.

## Packet layout (33 bytes, little-endian)

| Offset | Size | Field             | Encoding                       | Invalid value |
|-------:|-----:|-------------------|--------------------------------|---------------|
| 0      | 1    | magic             | `0x4C` (`'L'`)                 | —             |
| 1      | 1    | protocol_version  | `1`                            | —             |
| 2      | 1    | node_id           | 1..254                         | —             |
| 3      | 4    | sequence_number   | uint32, starts at 0 after boot | —             |
| 7      | 4    | uptime_seconds    | uint32                         | —             |
| 11     | 2    | temperature       | int16, °C × 100                | `-32768`      |
| 13     | 2    | humidity          | uint16, %RH × 100              | `0xFFFF`      |
| 15     | 2    | pressure          | uint16, hPa × 10               | `0xFFFF`      |
| 17     | 4    | light             | uint32, lux × 100              | `0xFFFFFFFF`  |
| 21     | 2    | air_quality_raw   | uint16, MQ-135 ADC 0..4095     | `0xFFFF`      |
| 23     | 2    | sound_avg         | uint16, mean abs deviation     | `0xFFFF`      |
| 25     | 2    | sound_peak        | uint16, peak-to-peak           | `0xFFFF`      |
| 27     | 2    | supply_mv         | uint16, millivolts             | `0xFFFF`      |
| 29     | 2    | status_flags      | bit field (below)              | —             |
| 31     | 2    | crc16             | CRC-16/CCITT-FALSE of bytes 0..30 | —          |

CRC-16/CCITT-FALSE uses polynomial `0x1021` with initial value `0xFFFF`, no reflection and no final XOR. The check value for `"123456789"` is `0x29B1`.

## Status flags

| Bit | Name                   | Meaning                                    |
|----:|------------------------|--------------------------------------------|
| 0   | BME280_ERROR           | BME280 not detected / read failed          |
| 1   | BH1750_ERROR           | BH1750 not detected / read failed          |
| 2   | MQ135_WARMUP           | uptime < warm-up time (air alerts ignored) |
| 3   | MQ135_SATURATED        | MQ-135 ADC at full scale                   |
| 4   | SOUND_SATURATED        | sound ADC at full scale                    |
| 5   | SUPPLY_LOW             | supply below firmware threshold            |
| 6   | SUPPLY_NOT_MONITORED   | supply monitor disabled                    |
| 7   | BME280_OUT_OF_RANGE    | BME280 values outside datasheet range      |
| 8   | BH1750_OUT_OF_RANGE    | BH1750 value outside range                 |
| 9   | LAST_TX_FAILED         | previous transmission failed               |
| 10  | BOOT                   | first packet after node reset              |
| 15  | PI_RANGE_REJECTED      | set by the Pi when it discarded a value    |

## Sequence numbers and packet loss

- Each node increments `sequence_number` once per transmission slot. It still increments when a transmission fails or a slot is skipped, so the Pi can count those packets as lost.
- On the Pi, a packet with the same sequence number and uptime as the last accepted one is a **duplicate**. It is rejected and logged.
- A gap of N sequence numbers counts as N **lost packets**.
- The Pi treats the node as **reset** if the `BOOT` flag is set, the uptime decreased, or the sequence number went backwards. In that case it counts `sequence_number` packets as lost.
- The Pi stores the last sequence number of each node in SQLite, so loss tracking continues correctly after the Pi restarts.

## Timing

Nodes transmit every 60 s, offset from their boot time: Node 1 at 10 s and Node 2 at 40 s. Each packet adds 0–2 s of random jitter. The slots are computed on a fixed grid, so jitter does not accumulate. The nodes have no real-time clock, so their slots can drift relative to each other. The random jitter and the short airtime keep repeated collisions unlikely.
