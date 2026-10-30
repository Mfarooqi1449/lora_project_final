# File Reference — Every File Explained

This document explains every file in the **LoRa Campus Monitor** project, one by one. For each file it covers:

- **Purpose:** why the file exists.
- **Contents:** the main parts (classes, functions, settings, sections).
- **How it works:** the logic, step by step where useful.
- **When to edit it:** what you would change and why.
- **Related files:** files it depends on or that depend on it.

Files are grouped by folder, in the order you would normally meet them.

---

## Table of contents

1. [Project root](#1-project-root)
2. [connections/ — wiring documents](#2-connections--wiring-documents)
3. [docs/ — documentation](#3-docs--documentation)
4. [esp32-node/ — C++ firmware for the field nodes](#4-esp32-node--c-firmware-for-the-field-nodes)
5. [raspberry-pi/ — Python main-node application](#5-raspberry-pi--python-main-node-application)
   - 5.1 [Top-level files](#51-top-level-files)
   - 5.2 [config/](#52-config)
   - 5.3 [app/ — Python package](#53-app--python-package)
   - 5.4 [app/templates/ — HTML pages](#54-apptemplates--html-pages)
   - 5.5 [app/static/ — CSS and JavaScript](#55-appstatic--css-and-javascript)
   - 5.6 [scripts/](#56-scripts)
   - 5.7 [systemd/](#57-systemd)
   - 5.8 [tests/](#58-tests)
   - 5.9 [database/ and logs/](#59-database-and-logs)
6. [tools/](#6-tools)
7. [How the files work together (end-to-end walk-through)](#7-how-the-files-work-together)

Folder tree:

```
lora-campus-monitor/
├── README.md
├── .gitignore
├── connections/
│   ├── 00_index_and_overview.txt
│   ├── 01_main_node_raspberry_pi.txt
│   ├── 02_field_node_1_esp32.txt
│   ├── 03_field_node_2_esp32.txt
│   ├── 04_master_connection_list.txt, master_connection_list.csv
│   ├── 05_hardware_list.txt, hardware_list.csv
│   ├── README.txt, start_3d_viewer.py / .bat / .sh
│   └── 3d/  connections_3d.html, connections_3d.js, README.md, vendor/, images/*.png
├── docs/
│   ├── packet_protocol.md
│   ├── HOW_TO_RUN.txt
│   └── file_reference.md            (this file)
├── esp32-node/
│   ├── platformio.ini
│   ├── include/  board_config.h, node_identity.h, packet_builder.h, data_filter.h,
│   │             scheduler.h, sensor_manager.h, lora_radio.h, diagnostics.h
│   ├── src/      main.cpp, packet_builder.cpp, data_filter.cpp, scheduler.cpp,
│   │             sensor_manager.cpp, lora_radio.cpp, diagnostics.cpp
│   └── test_host/ Makefile, test_main.cpp
├── raspberry-pi/
│   ├── requirements.txt, requirements-dev.txt, pytest.ini
│   ├── config/config.toml
│   ├── app/      __init__.py, config.py, protocol.py, validator.py, sequence.py,
│   │             database.py, alerts.py, processor.py, sx1278.py, simulator.py,
│   │             receiver.py, web.py, serve.py, exporter.py, health.py, logging_setup.py
│   │   ├── templates/ base.html, overview.html, node.html, alerts.html, maintenance.html
│   │   └── static/    style.css, app.js
│   ├── scripts/  install.sh, init_db.py, backup_db.py, radio_test.py
│   ├── systemd/  lora-receiver.service, lora-dashboard.service,
│   │             lora-backup.service, lora-backup.timer
│   ├── tests/    conftest.py, test_config.py, test_protocol.py, test_sequence.py,
│   │             test_processor.py, test_sx1278.py, test_web.py
│   ├── database/ .gitkeep   (monitor.db is created here at runtime)
│   └── logs/     .gitkeep   (receiver.log / dashboard.log at runtime)
└── tools/
    └── decode_packet.py
```

---

## 1. Project root

### `README.md`

- **Purpose:** The entry point for anyone opening the project. It explains what the system does and how to build, install, run and test it.
- **Contents:**
  1. System summary and network diagram (two ESP32 nodes, LoRa, Raspberry Pi, SQLite, Flask).
  2. Repository layout.
  3. **ESP32 section:**
     - how to build and flash with PlatformIO (`pio run -e node1 -t upload`);
     - pin table, settings to check before the first upload, and what the firmware does each minute;
     - how to run the host tests.
  4. **Raspberry Pi section:**
     - wiring table and production install (`sudo ./raspberry-pi/scripts/install.sh`);
     - useful `systemctl`/`journalctl` commands and the development/simulation mode;
     - receiver pipeline diagram;
     - how alerts, the database, backup/restore and the dashboard pages work.
  5. Bring-up order (a short version of the 16-phase delivery plan).
  6. Limitations (MQ-135 and the sound sensor are not certified instruments, no encryption, range must be measured).
- **When to edit it:** whenever setup steps, commands, folder layout or features change.
- **Related files:** all other files. The README links to `docs/packet_protocol.md` and refers to `config.toml`, `install.sh` and the scripts.

### `.gitignore`

- **Purpose:** Tells Git which files must **not** be committed.
- **Contents:**
  - `esp32-node/.pio/`: PlatformIO build output and downloaded libraries (large, regenerated on each build).
  - `esp32-node/test_host/run_tests`: the compiled host test program.
  - `__pycache__/`, `.pytest_cache/`, `.venv/`: Python caches and the virtual environment.
  - `raspberry-pi/database/*` and `raspberry-pi/logs/*`: runtime data (the SQLite database and log files). These are machine-specific and may be large.
  - Exceptions `!…/.gitkeep`: keep the empty folders in Git so they exist after cloning.
- **When to edit it:** if you add new generated files or local secrets.

---

## 2. `connections/` — wiring documents

These plain-text files are the **hardware wiring instructions**. They are written to be printed and used at the workbench. The pin numbers match the firmware (`board_config.h`) and the Pi configuration (`config.toml`) exactly.

### `connections/00_index_and_overview.txt`

- **Purpose:** One-page summary of the whole system's wiring.
- **Contents:**
  - **Index:** which file covers which board.
  - **Block diagram:**
    - Node 1 and Node 2 (sensors → ESP32 → Ra-02) send over 433 MHz LoRa to the Pi's Ra-02.
    - The Pi stores the data in SQLite and serves the dashboard, which a laptop or phone opens over Ethernet or Wi-Fi.
  - **Statement** that the three units are only linked by radio, never by wires.
  - **Pin summary table:** every signal with its ESP32 GPIO and its Pi physical pin / BCM number.
  - **Golden rules:** Ra-02 is 3.3 V only; ESP32 inputs take at most 3.3 V; fit the antenna before power; one common GND inside each unit; identical radio settings on all three modules.
- **When to edit it:** if any pin assignment changes. Also update the other three files, `board_config.h` and `config.toml`.

### `connections/01_main_node_raspberry_pi.txt`

- **Purpose:** Complete wiring guide for the **Raspberry Pi 3B+ main node** and its SX1278/Ra-02 receiver.
- **Contents (sections):**
  - **Safety first:**
    - power off before wiring;
    - Ra-02 VCC goes on pin 1 (3.3 V), **never on pin 2 or 4 (5 V)**;
    - fit the antenna before power;
    - use an adapter PCB for the SMD module.
  - **Parts list** for the main node.
  - **Wire colour code** (orange 3.3 V, black GND, yellow SCK, and so on).
  - **1. Power and storage:** microSD card, 5 V/2.5 A micro-USB adapter.
  - **2. Pi → Ra-02 table:**

    | Ra-02 pin | Pi physical pin | BCM name |
    |---|---|---|
    | VCC | 1 | 3.3 V |
    | GND | 6 | GND |
    | SCK | 23 | GPIO11 |
    | MISO | 21 | GPIO9 |
    | MOSI | 19 | GPIO10 |
    | NSS | 24 | GPIO8 / CE0 |
    | RESET | 22 | GPIO25 |
    | DIO0 | 18 | GPIO24 |

    DIO1 to DIO5 are not connected.
  - **3. Decoupling capacitors:** 100 nF and 10 µF placed right at the Ra-02.
  - **4. Antenna mounting.**
  - **5. ASCII map of the 40-pin header** marking the pins used and the forbidden 5 V pins, and where pin 1 is.
  - **6. Network** options and the dashboard URL.
  - **7. Radio settings** that must match the nodes.
  - **8. Power-on checklist:**
    - wiring and continuity checks;
    - enable SPI and confirm `/dev/spidev0.0` exists;
    - run `scripts/radio_test.py` and check for version `0x12`.
- **Why these pins:** NSS uses CE0 (GPIO8), so the Linux `spidev` driver drives chip-select automatically. RESET and DIO0 are ordinary GPIOs, configured in `config.toml` (`reset_pin = 25`, `dio0_pin = 24`).

### `connections/02_field_node_1_esp32.txt`

- **Purpose:** Complete wiring guide for **ESP32 field node 1** (`NODE_ID = 1`).
- **Contents (sections):**
  - **Header:** the flash command (`pio run -e node1 -t upload`).
  - **Safety rules:** 3.3 V-only Ra-02, 3.3 V maximum on GPIO, divider required for the MQ-135, antenna first, common GND, check your breakout labels.
  - **Parts list** including every resistor and capacitor.
  - **1. Power:**
    - the 5 V adapter feeds a 5 V rail on the perfboard, which supplies ESP32 VIN, the MQ-135 heater and the supply-monitor divider;
    - the ESP32 3V3 pin feeds a 3.3 V rail for the Ra-02, BME280, BH1750 and sound sensor;
    - notes on the ~150 mA MQ-135 heater (use a ≥1 A adapter) and on USB flashing.
  - **2. ESP32 → Ra-02 (SPI):** SCK 18, MISO 19, MOSI 23, NSS 5, RESET 14, DIO0 26, plus capacitors and antenna.
  - **3. BME280 (I2C, 0x76):** SDA 21, SCL 22; CSB to 3.3 V, SDO to GND. Also explains the 0x77 option and the BMP280 look-alike.
  - **4. BH1750 (I2C, 0x23):** shares SDA/SCL with the BME280; ADDR to GND.
  - **5. MQ-135:**
    - a 10 kΩ / 20 kΩ divider, a 1 kΩ series resistor to GPIO34 and a 100 nF filter capacitor;
    - an ASCII diagram and the formula (`Vjunction = AO × 0.667`);
    - the instruction to **measure before connecting**;
    - a note that the ADC saturates near 3.1 V (the firmware then sets the `MQ135_SATURATED` flag).
  - **6. Sound sensor:** a 3.3 V module connects directly to GPIO35; a 5 V module needs the same divider.
  - **7. Supply monitor:** a 100 kΩ / 100 kΩ divider from the 5 V rail to GPIO32 (about 2.5 V at 5 V).
  - **8. GPIO summary.**
  - **9. ASCII pin map** of the 30-pin DevKit V1 showing where each wire goes.
  - **10. Radio settings** and the transmission slot (+10 s).
  - **11. Power-on checklist** with expected voltages and the expected serial output (`Node ID : 1`, `[init] … OK`).

### `connections/03_field_node_2_esp32.txt`

- **Purpose:** Wiring guide for **ESP32 field node 2**.
- **Contents:** identical to Node 1 (same circuit and pins), except:
  - `NODE_ID = 2`, flashed with `pio run -e node2 -t upload`;
  - transmission slot **+40 s** (Node 1 uses +10 s, so they don't transmit at the same moment);
  - cross-references point to Node 1 instead of Node 2;
  - the checklist expects `Node ID : 2`.
- **Why a separate file:** each physical box gets its own printed sheet and its own checklist. This avoids flashing the wrong ID or building from the wrong page.

### `connections/README.txt`

- **Purpose:** The start page of the connections folder. The folder is **self-contained**: it can be copied alone to any computer and used without the rest of the project.
- **Contents:**
  - A list of every file in the folder.
  - How to open each part: the text guides, the CSV in a spreadsheet, and the 3D viewer through the launchers. The viewer needs only Python 3.7+.
  - A table showing which file is needed in which project phase (0 → 16).
  - What must be done before the first power-on.
  - How the pins map to the software settings.
  - The golden rules.

### `connections/04_master_connection_list.txt` and `master_connection_list.csv`

- **Purpose:** **One list of every required connection** for the whole system.
  - **Main node:** IDs M01–M15.
  - **Field node:** IDs N-01–N-43. The field-node list is built twice, so it has two tick boxes, `[N1]` and `[N2]`.
- **Columns:**
  - ID, from → to, wire colour.
  - Need: Required, If pin exists, Recommended, Optional or Not connected.
  - Signal.
  - **Software setting** that uses the pin, for example `board_config.h PIN_LORA_SCK` or `config.toml reset_pin=25`.
  - Note.
- **Section 3** counts what you need:
  - jumper wires per colour (80 in total for 1 main node and 2 field nodes);
  - resistors, capacitors and modules, as a shopping list.
- **The CSV** holds the same data with one row per connection for each unit (101 rows) and a "Done" column. It opens in Excel or Google Sheets.

### `connections/05_hardware_list.txt` and `hardware_list.csv`

- **Purpose:** The **hardware list (bill of materials)** for the complete system: 1 main node and 2 field nodes.
- **Sections:**
  - **A.** Main node.
  - **B.** LoRa radio parts.
  - **C.** Field-node modules.
  - **D.** Passive parts.
  - **E.** Wiring and mechanical parts.
  - **F.** Tools and test equipment.
  - **G.** Optional and future parts.
- **Each item lists:**
  - its specification and a buying note;
  - quantities for the main node, per field node, and spares;
  - **the total to buy** (main + 2 × node + spares);
  - whether it is needed (Required, Recommended, Optional or Future);
  - what it is used for, with connection IDs from `04_master_connection_list.txt`.
- **Also includes:**
  - a summary of the main modules;
  - **buying checks**: everything 433 MHz, BME280 rather than BMP280, an analog 3.3 V sound module, a USB data cable, local radio rules.
- **The CSV** has empty "Unit price" and "Line total" columns. Fill them in to get the cost sheet for the "Bill of materials and cost" deliverable.

### `connections/start_3d_viewer.py`, `.bat`, `.sh`

- **Purpose:** One-click start of the 3D viewer on any operating system, using only the Python standard library.
- **How it works:**
  1. Serves the `3d/` folder with `http.server`. It starts at port 8090 and moves to the next free port if that one is busy.
  2. Opens the browser at `connections_3d.html#<view>`.
- **Options:**
  - `--view system|main|node1|node2`
  - `--port`
  - `--lan`, which also lets phones on the same Wi-Fi open it
  - `--no-browser`
- **Launchers:**
  - The `.bat` is for a Windows double-click. It tries `py -3`, then `python`, and shows a hint if Python is missing.
  - The `.sh` is for Linux and macOS.

### `connections/3d/` — interactive 3D wiring model

- **Purpose:** The same wiring as the `.txt` files, shown as a 3D model you can rotate in a web browser. Each wire is a coloured tube following the wire colour guide.
- **Files:**
  - **`connections_3d.html`:** the page.
    - Top bar with four views: System overview, Main node, Field node 1 and Field node 2, plus checkboxes for pin labels and auto-rotate.
    - 3D canvas.
    - Right-hand list of every connection, grouped by module.
    - Colour legend at the bottom.
  - **`connections_3d.js`:** builds the scenes with three.js.
    - **Helpers:** `box`, `cyl`, `sprite` (text labels), `pin` (a header pin that returns its tip position), `resistor` (with colour bands), `capacitor`, `antenna`, `rail` (power strips) and `wire` (an arched tube between two pins with an info text).
    - **Module builders:** `esp32()` (30-pin DevKit V1), `ra02Module()`, `smallModule()` (BME280, BH1750, MQ-135, sound sensor).
    - **Scene builders:**
      - `buildFieldNode(id)`: perfboard with 3.3 V / 5 V / GND rails and every sensor wire, including the MQ-135 divider.
      - `buildMainNode()`: Raspberry Pi 3B+ with the 40-pin header and the 8 Ra-02 wires; pins 2 and 4 are marked red as 5 V.
      - `buildSystem()`: star network with animated LoRa packets.
    - **Interaction:**
      - `fitCamera()` frames each scene automatically.
      - Hovering over a wire shows a tooltip.
      - Clicking a wire or a list row highlights that connection and fades the others.
  - **`vendor/`:** a local copy of three.js r147 and OrbitControls (MIT licence), so the page works without internet.
  - **`images/`:** PNG renders of each view, plus close-ups of the Pi header, the ESP32 SPI/I2C wiring and the MQ-135 divider. Use them in the report and the PPT.
  - **`README.md`:** how to open the viewer (`python3 -m http.server 8090` in this folder) and a list of the images.

---

## 3. `docs/` — documentation

### `docs/packet_protocol.md`

- **Purpose:** The formal specification of the radio packet. Both programs (C++ on the ESP32, Python on the Pi) must follow it exactly.
- **Contents:**
  - **Radio layer table:** 433 MHz, BW 125 kHz, SF7, CR 4/5, preamble 8, sync word 0x12, explicit header, CRC on, 10 dBm. Airtime is about 72 ms at SF7 and 1.8 s at SF12.
  - **Packet layout:** 33 bytes, little-endian.

    | Offset | Field | Size | Encoding |
    |---|---|---|---|
    | 0 | magic | 1 byte | `0x4C` |
    | 1 | version | 1 byte | |
    | 2 | node id | 1 byte | |
    | 3 | sequence | 4 bytes | |
    | 7 | uptime | 4 bytes | seconds |
    | 11 | temperature | 2 bytes | ×100 |
    | 13 | humidity | 2 bytes | ×100 |
    | 15 | pressure | 2 bytes | ×10 |
    | 17 | lux | 4 bytes | ×100 |
    | 21 | MQ-135 raw | 2 bytes | |
    | 23 | sound average | 2 bytes | |
    | 25 | sound peak | 2 bytes | |
    | 27 | supply | 2 bytes | mV |
    | 29 | flags | 2 bytes | |
    | 31 | CRC-16 | 2 bytes | |

    Each field has an "invalid" sentinel value meaning the sensor failed.
  - **CRC definition:** CRC-16/CCITT-FALSE with check value `0x29B1`.
  - **Status flag table:** bits 0–10 are set by the node; bit 15 is set by the Pi.
  - **Sequence rules:** how duplicates, lost packets and node resets are detected.
  - **Timing:** slots, jitter, no real-time clock.
- **Why a binary format and not JSON:** it is about 33 bytes instead of about 200, so airtime is much shorter. That means fewer collisions, less energy and more range headroom.
- **When to edit it:** whenever you change the packet. You must then also change `packet_builder.*`, `protocol.py` and increase `PROTOCOL_VERSION`.

### `docs/file_reference.md`

- This document.

### `docs/HOW_TO_RUN.txt`

- **Purpose:** A step-by-step operating guide in plain text, for running the project on **any machine**.
- **Contents:**
  - **0. Prerequisites:** Python 3.11+, PlatformIO, drivers, Raspberry Pi OS, hardware.
  - **A. Demo** with simulated nodes on Windows, Linux or macOS.
  - **B. 3D wiring viewer.**
  - **C. Build and flash the ESP32 firmware.**
  - **D. Raspberry Pi install:** Imager, SSH, `install.sh`, radio test, services.
  - **E. Connect** from a laptop or phone: finding the IP address, firewall, port forwarding.
  - **F. Tests.**
  - **G. Troubleshooting.**
  - **H. Command summary.**

---

## 4. `esp32-node/` — C++ firmware for the field nodes

The firmware uses the **Arduino framework** on **PlatformIO**. It is split into small modules. Each module has a header file in `include/` (its interface) and a source file in `src/` (its implementation). The module names follow the "ESP32 firmware" list in File 1, section 10.

Three of the modules use **no Arduino functions at all**: `packet_builder`, `data_filter` and `scheduler`. Because of that they can be compiled and unit-tested on a normal PC (see `test_host/`).

### `esp32-node/platformio.ini`

- **Purpose:** PlatformIO project file. It defines how to build and flash the firmware.
- **Contents:**
  - `[platformio] default_envs = node1, node2`: `pio run` builds both nodes.
  - `[env]` holds the settings shared by both nodes:
    - `platform = espressif32@6.9.0`, pinned so builds are reproducible (Arduino-ESP32 core 2.0.17);
    - `board = esp32doit-devkit-v1` and `framework = arduino`;
    - `monitor_speed = 115200`;
    - `build_flags = -Wall` to show all compiler warnings.
  - `lib_deps`: the external libraries, downloaded automatically:
    - `sandeepmistry/LoRa`: SX127x radio driver;
    - `adafruit/Adafruit BME280 Library` and `Adafruit Unified Sensor`;
    - `claws/BH1750`.
  - `[env:node1]` adds `-DNODE_ID=1`; `[env:node2]` adds `-DNODE_ID=2`.
- **Why the node ID is a build flag:** each board's ID is fixed at compile time. You cannot accidentally run two boards with the same ID unless you flash the same environment twice.
- **When to edit it:** to add a third node (`[env:node3]` with `-DNODE_ID=3`), add libraries, or change the board type.

### `esp32-node/include/board_config.h`

- **Purpose:** The **single place** for all hardware and radio settings of a field node.
- **Contents (three namespaces):**
  - `board::`
    - LoRa SPI pins (`PIN_LORA_SCK = 18`, `MISO = 19`, `MOSI = 23`, `NSS = 5`, `RESET = 14`, `DIO0 = 26`);
    - I2C pins (`SDA = 21`, `SCL = 22`) and the I2C clock (100 kHz);
    - sensor addresses (`BME280_I2C_ADDR = 0x76`, `BH1750_I2C_ADDR = 0x23`);
    - analog pins (`PIN_MQ135 = 34`, `PIN_SOUND = 35`, `PIN_SUPPLY = 32`);
    - supply-monitor settings (`SUPPLY_MONITOR_ENABLED`, divider ratio 2.0, low-voltage threshold 4600 mV).
  - `radio::` — frequency 433 MHz, bandwidth 125 kHz, SF7, CR 4/5, preamble 8, sync word 0x12, TX power 10 dBm.
  - `timing::`
    - send period 60 s and maximum jitter 2 s;
    - MQ-135 warm-up 180 s;
    - sound window 1000 ms, sampled every 500 µs (2 kHz);
    - 32 ADC samples per reading;
    - watchdog 30 s;
    - retry missing sensors every 30 s.
- **Why the addresses are named `…_I2C_ADDR`:** the Adafruit library already defines a macro called `BME280_ADDRESS`, which would clash with a constant of the same name.
- **When to edit it:**
  - change the BME280 address to 0x77 if SDO is tied to 3.3 V;
  - disable the supply monitor if it is not fitted;
  - change SF or TX power for range tests. The radio values must match `raspberry-pi/config/config.toml`.

### `esp32-node/include/node_identity.h`

- **Purpose:** Turns the `NODE_ID` build flag into usable constants and checks it.
- **Contents:**
  - `#error` if `NODE_ID` is missing, so you can't build a node without an ID.
  - `static_assert` that `NODE_ID` is between 1 and 254.
  - `identity::NODE`: the node ID as a `uint8_t`.
  - `identity::FIRMWARE_VERSION = "1.0.0"`.
  - `identity::SLOT_OFFSET_MS = (10000 + (NODE_ID-1) × 30000) % 60000`. This gives Node 1 = 10 s and Node 2 = 40 s, so the two nodes transmit 30 s apart.
- **When to edit it:** to bump the firmware version, or to change the slot formula for more nodes.

### `esp32-node/include/packet_builder.h` and `src/packet_builder.cpp`

- **Purpose:** Build the 33-byte binary packet defined in `docs/packet_protocol.md`. This is the "packet_builder" module from File 1.
- **Contents of the header:**
  - Constants: `MAGIC = 0x4C`, `PROTOCOL_VERSION = 1`, `PACKET_SIZE = 33`, and the invalid sentinels (`INVALID_I16`, `INVALID_U16`, `INVALID_U32`).
  - `enum StatusFlag`: bit masks such as `FLAG_BME280_ERROR`, `FLAG_MQ135_WARMUP`, `FLAG_BOOT`.
  - `struct Fields`: all values in real units (°C, %, hPa, lux, mV, …).
  - `crc16Ccitt()` and `encode()`.
- **How `encode()` works:**
  1. Writes magic, version and node ID.
  2. Writes sequence and uptime as 4-byte little-endian numbers (`putU32`).
  3. Scales the floats to integers. For example, temperature 25.47 °C becomes 2547. `scaleI16`, `scaleU16` and `scaleU32` round the value and **replace NaN, negative or too-large values with the invalid sentinel**.
  4. Copies the raw ADC values, supply voltage and flags.
  5. Computes the CRC-16 over bytes 0–30 and appends it at bytes 31–32.
  6. Returns 33, or 0 if the output buffer is too small.
- **Why integers instead of floats:** they are smaller, have the same byte layout on every CPU, and are easy to decode in Python with `struct`.
- **Related files:** `raspberry-pi/app/protocol.py` (the decoder) and `test_host/test_main.cpp`.

### `esp32-node/include/data_filter.h` and `src/data_filter.cpp`

- **Purpose:** Hardware-independent filtering and validation. This is the "data_filter" module from File 1.
- **Contents:**
  - **Range limits** taken from the sensor datasheets:
    - temperature −40…85 °C;
    - humidity 0…100 %;
    - pressure 300…1100 hPa;
    - light 0…120 000 lux;
    - ADC maximum 4095, with saturation treated as ≥ 4080.
  - **`inRange(value, min, max)`:** false for NaN or out-of-range values.
  - **`trimmedMean(samples, n)`:**
    - sorts the samples (insertion sort, which is fast for 32 values);
    - throws away the lowest 25 % and the highest 25 %;
    - averages the middle half.

    This removes ADC spikes and noise far better than a plain average. Example: `{100, 4095, 102, 98, 0, 101, 99, 100}` gives 100.
  - **`computeSoundStats(samples, n)`** returns three values:
    - `average_deviation`: the mean of |sample − mean|. This is the "loudness" and is sent as `sound_avg`.
    - `peak_to_peak`: max − min in the window, sent as `sound_peak`.
    - `maximum`: used to detect ADC saturation.
- **Why use the average deviation for sound:** analog sound modules output a waveform centred on a DC level. Its average value stays almost the same whether the room is loud or quiet, but the deviation from that level grows with loudness.

### `esp32-node/include/scheduler.h` and `src/scheduler.cpp`

- **Purpose:** Decides **when** to transmit. This is the "scheduler" module from File 1.
- **Contents:** `class Scheduler` with `start()`, `isDue()`, `advance()`, `msUntilDue()` and `nextDueMs()`.
- **How it works:**
  - `start(now, random)` sets the first slot to `now + slot_offset` and the actual send time to `slot + jitter` (0–2000 ms).
  - Slots lie on a **fixed grid** (`slot_base += 60000` each time). Jitter is added to the send time only and never moves the grid. This keeps jitter from piling up as drift.
  - `advance()` moves to the next slot. If the program was blocked for longer than a period, it skips the missed slots and returns how many it skipped. `main.cpp` adds that count to the sequence number so the Pi counts them as lost.
  - Every time comparison uses `int32_t(now − due) >= 0`. This stays correct when `millis()` wraps around after 49.7 days.
- **Why random jitter:** if both nodes ever drift into the same slot, the random delay makes it unlikely that they collide again on the next packet.

### `esp32-node/include/sensor_manager.h` and `src/sensor_manager.cpp`

- **Purpose:** Reads every sensor and fills in a `SensorSnapshot`. This is the "sensor_manager" module from File 1.
- **Contents:**
  - `struct SensorSnapshot`: temperature, humidity, pressure, lux, MQ-135 raw value, sound average and peak, supply voltage (mV) and flags.
  - `class SensorManager`:
    - `begin()`: starts I2C and configures the ADC.
    - `read(uptime)`: reads everything.
    - private helpers, one per sensor.
- **How it works:**
  - **`begin()`:**
    - starts I2C on GPIO21/22 at 100 kHz;
    - sets the ADC to 12 bits;
    - sets 11 dB attenuation on GPIO34, 35 and 32, which gives a measuring range of about 0–3.1 V;
    - initialises the BME280 and BH1750.
  - **BME280:**
    - uses **forced mode**: one measurement on demand, then the sensor sleeps. This keeps the sensor from heating itself and skewing the temperature reading.
    - Before each read it checks the device still answers on I2C.
    - If the device is missing it sets `FLAG_BME280_ERROR`. If a value is outside the datasheet range it sets `FLAG_BME280_OUT_OF_RANGE`.
  - **BH1750:**
    - runs in continuous high-resolution mode;
    - `readLightLevel()` returns a negative number on error, which sets `FLAG_BH1750_ERROR`.
  - **MQ-135:**
    - takes 32 samples 200 µs apart and keeps the trimmed mean;
    - sets the warm-up flag if uptime is under 180 s;
    - sets the saturation flag if the value is ≥ 4080.
  - **Sound:**
    - samples GPIO35 every 500 µs for 1 s (about 2000 samples, held in a member buffer);
    - computes the stats with `computeSoundStats`;
    - sets the saturation flag if needed.
  - **Supply voltage:**
    - takes 32 `analogReadMilliVolts()` samples (which use the ESP32's factory calibration);
    - computes the trimmed mean and multiplies by 2 (the divider ratio);
    - sets the low-supply flag below 4600 mV.
  - **Automatic retry:** if a sensor was missing, `retryMissingSensors()` tries to initialise it again every 30 s. You can plug a sensor back in without rebooting.

### `esp32-node/include/lora_radio.h` and `src/lora_radio.cpp`

- **Purpose:** Wraps the LoRa library to configure the SX1278 and send packets. This is the "lora_radio" module from File 1.
- **Contents:** `class LoraRadio` with `begin()`, `ready()`, `send(data, len)` and `lastAirtimeMs()`.
- **How it works:**
  - **`begin()`:**
    - starts the SPI bus on the configured pins and tells the library which NSS, RESET and DIO0 pins to use;
    - calls `LoRa.begin(433E6)`, which resets the chip and checks the version register (`0x12`). It returns false if the module is missing or badly wired.
    - applies bandwidth, spreading factor, coding rate, preamble, sync word, CRC and TX power;
    - puts the radio to sleep.
  - **`send()`:**
    - wakes the radio (`idle`) and starts an explicit-header packet;
    - writes the bytes and calls the blocking `endPacket()`;
    - measures the airtime, puts the radio back to sleep, and returns success or failure.
  - If the radio hangs inside `endPacket()`, the **task watchdog** in `main.cpp` resets the ESP32 after 30 s.
- **Why the radio sleeps between packets:** it saves power, and the node only transmits once a minute.

### `esp32-node/include/diagnostics.h` and `src/diagnostics.cpp`

- **Purpose:** Readable serial output for testing and for the demonstration. This is the "diagnostics" module from File 1.
- **Contents:**
  - `begin()`: starts Serial at 115200 baud.
  - `printBanner()`: firmware version, node ID, slot timing and radio settings.
  - `printInitResult("BME280", ok)`: prints `[init] BME280 OK` or `[init] BME280 FAILED`.
  - `printReading(seq, snapshot)`: one line with every value (`--` if invalid) and the flags in hex. It also prints a human-readable line for each problem, such as `! BME280 not responding` or `- MQ-135 warming up`.
  - `printTxResult(...)`: `SENT` or `FAILED`, byte count, airtime in ms, and the **full packet in hex**. You can paste that hex into `tools/decode_packet.py`.
  - `printSkippedSlots(n)`.
- **Example output:**
  ```
  [seq 12] T=27.41C RH=58.2% P=1008.6hPa L=312.5lx MQ135=1187 SndAvg=95 SndPk=640 Vs=5.02V flags=0x0000
  [tx  12] SENT, 33 bytes, 72 ms airtime | 4C01010C000000...
  ```

### `esp32-node/src/main.cpp`

- **Purpose:** The firmware's main program (`setup()` and `loop()`). It connects all the modules.
- **How it works:**
  - **`setup()`:**
    1. Starts the serial port and prints the banner.
    2. Starts the **task watchdog** (30 s, panic/reset when it expires).
    3. Calls `sensors.begin()` and prints the BME280 and BH1750 results.
    4. Calls `lora.begin()` and prints the LoRa result.
    5. Starts the scheduler with a random jitter from `esp_random()`, which uses the hardware random number generator.
  - **`loop()`**, every 20 ms:
    1. Feeds the watchdog.
    2. If the scheduler says a packet is due:
       - calls `transmitCycle()`;
       - advances the scheduler;
       - adds any skipped slots to the sequence number.
  - **`transmitCycle()`:**
    1. Computes uptime from `esp_timer_get_time()`, which is 64-bit and does not wrap after 49 days like `millis()`.
    2. Reads the sensors.
    3. If the radio failed earlier, tries `lora.begin()` again.
    4. Fills `packet::Fields`. It adds `FLAG_LAST_TX_FAILED` if the previous send failed, and `FLAG_BOOT` on the first packet (sequence 0).
    5. Prints the reading, encodes the packet, sends it and prints the result.
    6. Increments `sequence_number` **even if sending failed**, so the Pi can count the gap as a lost packet.
- **Automatic recovery (File 1, Feature 7):** after a power cut the ESP32 boots, runs `setup()` and starts sending again with no human action. The `BOOT` flag tells the Pi that the node restarted.

### `esp32-node/test_host/Makefile`

- **Purpose:** Build and run the firmware unit tests on a PC (Linux, macOS or WSL) with `g++`. No ESP32 is needed.
- **Contents:**
  - compiles `test_main.cpp` together with `packet_builder.cpp`, `data_filter.cpp` and `scheduler.cpp`;
  - uses `-std=c++17 -Wall -Wextra -Werror`, so any warning fails the build;
  - targets: `run` (the default: build then run), `run_tests` (build only) and `clean`.
- **Usage:** `make -C esp32-node/test_host`

### `esp32-node/test_host/test_main.cpp`

- **Purpose:** Unit tests for the hardware-independent firmware modules.
- **Contents:** a tiny `CHECK()` macro (no test framework needed) and these tests:

  | Test | What it checks |
  |---|---|
  | `testCrc` | The CRC of `"123456789"` is `0x29B1` (the standard check value). |
  | `testEncode` | Byte positions, negative temperature encoding, the CRC field, and that a too-small buffer returns 0. |
  | `testInvalidValues` | NaN and negative values become the invalid sentinels. |
  | `testTrimmedMean` | Spikes are rejected; empty and single-sample input are handled. |
  | `testSoundStats` | A flat signal gives 0; a square wave gives the expected deviation and peak-to-peak. |
  | `testInRange` | Valid, too-high and NaN values. |
  | `testScheduler` | Slot offset, jitter, fixed grid with no drift, skipped-slot count, `millis()` wrap-around. |

  - `--vector` mode prints a reference packet as hex. The Python test `test_matches_firmware_encoder` uses it to check that **C++ and Python agree byte for byte**.

---

## 5. `raspberry-pi/` — Python main-node application

The Pi software is one Python package, `app`, with two long-running programs:

1. **Receiver** (`python -m app.receiver`): radio → validation → database → alerts.
2. **Dashboard** (`python -m app.serve`): reads the database and serves the web pages.

They are separate processes, so a crash in the web server can never stop data collection. They share data only through the SQLite file, which uses WAL mode so one process can read while the other writes.

### 5.1 Top-level files

#### `raspberry-pi/requirements.txt`

- **Purpose:** Python packages needed in production.
- **Contents:** `flask` (web framework) and `waitress` (production web server).
- **Note:** the hardware libraries `spidev`, `gpiozero` and `lgpio` are installed with **apt**, not pip, because Raspberry Pi OS ships tested versions. The virtual environment is created with `--system-site-packages` so it can use them.

#### `raspberry-pi/requirements-dev.txt`

- **Purpose:** Extra packages for development and testing.
- **Contents:** everything in `requirements.txt`, plus `pytest`.

#### `raspberry-pi/pytest.ini`

- **Purpose:** pytest configuration.
- **Contents:** `testpaths = tests` (where to look for tests) and `addopts = -q` (quiet output).

### 5.2 `config/`

#### `raspberry-pi/config/config.toml`

- **Purpose:** The **only file you normally edit** on the Pi. It holds every setting of the main node. TOML is a simple, readable format.
- **Sections:**
  - **`[radio]`:**
    - LoRa settings (frequency, bandwidth, SF, coding rate, preamble, sync word, CRC), which **must equal** the values in `board_config.h`;
    - SPI bus and device (0, 0 → `/dev/spidev0.0`) and SPI speed;
    - `reset_pin = 25` and `dio0_pin = 24` (BCM numbers).
  - **`[database]`:**
    - `path` of the SQLite file;
    - `backup_dir` and `backup_keep` (how many backups to keep);
    - `retention_days` (0 means keep data forever).
  - **`[receiver]`:**
    - `offline_timeout_s = 180`: a node is offline after 3 minutes without a packet;
    - `health_interval_s` (heartbeat period), `log_file`, `log_level`.
  - **`[web]`:** `host`, `port = 5000`, `refresh_interval_s` (how often the pages update) and `log_file`.
  - **`[[nodes]]`** (one block per node): `node_id`, `name`, `location`, `enabled`. **Set real locations here.**
  - **`[alerts]`:** `consecutive_samples = 3`, the number of bad or good packets needed before an alert opens or closes.
  - **`[[alerts.rules]]`** (one block per threshold):
    - `type`, `metric` (which reading), `direction` (`high` or `low`);
    - `threshold` (opens the alert) and `clear` (closes it; the gap between them is the hysteresis);
    - `severity` (`info`, `warning` or `critical`) and `enabled`.
    - The included rules are high temperature, high humidity, low light, high MQ-135, high sound and low supply voltage.
- **Relative paths** such as `database/monitor.db` are resolved against the `raspberry-pi/` folder.
- **Override:** the environment variable `LORA_MONITOR_CONFIG=/path/to/other.toml` makes the programs use a different file. The demo uses this.
- **Changes take effect** after `sudo systemctl restart lora-receiver lora-dashboard`.

### 5.3 `app/` — Python package

#### `app/__init__.py`

- **Purpose:** Marks `app` as a Python package and holds the application version (`__version__ = "1.0.0"`), which the dashboard and logs show.

#### `app/config.py`

- **Purpose:** Loads `config.toml`, **checks it**, and turns it into typed Python objects. This is the "configuration loader" module from File 1.
- **Contents:**
  - **Frozen dataclasses**, one per section: `RadioConfig`, `DatabaseConfig`, `ReceiverConfig`, `WebConfig`, `NodeConfig`, `AlertRule`, `AlertConfig`, and `Config` for the whole file. "Frozen" means a value cannot change by accident while the program runs.
  - `load_config(path=None)`:
    - finds the file in this order: the argument, then `$LORA_MONITOR_CONFIG`, then `config/config.toml`;
    - parses it with Python's built-in `tomllib`;
    - resolves relative paths and builds the objects.
  - **Checks** (each one raises `ConfigError` with a clear message):
    - unknown keys, which catches typos such as `spreading_factr`;
    - bandwidth must be one of the 10 values the SX1278 supports;
    - SF between 7 and 12, coding rate between 5 and 8;
    - frequency within 410–525 MHz (the SX1278 band);
    - duplicate node IDs, and at least one node;
    - alert metric names and directions;
    - **hysteresis** in the right direction (for a high alert, `clear` must be ≤ `threshold`);
    - offline timeout ≥ 30 s.
- **Why so many checks:** a typo in the config should stop the program at startup with a clear message. Otherwise it could quietly receive nothing for days.

#### `app/protocol.py`

- **Purpose:** The Python side of the packet format. It **decodes** packets from the nodes and can **encode** them for the simulator and tests. Part of the "packet parser and validator" module from File 1.
- **Contents:**
  - The same constants as the C++ side (`MAGIC`, `PROTOCOL_VERSION`, `PACKET_SIZE`, the invalid sentinels).
  - A `struct.Struct("<BBBIIhHHIHHHHH")` describing the 31 data bytes. An `assert` checks that the layout plus the CRC is 33 bytes.
  - Flag constants and `FLAG_NAMES`, which turns flag bits into text such as "MQ-135 warm-up".
  - `ProtocolError(reason, message)`. Its `reason` is a short code (`bad_length`, `bad_magic`, `bad_version`, `bad_crc`) that gets stored in the database.
  - `Packet`: a frozen dataclass holding the decoded values in real units, with `None` for invalid ones.
  - `crc16_ccitt(data)`: the same algorithm as the C++ code.
  - `decode(data)` checks, in order:
    1. the length is 33;
    2. the magic byte is right;
    3. the version is supported;
    4. the CRC matches.

    Only then does it unpack the fields, turn sentinels into `None`, and divide the scaled values back to real units (2547 → 25.47 °C).
  - `encode(packet)`: the exact reverse.
  - `flag_names(flags)`: a list of readable flag names.

#### `app/validator.py`

- **Purpose:** A second range check on the Pi. It protects the database even if a node has a firmware bug or a faulty sensor.
- **Contents:**
  - `RANGES`: the allowed range for each field (the same datasheet limits as the firmware, plus 0–6 V for the supply).
  - `validate_ranges(packet)`:
    - returns a copy of the packet in which any out-of-range value is replaced by `None`;
    - sets flag bit 15 (`FLAG_PI_RANGE_REJECTED`);
    - returns the list of fields it rejected.

    The other, valid values in the same packet are still stored.

#### `app/sequence.py`

- **Purpose:** Uses sequence numbers to detect **duplicates, packet loss and node reboots**. This is the "duplicate/sequence detector" module from File 1 and covers Feature 6.
- **Contents:**
  - `SequenceStatus`: `FIRST`, `OK`, `GAP`, `DUPLICATE` or `NODE_RESET`.
  - `SequenceResult(status, lost)`.
  - `NodeSequenceState(last_sequence, last_uptime)`: one per node.
  - `classify(state, seq, uptime, flags)` applies these rules in order:
    1. No previous packet → `FIRST`, lost = 0.
    2. Same sequence number and uptime within 5 s → `DUPLICATE`, which is rejected.
    3. The node rebooted if **any** of these is true:
       - the `BOOT` flag is set;
       - uptime went backwards;
       - the sequence number did not increase;
       - the gap is impossibly large (more than 10 000).

       Result: `NODE_RESET`. After a reboot the node counts from 0, so `lost = seq`, the packets sent since the reboot that never arrived.
    4. Otherwise `gap = seq − last − 1`. If the gap is above 0 the result is `GAP`, with `lost = gap`; if it is 0 the result is `OK`.
  - `accept(state, seq, uptime)` updates the state. It is called **only after** the packet has been stored.
- **Packet loss %** shown on the dashboard is `lost / (received + lost)`.

#### `app/database.py`

- **Purpose:** All SQLite access. Every SQL statement uses `?` parameters, so values are never pasted into SQL text and SQL injection is impossible. This is the "SQLite database layer" module from File 1.
- **Contents:**
  - **`SCHEMA`:** creates the tables if they don't exist.

    | Table | Contents |
    |---|---|
    | `nodes` | ID, name, location, enabled, `last_seen`, last sequence and uptime, last RSSI/SNR, and the counters `packets_received`, `packets_lost`, `duplicates` and `reboots` |
    | `readings` | One row per stored packet: every sensor value, RSSI, SNR, flags, `lost_before` |
    | `alerts` | `created_at`, `cleared_at`, type, measured value, threshold, severity, message, acknowledged |
    | `system_events` | Receiver start/stop, radio errors, node resets, alerts opened/cleared, backups, retention |
    | `rejected_packets` | Every invalid packet, with the reason and raw hex (Phase 7: "invalid packets logged separately") |
    | `system_status` | Key/value pairs: receiver heartbeat, radio OK, packet counters |

  - **Indexes:**
    - `(node_id, received_at)` and `received_at`, so history and CSV queries stay fast;
    - a **partial unique index** on alerts `(node_id, alert_type) WHERE cleared_at IS NULL`, which lets the database itself guarantee there is never more than one active alert of the same type per node.
  - **Time helpers:** `utc_now()`, `to_iso()` (always `YYYY-MM-DDTHH:MM:SSZ` in UTC, which sorts correctly as text) and `parse_iso()`. The browser converts times to local time for display.
  - **`class Database`:**
    - **Connecting:** opens the file, turns on foreign keys, a 15 s busy timeout, **WAL journal mode** (the receiver writes while the dashboard reads) and `synchronous=NORMAL` (safe with WAL, and faster on an SD card).
    - **Setup:** `init_schema()` and `sync_nodes(nodes)`, which inserts or updates node names and locations from the config.
    - **Nodes:** `get_nodes()`, `get_node()` and `load_sequence_states()`. The last of these lets sequence tracking **continue after a Pi restart**.
    - **Readings:**
      - `store_reading(...)` inserts the reading **and** updates the node counters in **one transaction**, so the two can never get out of step;
      - `record_duplicate()`, `latest_reading()`, `recent_readings()`;
      - `history(node, start, end, max_points)` splits the time range into at most about 500 buckets and averages each one in SQL. A 30-day chart therefore loads about 500 points instead of 43 000;
      - `iter_readings()` streams rows for the CSV export;
      - `reading_count()` and `purge_older_than(days)`, which removes old readings, events, rejected packets and cleared alerts.
    - **Rejected packets, events and status:** `insert_rejected()`, `recent_rejected()`, `rejected_count()`, `log_event()`, `recent_events()`, `set_status()` and `get_status()`.
    - **Alerts:** `open_alert()` (returns `None` if the unique index blocks a duplicate), `clear_alert()`, `acknowledge_alert()`, `active_alerts()` and `cleared_alerts()`.
    - **Maintenance:** `backup_to(path)` uses SQLite's online backup API, which makes a consistent copy even while the receiver is writing. `integrity_ok()` runs `PRAGMA quick_check`.

#### `app/alerts.py`

- **Purpose:** The alert engine. It implements File 1, section 9: no alert from one noisy sample, consecutive samples required, hysteresis, created and cleared events stored, and offline detection.
- **Contents:**
  - `NODE_OFFLINE = "node_offline"`.
  - `SENSOR_FAILURES` maps `sensor_failure_bme280` and `sensor_failure_bh1750` to the flag bits that trigger them.
  - `class AlertEngine`:
    - `__init__` keeps only the enabled rules and **reloads active alerts from the database**, so a restart doesn't open the same alerts again.
    - `evaluate(packet, when)`, called for each stored reading:
      1. If the node was marked offline, the alert clears at once because a packet arrived.
      2. For each threshold rule:
         - skips missing values;
         - skips MQ-135 values during warm-up;
         - otherwise passes the value to `_rule_sample`.
      3. For each sensor-failure type, checks the flags.
    - `check_offline(nodes, now)`, called every 10 s by the receiver:
      - for each enabled node, measures the time since `last_seen`; if the node was never seen, it uses the time since the receiver started;
      - if that is longer than the timeout, opens `node_offline`;
      - for a disabled node, clears any offline alert.
    - `_update()` holds the **state machine**, with a counter per (node, alert type):
      - **No active alert:**
        - a violating sample adds 1 to `bad`; any other sample resets `bad` to 0;
        - when `bad` reaches `consecutive_samples`, the alert **opens**.
      - **Alert active:**
        - a "recovered" sample (past the `clear` level) adds 1 to `good`; any other sample resets `good` to 0;
        - when `good` reaches `consecutive_samples`, the alert **clears**.
      - **Hysteresis example** (threshold 40, clear 38): a reading of 39 neither opens nor clears an alert. This stops an alert from flickering on and off when the value hovers around 40.
    - `_open()` and `_clear()` write to the `alerts` table, add an `alert_opened` or `alert_cleared` system event, and write to the log.

#### `app/processor.py`

- **Purpose:** The **packet pipeline**. It is the single function every received packet goes through.
- **Contents:**
  - `ProcessResult`: whether the packet was accepted, the reason, node, sequence, lost count and reading ID.
  - `class PacketProcessor`:
    - `__init__` loads the sequence states from the database and starts counters (received, stored, rejected, duplicates).
    - `handle(raw, rssi, snr, crc_error, received_at)` runs these steps:
      1. If the radio reported a CRC error → reject as `radio_crc_error`.
      2. `decode()` → reject as `bad_length`, `bad_magic`, `bad_version` or `bad_crc`.
      3. Look up the node in the database → reject as `unknown_node` or `node_disabled`.
      4. Run the sequence check → reject as `duplicate` (and increase the node's duplicate counter).
      5. Run the range check (bad fields become `None`).
      6. **Store** the reading and update the node statistics.
      7. Update the sequence state. On a node reset, add a `node_reset` system event.
      8. Write one log line with all values.
      9. Pass the packet to the alert engine.
    - `_reject()` stores the reason, raw hex, RSSI and SNR in `rejected_packets` and logs a warning.
- **Why this is separate from the radio code:** the same `handle()` is used with the real SX1278, with the simulator and in the tests. All the logic can therefore be tested without hardware.

#### `app/sx1278.py`

- **Purpose:** The **LoRa radio driver for the Raspberry Pi**. It talks to the SX1278 registers over SPI. This is the "LoRa receiver" module from File 1.
- **Contents:**
  - **Constants:**
    - SX1278 register addresses (`REG_FIFO`, `REG_OP_MODE`, `REG_FRF_*`, `REG_IRQ_FLAGS`, `REG_MODEM_CONFIG_1/2/3`, `REG_SYNC_WORD`, …);
    - operating modes (sleep, standby, RX continuous) and IRQ bits;
    - `BANDWIDTH_CODES`, which maps Hz to the register code.
  - `RadioError` and `RadioPacket(payload, rssi_dbm, snr_db, crc_error)`.
  - **Helper functions:**
    - `frf_register(freq)`: the frequency register value, `freq × 2¹⁹ / 32 MHz`.
    - `low_data_rate_optimize(sf, bw)`: true when one symbol lasts longer than 16 ms. This is the same rule the Arduino library uses on the nodes.
    - `packet_rssi(raw, snr, freq)`: the datasheet formula. The offset is −164 for the 433 MHz band, with a correction when SNR is below 0.
    - `to_signed8()`.
  - **`class SX1278`:**
    - **Register access:**
      - `_read` and `_write` do one SPI transfer each; bit 7 of the address means "write";
      - `_read_burst` reads the FIFO.
    - **`open()`:**
      1. Opens `/dev/spidev0.0` (5 MHz, mode 0) and creates the gpiozero devices for RESET (output) and DIO0 (input).
      2. Pulses RESET.
      3. Reads the version register and **raises an error with troubleshooting hints if it is not `0x12`**.
      4. Calls `configure()`.

      The SPI and GPIO objects are created only once, so a retry does not raise "pin already in use".
    - **`configure()`:**
      1. Enters sleep mode (needed to switch the chip into LoRa mode).
      2. Sets the frequency and the FIFO base addresses, and turns on LNA boost.
      3. Sets ModemConfig1 (bandwidth, coding rate, explicit header), ModemConfig2 (SF, CRC on) and ModemConfig3 (automatic gain control, plus low-data-rate optimisation if needed).
      4. Sets detection optimise and threshold for SF7–12, the preamble length and the sync word.
      5. Maps DIO0 to "RX done", clears the IRQ flags and enters **RX continuous** mode.
    - **`receive(timeout)`:**
      1. Waits for DIO0 to go high; if DIO0 is not wired, it polls the IRQ register instead.
      2. Reads and clears the IRQ flags.
      3. Treats the packet as bad if the payload CRC flag is set, **or if the received packet had no CRC at all** (a sender that is configured wrongly).
      4. Reads the byte count and current FIFO address, then reads the payload.
      5. Calculates SNR (raw value / 4) and RSSI.
      6. Returns a `RadioPacket`.

      If nothing arrived, it checks the chip is still in RX mode (`_ensure_rx_mode`) and puts it back if not.
    - **`health_check()`** re-reads the version register; the receiver calls it every minute.
    - **`close()`** puts the radio to sleep and releases SPI and GPIO.
- **Why a custom driver:** most Python LoRa libraries for the Pi are unmaintained or need extra C libraries. About 200 lines of register code with no dependencies is easier to understand, to test (see `test_sx1278.py`) and to explain in a viva.

#### `app/simulator.py`

- **Purpose:** A **fake radio** that behaves like the real one. Use it for demonstrations, to develop the dashboard on a laptop, and for testing, all without hardware.
- **Contents:** `class SimulatedRadio`, with the same methods as `SX1278` (`open`, `receive`, `health_check`, `describe`, `close`).
- **How it works:**
  - Each simulated node has a due time based on the same slot offsets (Node 1 at +10, Node 2 at +40, scaled by `period_s`) and a sequence counter.
  - `receive()` builds a realistic `Packet` and encodes it with the **real** `protocol.encode()`:
    - temperature follows a daily sine wave, with Node 2 1 °C warmer;
    - humidity moves opposite to temperature;
    - light is 0 at night;
    - MQ-135, sound and supply values have random noise.

    So the whole pipeline (decode, CRC, sequence, database, alerts) runs exactly as it would with real hardware.
  - About 3 % of packets are dropped (to show packet-loss tracking) and about 1 % are marked as CRC errors (to show rejected-packet logging).
  - Node 2 gets weaker RSSI and SNR, as if it were further away.
- **Usage:** `python -m app.receiver --simulate --sim-period 5`

#### `app/receiver.py`

- **Purpose:** The **receiver service**: the long-running program that systemd starts as `lora-receiver.service`.
- **Contents:**
  - `class Receiver`:
    - creates the `AlertEngine` and `PacketProcessor`;
    - `_open_radio()` initialises the radio, logs `radio_ready` or `radio_error`, and never crashes the program.
    - `heartbeat()` writes to `system_status`:
      - the receiver version, start time and heartbeat time;
      - whether the radio is OK, and the radio settings;
      - packet counters and the Pi's CPU temperature.

      The dashboard uses this to show "Receiver Running / Stopped".
    - `periodic()`:
      - **every 10 s:** offline check;
      - **every `health_interval_s`:** radio health check and heartbeat;
      - **once a day:** retention purge, if enabled;
      - **every 30 s while the radio is broken:** try to initialise it again.
    - `run()`, the main loop:
      1. Logs `receiver_started`.
      2. Opens the radio.
      3. Repeatedly: `radio.receive(1 s)`, then `processor.handle()`, then `periodic()`. An SPI read error marks the radio as failed instead of crashing.
      4. On stop: clears the heartbeat, logs `receiver_stopped`, closes the radio.
  - `main()`:
    - parses `--config`, `--simulate` and `--sim-period`;
    - loads the config and sets up logging;
    - opens the database, creates the schema and syncs the nodes;
    - chooses the real `SX1278` or the `SimulatedRadio`;
    - installs **SIGTERM and SIGINT handlers**, so `systemctl stop` and Ctrl+C shut down cleanly.
- **Why it doesn't depend on the network:** the receiver only needs the SD card. Wi-Fi or Ethernet outages don't affect data collection (Phase 11, item 8).

#### `app/web.py`

- **Purpose:** The **Flask dashboard and JSON API**. This is the "Flask API and dashboard" module from File 1.
- **Contents:**
  - `METRIC_LABELS`: the display name and unit for each chart.
  - `node_summary(db, node, timeout, now)`: one node's latest reading, online/offline state, age of the last packet, packet-loss %, active alert count and readable flag names.
  - `receiver_status(db, config, now)`: reads `system_status`. The receiver counts as "running" if the heartbeat is no older than 3 × `health_interval_s`.
  - `create_app(config)`, the Flask application factory:
    - creates the schema and nodes, so the dashboard can start before the receiver;
    - opens **one database connection per request** (stored in Flask's `g`) and closes it at the end of the request.
    - **Pages:**
      - `GET /`: Overview.
      - `GET /node/<id>`: one node's page.
      - `GET /alerts`: active and cleared alerts.
      - `POST /alerts/<id>/ack`: marks an alert as acknowledged.
      - `GET /maintenance`:
        - database file, size, reading count, rejected count;
        - backup history;
        - receiver and radio status;
        - CPU temperature, load, uptime, free disk space, versions;
        - node counters, recent system events and rejected packets.
    - **JSON API:**
      - `/api/overview`: everything the Overview page needs.
      - `/api/nodes/<id>`: node summary, the 15 most recent readings and active alerts.
      - `/api/nodes/<id>/history?hours=&points=`: downsampled history, limited to at most 31 days and 2000 points.
      - `/api/alerts`.
      - `/healthz`: runs a database integrity check and returns 200 or 503, for monitoring.
    - **`/export.csv?node_id=&start=&end=`:**
      - checks the inputs (400 error for a bad node ID, bad date or start after end);
      - **streams** the CSV, so even a very large export uses little memory;
      - uses its own database connection, because the response continues after the request context ends.
  - `main()`: the Flask development server (`python -m app.web`).
- **Security note:** there is no login. Use the dashboard only on the local network.

#### `app/serve.py`

- **Purpose:** **Production** start-up of the dashboard using **waitress**, a stable multi-threaded WSGI server. This meets Phase 9's requirement to use a production WSGI server.
- **How it works:** loads the config, sets up logging to `dashboard.log`, and calls `waitress.serve(create_app(config), host, port, threads=4)`.
- **Used by:** `systemd/lora-dashboard.service` (`python -m app.serve`).

#### `app/exporter.py`

- **Purpose:** CSV export. This is the "CSV exporter" module from File 1 and covers Feature 8.
- **Contents:**
  - `CSV_COLUMNS`: every reading column plus `status_text` (the flags as words, for example "MQ-135 warm-up; Node boot").
  - `iter_csv(db, node_id, start, end)`: a generator that writes the header, then the rows in batches of 500, yielding text pieces as it goes.
  - `export_filename(...)`: builds names like `readings_node1_20261030-0000_20261030-2359.csv`.

#### `app/health.py`

- **Purpose:** Main-node health information for the Maintenance page and the heartbeat. Part of the "logging and health monitor" module from File 1.
- **Contents:**
  - `cpu_temperature_c()` reads `/sys/class/thermal/thermal_zone0/temp`.
  - `disk_usage(path)`: total and free GB, and used %.
  - `system_uptime_s()` reads `/proc/uptime`.
  - `load_average()`: the 1-minute load.
  - `file_size_mb(path)`: database size including its `-wal` and `-shm` files.
- Each function returns `None` instead of raising an error when the information isn't available, for example on a non-Pi PC.

#### `app/logging_setup.py`

- **Purpose:** One logging set-up shared by the receiver and the dashboard.
- **How it works:**
  - logs to **stderr**, which systemd sends to **journald** (`journalctl -u lora-receiver`);
  - also logs to a **rotating file**: at most 2 MB × 5 files, so the SD card can never fill up with logs;
  - if the log folder isn't writable, it prints a warning and keeps running with console logging only.

### 5.4 `app/templates/` — HTML pages

These are Jinja2 templates rendered by Flask. Live values are filled in by JavaScript that calls the JSON API every `refresh_interval_s`, so the page never needs a full reload.

#### `templates/base.html`

- **Purpose:** The shared layout every page extends.
- **Contents:**
  - `<head>` with the stylesheet;
  - the dark top bar with the title and navigation (Overview, one link per configured node, Alerts, Maintenance); the current page is highlighted;
  - `<main>` holds each page's content (`{% block content %}`);
  - the footer shows the version and the disclaimer that MQ-135 and sound values are indicative, not certified;
  - loads `app.js`, then the page's own script (`{% block scripts %}`);
  - `data-refresh` on `<body>` passes the refresh interval to JavaScript.

#### `templates/overview.html`

- **Purpose:** The **Overview page** (File 1, section 8, "Overview page").
- **Contents:**
  - **Four status cards:**
    - Main node receiver (Running/Stopped, heartbeat age, version);
    - LoRa radio (OK / Not ready, settings);
    - Database (OK, size);
    - Active alerts (count; links to the Alerts page).
  - **One card per field node:**
    - name, location and an online/offline/disabled badge;
    - six current values;
    - last packet time and how long ago it was;
    - RSSI, SNR, loss % and alert count.

    Clicking a card opens that node's page.
- **Script:** `refreshOverview()` fetches `/api/overview`, updates the cards and rebuilds the node cards. It runs on load and then on a timer.

#### `templates/node.html`

- **Purpose:** The **node detail page** (File 1, section 8, "Node page").
- **Contents:**
  - Title with the online badge, node ID, location, and an "Export CSV" button.
  - **Current-value cards:** temperature, humidity, pressure, light, MQ-135, sound average/peak, supply.
  - **Status cards:**
    - last update;
    - signal (RSSI/SNR);
    - packets (received, lost and %, duplicates, node restarts);
    - sensor status (flag names or "All OK", and node uptime).
  - **History:** range buttons (1 h, 6 h, 24 h, 7 d, 30 d) and nine charts: temperature, humidity, pressure, light, MQ-135, sound, RSSI, SNR, supply.
  - **Active alerts** for this node.
  - **Recent packets** table: the last 15 packets with every value, lost count and flags in hex.
- **Script:**
  - `refreshNode()` calls `/api/nodes/<id>` on every refresh interval.
  - `refreshCharts()` calls `/history` at most once a minute, or when you click a range button or resize the window. It then draws each chart with `drawLineChart()`.

#### `templates/alerts.html`

- **Purpose:** The **Alerts page** (File 1, section 8, "Alerts page").
- **Contents:**
  - **Active alerts table:** since, node, type, severity badge, measured value, threshold, details, and an **Acknowledge** button. Acknowledged rows are faded.
  - **Cleared alerts table:** the last 200, with opened and cleared times.
- **Script:** `formatTimestamps()` converts UTC times to the browser's local time. The page reloads itself on the refresh interval.

#### `templates/maintenance.html`

- **Purpose:** The **Maintenance page** (File 1, section 8, "Maintenance page").
- **Contents:**
  - **CSV export form:**
    - node selector (all, or one node);
    - "From" and "To" local date/time pickers;
    - on submit, JavaScript converts the local times to UTC ISO in hidden fields. Empty dates mean "export everything".
  - **Database card:** file path, size, readings stored, rejected packets, backup folder, last 5 backups (red warning if none).
  - **Main node card:** receiver and radio status, radio settings, start time, packet counters, CPU temperature, load, system uptime, free disk, application and Python versions.
  - **Nodes table:** ID, name, location, enabled, received, lost, duplicates, restarts.
  - **System events** (last 30) and **rejected packets** (last 20, with reason and raw hex).

### 5.5 `app/static/` — CSS and JavaScript

#### `static/style.css`

- **Purpose:** All the dashboard styling. There are no external frameworks, so it works **without internet**.
- **Contents:**
  - CSS variables for colours: `--accent` blue, `--good` green, `--bad` red, `--warn` amber, `--grid` for chart grid lines, and so on;
  - the top bar and navigation;
  - responsive card grids (status, node, metric, chart and two-column), which become a single column on phones (under 520 px wide);
  - cards, labels, large values and units;
  - online/offline badges (`.pill`) and severity badges (`.sev.info`, `.warning`, `.critical`);
  - buttons and range buttons;
  - tables, including key/value tables and faded acknowledged rows;
  - form fields.

#### `static/app.js`

- **Purpose:** JavaScript shared by all pages, including a **small chart drawer** written from scratch. No CDN or chart library is used, so the dashboard works on a campus LAN without internet.
- **Contents:**
  - `refreshMs()` reads the refresh interval from `<body data-refresh>`.
  - `fetchJSON(url)`: `fetch` with caching disabled; throws on an HTTP error.
  - `esc()`: HTML-escapes text before inserting it (protects against injection through node names).
  - `fmt()`, `fmtTime()` and `fmtAge()` format numbers, local times and durations (for example "3 min 12 s").
  - `setText()`, `setState()` (green or red value), `metric()` (HTML for one metric) and `formatTimestamps()`.
  - **`drawLineChart(canvas, points, key, unit, hours)`:**
    1. Sizes the canvas for the screen's pixel density so the chart stays sharp.
    2. Filters out missing values, converts timestamps, and computes the min/max with an 8 % margin.
    3. Draws five horizontal grid lines with y-labels. The number of decimals depends on the step size, so a small range never shows repeated labels like 29.5, 29.5, 29.5.
    4. Draws five time labels: hh:mm for ranges up to 48 h, otherwise the date. The first label is left-aligned and the last right-aligned so they aren't cut off.
    5. Draws the data line, **breaking it where there is a gap** (for example while a node was offline) instead of drawing a misleading straight line.
    6. Draws dots when there are fewer than 60 points.
    7. Writes the "latest value" label.

### 5.6 `scripts/`

#### `scripts/install.sh`

- **Purpose:** **One-command installation** on the Raspberry Pi (Phase 11).
- **What it does, in order:**
  1. Checks it is running as root.
  2. Installs the apt packages: Python, venv, `python3-spidev`, `python3-gpiozero`, `python3-lgpio`, `sqlite3`, `rsync`, `git`.
  3. Checks for Python 3.11 or newer (Bookworm).
  4. **Enables SPI** with `raspi-config nonint do_spi 0`.
  5. Creates the system user **`loramon`** (no login shell) and adds it to the `spi` and `gpio` groups. The services never run as root.
  6. Copies the app to `/opt/lora-campus-monitor/raspberry-pi` with `rsync`. It **keeps** any existing `config.toml`, database and logs, so re-running the script updates the code safely.
  7. Creates `database/backups/` and `logs/`.
  8. Creates the virtual environment (`--system-site-packages`) and installs `requirements.txt`.
  9. Gives ownership of everything to `loramon`.
  10. Initialises the database (`init_db.py`).
  11. Installs the systemd units, enables them and starts them.
  12. Prints the dashboard URL and useful commands.

#### `scripts/init_db.py`

- **Purpose:** Creates the database schema and node rows, then prints a summary: each node with its reading count, and the result of an integrity check.
- **When to use it:** first install (`install.sh` calls it), and after editing node names or locations in the config to check them.

#### `scripts/backup_db.py`

- **Purpose:** Database **backup and restore** (Feature 8, Phase 8 item 7).
- **Modes:**
  - **No arguments:**
    - makes a consistent online backup to `backup_dir/monitor-YYYYmmdd-HHMMSS.db` (safe while the receiver is running);
    - checks the integrity of the copy;
    - logs a `backup` system event, which the Maintenance page shows;
    - deletes old backups, keeping the newest `backup_keep`.
  - **`--dest /media/usb`:** backs up to another folder, such as a USB drive. `--keep N` overrides how many backups to keep.
  - **`--restore FILE`:**
    1. Checks the backup's integrity.
    2. **Saves the current database first** as `monitor-before-restore-<time>.db`.
    3. Removes the old WAL/SHM files and copies the backup into place.

    Stop both services before restoring.
- **Run automatically** every day at 02:30 by `lora-backup.timer`.

#### `scripts/radio_test.py`

- **Purpose:** **Bench test of the Pi's LoRa module** (Phase 6) without touching the database.
- **How it works:**
  - opens the SX1278 with the config settings and prints its version and settings;
  - then prints one line for every packet: time, size, RSSI, SNR, and either the decoded values or the reason it is invalid (CRC error, wrong magic, …).
  - Stop it with Ctrl+C. Stop `lora-receiver` first, because only one program can use the radio at a time.
- **Typical use:** power Node 1 only, then Node 2 only, then both. Write down the RSSI, SNR and sequence numbers for the test report.

### 5.7 `systemd/`

These unit files make the system **start automatically after a reboot and restart after a crash** (Feature 7, Phase 11). `install.sh` copies them to `/etc/systemd/system/`.

#### `systemd/lora-receiver.service`

- **Purpose:** Runs the receiver (`.venv/bin/python -m app.receiver`).
- **Key settings:**
  - `After=local-fs.target`: waits only for storage, **not** the network, so it keeps working without Wi-Fi.
  - `User=loramon` and `SupplementaryGroups=spi gpio`: not root, but allowed to use SPI and GPIO.
  - `Restart=always` and `RestartSec=5`: restarts after any crash. `StartLimitBurst=10` within 300 s stops an endless restart loop.
  - `TimeoutStopSec=15`: time allowed for a clean shutdown.
  - **Hardening:**
    - `NoNewPrivileges` (the program can never gain extra privileges);
    - `ProtectSystem=full` (system folders are read-only);
    - `ProtectHome` (no access to home folders);
    - `ReadWritePaths` (only `database/` and `logs/` are writable).
  - `WantedBy=multi-user.target`: starts at boot.

#### `systemd/lora-dashboard.service`

- **Purpose:** Runs the dashboard (`python -m app.serve`).
- **Settings:** the same as the receiver, except `After=network.target` and no SPI/GPIO groups, because the web server never needs the radio.

#### `systemd/lora-backup.service`

- **Purpose:** A one-shot job that runs `scripts/backup_db.py` as `loramon`, with the same hardening. It does nothing on its own; the timer starts it.

#### `systemd/lora-backup.timer`

- **Purpose:** Triggers `lora-backup.service` **every day at 02:30**.
- `Persistent=true`: if the Pi was off at 02:30, the backup runs at the next boot.
- `RandomizedDelaySec=300`: up to 5 minutes of random delay.
- Check it with `systemctl list-timers lora-backup.timer`.

### 5.8 `tests/`

Run them with `python -m pytest` from `raspberry-pi/`. There are 50 tests, they need no hardware, and they finish in about 2 s.

#### `tests/conftest.py`

- **Purpose:** Shared test set-up.
- **Contents:**
  - adds `raspberry-pi/` to `sys.path` so `import app` works;
  - **fixture `config`:** loads the real `config.toml`, then points the database and backups at a temporary folder and turns off log files. Tests never touch real data.
  - **fixture `db`:** a fresh database with the schema and nodes, closed after the test.
  - **`make_packet(**overrides)`:** builds a normal test packet. Any field can be overridden, for example `make_packet(temperature_c=45)`.

#### `tests/test_config.py`

- The default `config.toml` loads with nodes 1 and 2, sync word 0x12, absolute paths and the expected alert rules.
- Hysteresis in the wrong direction raises `ConfigError`.
- A misspelt key such as `spreading_factr` raises `ConfigError`.

#### `tests/test_protocol.py`

- The CRC check value is `0x29B1`.
- Encode then decode returns the same packet, including the all-invalid packet and a negative temperature.
- Each kind of damaged packet is rejected with the right reason (length, magic, version, CRC).
- `flag_names()` output.
- **`test_matches_firmware_encoder`:**
  - compiles the C++ host test and runs `./run_tests --vector`;
  - decodes its output in Python, checks every field, and re-encodes it to the same hex.

  This proves the ESP32 code and the Pi code agree on the packet format. It is skipped if `g++` or `make` is missing.

#### `tests/test_sequence.py`

- Covers each sequence case: first packet, consecutive, gap (lost = 3), duplicate, reboot shown by the `BOOT` flag, reboot without the boot packet (lost = 2), and `accept()` updating the state.

#### `tests/test_processor.py`

The full pipeline with a real temporary database:

| Test | Checks |
|---|---|
| `test_valid_packet_is_stored` | Values, `sound_raw`, RSSI and node counters are stored. |
| `test_rejections_are_logged_separately` | Garbage, CRC error, unknown node and duplicate are each stored in `rejected_packets` with the right reason; only one reading is stored. |
| `test_disabled_node_rejected` | A node with `enabled = false` is rejected. |
| `test_packet_loss_and_reset_tracking` | A gap counts 3 lost packets; a boot packet counts a reboot and logs an event. |
| `test_sequence_state_survives_restart` | A new processor (simulating a Pi restart) still detects duplicates and gaps. |
| `test_out_of_range_values_are_dropped` | Humidity 120 % and MQ-135 5000 become NULL; flag bit 15 is set; other values are kept. |
| `test_alert_requires_consecutive_samples_and_hysteresis` | One noisy sample resets the count; the alert opens on the 3rd consecutive sample; 39 °C keeps it open with no duplicate; three readings of 30 °C clear it. |
| `test_mq135_warmup_suppresses_air_alert` | High MQ-135 during warm-up never opens an alert. |
| `test_sensor_failure_alert` | Three packets with the BME280 error flag open `sensor_failure_bme280`. |
| `test_offline_detection_and_recovery` | A node that never reported goes offline and a fresh one does not; no duplicate offline alert; the alert clears when a packet arrives. |
| `test_active_alerts_reloaded_after_restart` | A new engine does not open the same alerts again. |
| `test_history_retention_and_backup` | History averaging; the backup copy passes the integrity check; purging removes only old rows. |

#### `tests/test_sx1278.py`

- **`FakeSPI`:** a small software model of the SX1278 registers and FIFO, including write-1-to-clear IRQ flags. It lets the real driver run with no chip.
- **`test_configuration_registers`:** the exact register values for BW 125 kHz / CR 4/5 (0x72), SF7 + CRC (0x74), AGC (0x04), sync word, RX continuous mode (0x85) and the 433 MHz frequency bytes (0x6C 0x40 0x00).
- **`test_wrong_version_raises`:** a missing chip gives a `RadioError`.
- **`test_receive_packet`:** the payload is read from the right FIFO address; SNR 7.5 dB and RSSI are calculated; IRQ flags are cleared; nothing pending returns `None`.
- **`test_crc_error_and_missing_crc_flagged`.**
- **`test_helpers`:** frequency register, low-data-rate rule, RSSI formula.

#### `tests/test_web.py`

- **Fixture:** stores 5 packets for node 1, marks node 2 offline and writes a heartbeat.
- Every page returns 200, and an unknown node returns 404.
- `/api/overview` shows node 1 online and node 2 offline, the latest temperature, 0 % loss, the receiver running and 1 active alert.
- `/api/nodes/1/history` returns 5 points.
- CSV export: download headers, 5 rows with correct values, time filtering, and 400 errors for bad input.
- Acknowledging an alert redirects and sets `acknowledged = 1`.
- `/healthz` reports ok.

### 5.9 `database/` and `logs/`

#### `database/.gitkeep` and `logs/.gitkeep`

- Empty placeholder files that keep these folders in Git.
- At runtime:
  - `database/` holds `monitor.db` (plus `monitor.db-wal` and `monitor.db-shm` from WAL mode) and `backups/`;
  - `logs/` holds `receiver.log` and `dashboard.log`, each with up to 5 rotated old files.

---

## 6. `tools/`

### `tools/decode_packet.py`

- **Purpose:** Decode a packet by hand. Copy the hex from the ESP32 serial line `[tx 12] SENT … | 4C0101…` and check exactly what was sent.
- **Usage:**
  ```
  python tools/decode_packet.py 4C010240E20100D21E00002EFB2E16942707870000DC052A0084037B13040474D1
  ```
  It prints every field (node 2, seq 123456, −12.34 °C, …) and the flag names, or `INVALID (bad_crc)` and similar if the packet is damaged.
- It imports `raspberry-pi/app/protocol.py`, so it always uses the same decoder as the receiver.

---

## 7. How the files work together

Here is one measurement's journey from the sensor to the browser, with the file responsible for each step:

| Step | What happens | File |
|---|---|---|
| 1 | Pins and radio settings are defined | `board_config.h`, `node_identity.h` |
| 2 | The slot timer says "send now" (every 60 s, at +10 s or +40 s, plus jitter) | `scheduler.cpp` |
| 3 | BME280 and BH1750 are read over I2C; MQ-135, sound and supply over the ADC | `sensor_manager.cpp` |
| 4 | Spikes are removed and ranges checked; error flags are set | `data_filter.cpp` |
| 5 | The 33-byte packet is built with node ID, sequence and CRC-16 | `packet_builder.cpp` |
| 6 | The packet is sent over LoRa; the radio sleeps | `lora_radio.cpp` |
| 7 | The serial monitor shows the values and the hex | `diagnostics.cpp` |
| 8 | The Pi's SX1278 raises DIO0; the payload, RSSI and SNR are read | `sx1278.py` |
| 9 | Radio CRC, length, magic, version and CRC-16 are checked; the packet is decoded | `processor.py`, `protocol.py` |
| 10 | Unknown or disabled nodes are rejected; duplicates, gaps and reboots are detected | `processor.py`, `sequence.py` |
| 11 | Impossible values are removed | `validator.py` |
| 12 | The reading and node counters are stored in one transaction; rejected packets are stored separately | `database.py` |
| 13 | Thresholds (consecutive samples and hysteresis), sensor failures and the offline check are evaluated | `alerts.py` |
| 14 | The receiver loop also writes the heartbeat and handles retention and radio recovery | `receiver.py` |
| 15 | The browser polls the JSON API; pages and charts update | `web.py`, `templates/*.html`, `app.js`, `style.css` |
| 16 | CSV export and daily backup | `exporter.py`, `backup_db.py`, `lora-backup.timer` |
| 17 | Automatic start and restart after a reboot or crash | `lora-receiver.service`, `lora-dashboard.service`, `install.sh` |

Settings that must always match on both sides:

| Setting | ESP32 file | Pi file |
|---|---|---|
| Frequency, BW, SF, CR, preamble, sync word, CRC | `board_config.h` (`radio::`) | `config.toml` (`[radio]`) |
| Packet layout and flags | `packet_builder.h/.cpp` | `protocol.py` |
| Node IDs | `platformio.ini` (`-DNODE_ID`) | `config.toml` (`[[nodes]]`) |
| Wiring | `board_config.h` (`board::`) | `config.toml` (`reset_pin`, `dio0_pin`) and `connections/*.txt` |
