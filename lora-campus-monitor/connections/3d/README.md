# 3D Wiring Viewer

This folder is an interactive 3D model of all connections for the main node and both field nodes. It uses the same pins as `../01_main_node_raspberry_pi.txt`, `../02_field_node_1_esp32.txt`, `../03_field_node_2_esp32.txt` and `../04_master_connection_list.txt`. If you have the full project, those pins are also set in `esp32-node/include/board_config.h` and `raspberry-pi/config/config.toml`. The viewer does not need either of those files.
## Open it

Easiest: use the launcher in the parent folder (needs Python 3.7+ only):

- Windows: double-click `../start_3d_viewer.bat`
- Linux / macOS: run `../start_3d_viewer.sh`
- Any OS: run `python ../start_3d_viewer.py --view node1`

Manual alternative: run `python3 -m http.server 8090` in this folder, then open `http://localhost:8090/connections_3d.html`.

Do not double-click the HTML file; browsers block local scripts.

Add `#system`, `#main`, `#node1` or `#node2` to the URL to open a view directly. The page needs no internet, because three.js is included in `vendor/`.

## Views

| Button | Shows |
|---|---|
| System overview | Star network with animated LoRa packets from Node 1 and Node 2 to the Pi, plus the Ethernet/Wi-Fi link to the laptop |
| Main node | Raspberry Pi 3B+ 40-pin header and the eight wires to the Ra-02. Pins 2 and 4 (5 V) are marked in red. Also shows the decoupling capacitors, antenna, power and network |
| Field node 1 / 2 | Perfboard with power rails, the ESP32 DevKit V1, the Ra-02 (SPI), BME280 and BH1750 (shared I2C), the MQ-135 with its 10k/20k divider, 1 kΩ resistor and 100 nF filter, the sound sensor, the optional supply monitor, and the 5 V adapter |

Controls:
- Drag to rotate, right-drag to pan, and scroll to zoom.
- Hover over a wire to see what it connects.
- Click a wire, or a row in the right-hand list, to highlight that one connection.
- "Pin labels" shows or hides the pin names. "Auto-rotate" turns the model slowly.

Wire colours follow the wire colour guide in the hardware design document:

| Colour | Use |
|---|---|
| Red | 5 V |
| Orange | 3.3 V |
| Black | GND |
| Blue | SDA |
| Cyan | SCL |
| Yellow | SCK |
| Green | MISO |
| Purple | MOSI |
| White | NSS |
| Brown | RESET |
| Gray | DIO0 |
| Magenta | analog |

## Still images (`images/`)

| File | Content |
|---|---|
| `wiring_3d_system.png` | System overview |
| `wiring_3d_main.png` | Raspberry Pi main node |
| `wiring_3d_main_closeup.png` | Close-up: Pi GPIO header → Ra-02 |
| `wiring_3d_node1.png` | ESP32 field node 1 |
| `wiring_3d_node2.png` | ESP32 field node 2 |
| `wiring_3d_node_lora_i2c_closeup.png` | Close-up: ESP32 → Ra-02 (SPI) and BH1750 (I2C) |
| `wiring_3d_node_mq135_closeup.png` | Close-up: MQ-135 voltage divider → GPIO34 |

The model is a wiring guide, not an exact mechanical drawing. Module sizes and pin spacing are enlarged so the labels are readable. Always check the labels on your actual breakout boards before power-on.

## Files

| File | Purpose |
|---|---|
| `connections_3d.html` | Page layout: top bar, 3D view, connection list, legend |
| `connections_3d.js` | Builds the scenes with three.js. Each wire is a coloured tube between two pins, with an info text |
| `vendor/three.min.js`, `vendor/OrbitControls.js` | three.js r147 (MIT licence, see `vendor/LICENSE-three.txt`) |
