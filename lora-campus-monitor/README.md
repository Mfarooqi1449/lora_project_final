# LoRa-Based Distributed Environmental Monitoring System

This system monitors environmental conditions at two campus locations.

- **Two ESP32 field nodes** each read a BME280, BH1750, MQ-135 and a sound sensor. Once per minute each node sends one LoRa packet through an SX1278/Ra-02 module.
- **A Raspberry Pi 3B+ main node** receives, validates and timestamps the packets and stores them in SQLite.
- **A Flask dashboard** on the Pi shows live and historical data, node status and alerts, and provides CSV export.

```
ESP32 NODE 1 ── LoRa ──┐
                       ├── RASPBERRY PI 3B+ ── SQLite ── Flask dashboard (:5000)
ESP32 NODE 2 ── LoRa ──┘                      └─ alerts, CSV export, backups
```

## Repository layout

```
lora-campus-monitor/
  esp32-node/                 C++ firmware (PlatformIO, Arduino framework)
    platformio.ini            env:node1 (NODE_ID=1), env:node2 (NODE_ID=2)
    include/ src/             board_config, node_identity, sensor_manager, data_filter,
                              packet_builder, lora_radio, scheduler, diagnostics, main
    test_host/                host unit tests (g++) for the hardware-independent code
  raspberry-pi/               Python main-node application
    app/                      config, sx1278 driver, protocol, validator, sequence,
                              database, alerts, processor, receiver, web, exporter, ...
    config/config.toml        radio settings, nodes, thresholds, paths
    scripts/                  install.sh, init_db.py, backup_db.py, radio_test.py
    systemd/                  receiver + dashboard services, daily backup timer
    tests/                    pytest suite (no hardware needed)
    database/ logs/           created at runtime
  docs/packet_protocol.md     packet format, flags, sequence/loss rules
  docs/file_reference.md      detailed explanation of every file, one by one
  docs/HOW_TO_RUN.txt         prerequisites + how to run/connect on any machine
  connections/                self-contained wiring pack: guides, master connection
                              list (.txt/.csv), 3D viewer + launchers (see README.txt)
  tools/decode_packet.py      decode a packet hex string from the ESP32 serial log
```

---

## 1. ESP32 field nodes (C++)

### Build and flash

Install [PlatformIO](https://platformio.org/) (the VS Code extension or `pip install platformio`), then:

```bash
cd esp32-node
pio run -e node1 -t upload      # flash board 1 (NODE_ID = 1)
pio run -e node2 -t upload      # flash board 2 (NODE_ID = 2)
pio device monitor -b 115200    # serial diagnostics
```

`NODE_ID` is set at compile time by the environment, so it cannot be changed by mistake on the board.

### Configuration

All pins, radio settings and timing are in [`include/board_config.h`](esp32-node/include/board_config.h). The pin map follows the hardware document:

| Function      | GPIO | Function      | GPIO |
|---------------|------|---------------|------|
| LoRa SCK      | 18   | I2C SDA       | 21   |
| LoRa MISO     | 19   | I2C SCL       | 22   |
| LoRa MOSI     | 23   | MQ-135 (div.) | 34   |
| LoRa NSS      | 5    | Sound         | 35   |
| LoRa RESET    | 14   | Supply mon.   | 32   |
| LoRa DIO0     | 26   |               |      |

Things to check before the first upload:
- **BME280 address:** the default is `0x76` (SDO to GND). Use `0x77` if SDO is tied to 3.3 V.
- **Supply monitor:** set `SUPPLY_MONITOR_ENABLED = false` if the 100k/100k divider on GPIO32 is not fitted.
- **Radio settings:** they must be identical in `board_config.h` and in `raspberry-pi/config/config.toml`.
- **Frequency:** 433 MHz. Check your local regulations; in India the 433–434.79 MHz band is licence-free at low power. Transmit power is set to a conservative 10 dBm.

### What the firmware does
1. Initialises serial, I2C, the ADC with 11 dB attenuation, the sensors and the LoRa radio. It prints the result of each step.
2. Once per slot (60 s, Node 1 at +10 s and Node 2 at +40 s, plus 0–2 s jitter):
   - Reads the BME280 in forced mode and the BH1750.
   - Takes 32 samples of the MQ-135 and of the supply voltage and averages the middle half (trimmed mean).
   - Samples the sound input at 2 kHz for 1 s and computes the average deviation and the peak-to-peak value.
   - Checks values against the sensor datasheet ranges and sets status flags.
   - Builds the 33-byte packet with a CRC-16 and transmits it. It prints the readings and the packet hex.
3. Re-detects missing sensors every 30 s. A disconnected sensor sets an error flag and the node keeps running.
4. A 30 s task watchdog resets the ESP32 if it hangs, for example if the radio stops responding. After a power cut or reset the node restarts sampling on its own; its first packet carries the `BOOT` flag.

### Host tests

```bash
make -C esp32-node/test_host        # builds and runs with g++
```

---

## 2. Raspberry Pi main node (Python)

Requirements: Raspberry Pi OS **Bookworm** (Python 3.11 or newer) with SPI enabled.

### Wiring (Ra-02 to Pi, 3.3 V only)

| Ra-02 | Pi physical pin (BCM) |
|-------|-----------------------|
| VCC   | 1 (3.3 V)             |
| GND   | 6                     |
| SCK   | 23 (GPIO11)           |
| MISO  | 21 (GPIO9)            |
| MOSI  | 19 (GPIO10)           |
| NSS   | 24 (GPIO8, CE0)       |
| RESET | 22 (GPIO25)           |
| DIO0  | 18 (GPIO24)           |

### Install (production)

```bash
git clone <your-repo> lora-campus-monitor   # or copy the folder to the Pi
cd lora-campus-monitor
sudo ./raspberry-pi/scripts/install.sh
sudo nano /opt/lora-campus-monitor/raspberry-pi/config/config.toml   # set node locations
sudo systemctl restart lora-receiver lora-dashboard
```

The installer does the following:
- Installs the apt packages: `python3-spidev`, `python3-gpiozero`, `python3-lgpio`, `sqlite3`, `rsync`.
- Enables SPI.
- Creates the non-root `loramon` user and adds it to the `spi` and `gpio` groups.
- Copies the app to `/opt/lora-campus-monitor` and creates a virtual environment with Flask and waitress.
- Initialises the database.
- Installs and enables three systemd units:
  - `lora-receiver.service` receives radio packets and stores them. It needs only local storage, so it keeps working when Wi-Fi is down.
  - `lora-dashboard.service` serves the dashboard with waitress on port 5000.
  - `lora-backup.timer` makes a daily SQLite backup at 02:30.

All of these restart automatically on failure and start after a reboot.

Open the dashboard at `http://<raspberry-pi-ip>:5000`.

Useful commands:
```bash
systemctl status lora-receiver lora-dashboard
journalctl -u lora-receiver -f                  # live packet log
sudo systemctl stop lora-receiver && sudo -u loramon /opt/lora-campus-monitor/raspberry-pi/.venv/bin/python \
     /opt/lora-campus-monitor/raspberry-pi/scripts/radio_test.py    # raw radio bench test
```

### Development / demo without hardware

```bash
cd raspberry-pi
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest                                 # full test suite
python -m app.receiver --simulate --sim-period 5 # fake nodes, one packet / 5 s each
python -m app.web                                # dashboard on http://localhost:5000
```

The simulator produces real protocol packets. It also simulates some packet loss and CRC errors, so loss tracking and rejected-packet logging can be demonstrated.

### Receiver pipeline

```
SX1278 RxDone ─► radio CRC check ─► decode (length, magic, version, CRC-16)
   ─► known & enabled node? ─► duplicate / gap / node-reset check
   ─► range validation ─► SQLite insert + node statistics ─► alert engine
Rejected packets ─► rejected_packets table + log (with reason and raw hex)
Every 10 s: offline check · every 60 s: heartbeat + radio health · daily: retention
```

### Alerts

Thresholds are set in `config/config.toml` under `[[alerts.rules]]`.
- An alert opens only after `consecutive_samples` violating packets in a row (default 3, about 3 minutes).
- It clears only after the same number of packets on the other side of the `clear` value (hysteresis).
- There is at most one active alert per node and alert type; the database enforces this.
- Built-in alert types:
  - `sensor_failure_bme280` and `sensor_failure_bh1750` come from the sensor status flags.
  - `node_offline` opens when no packet arrives within `offline_timeout_s` (default 180 s).
- Alerts on MQ-135 values are ignored during the sensor's warm-up period.
- Opening and clearing times are stored, and alerts can be acknowledged on the Alerts page.
- The thresholds supplied are starting values only. Set the final values from field measurements.

### Database

The SQLite file is `database/monitor.db`. It uses WAL mode, so the dashboard can read while the receiver writes. Tables:
- `nodes`: metadata plus last-seen time and packet counters
- `readings`
- `alerts`
- `system_events`
- `rejected_packets`
- `system_status`: the receiver heartbeat

To keep the database from growing forever, set `retention_days` to delete old readings automatically.

Backup and restore:
```bash
python scripts/backup_db.py                       # to database/backups (keeps 14)
python scripts/backup_db.py --dest /media/usb     # to a USB drive
sudo systemctl stop lora-receiver lora-dashboard
python scripts/backup_db.py --restore database/backups/monitor-YYYYmmdd-HHMMSS.db
sudo systemctl start lora-receiver lora-dashboard
```

### Dashboard

| Page        | Content |
|-------------|---------|
| Overview    | Receiver, radio and database status; online/offline state of each node; latest values, last packet time, RSSI/SNR, loss and alert count |
| Node 1 / 2  | Current values; RSSI/SNR; packets received, lost and duplicated; node restarts; sensor flags; charts for 1 h / 6 h / 24 h / 7 d / 30 d; recent packets |
| Alerts      | Active alerts (with acknowledge button) and cleared alerts with severity and timestamps |
| Maintenance | CSV export by node and time range; database size and backup status; Pi CPU temperature and disk space; application version; system events; rejected packets |

JSON API endpoints:
- `/api/overview`
- `/api/nodes/<id>`
- `/api/nodes/<id>/history?hours=24`
- `/api/alerts`
- `/export.csv?node_id=1&start=…&end=…` (times in ISO 8601)
- `/healthz`

The dashboard has no login. Keep it on the local network and do not forward port 5000 to the internet unless you add authentication.

---

## 3. Bring-up order (summary of the delivery plan)

1. Run the firmware host tests and `pytest` on a PC.
2. Prepare the Pi: install the OS, enable SPI, and run `install.sh`. Use `--simulate` to check the dashboard.
3. Build Node 1 without LoRa and check every sensor in the serial monitor for one hour. Then build and test Node 2.
4. Connect antennas **before** powering any LoRa module.
5. Stop `lora-receiver` and run `scripts/radio_test.py` on the Pi. Power Node 1 only, then Node 2 only, then both. Record RSSI, SNR and sequence numbers.
6. Start `lora-receiver` and confirm that rows appear on the dashboard.
7. Test alerts: lower a threshold in `config.toml` and restart `lora-receiver`. Switch a node off to see the `node_offline` alert after 3 minutes.
8. Field test, then a 24–72 h reliability run that includes reboots, power cycles, a Wi-Fi outage and a backup restore.

## Limitations

- MQ-135 gives only an approximate air-quality indication; it is not a calibrated CO₂ or AQI sensor. The firmware flags readings during the first 3 minutes of warm-up, but the sensor needs 24–48 h of burn-in for stable readings.
- The sound module gives a relative activity level, not dB SPL.
- LoRa range depends on antennas, obstacles and mounting height. Report only ranges you have actually measured.
- The packets are not encrypted or authenticated. This is acceptable for an educational prototype only.
