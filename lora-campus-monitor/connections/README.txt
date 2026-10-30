======================================================================
LoRa CAMPUS MONITOR - CONNECTIONS FOLDER  (START HERE)
======================================================================

This folder is SELF-CONTAINED. You can copy it on its own (USB stick,
zip, email) to any computer, workbench PC or phone and use it without
the rest of the project.
  - The .txt and .csv files open in any text editor or spreadsheet.
  - The 3D viewer needs only Python 3.7 or newer. No internet, no packages.
  - The PNG images open in any image viewer.

----------------------------------------------------------------------
1. WHAT IS IN THIS FOLDER
----------------------------------------------------------------------
 README.txt                       This file
 00_index_and_overview.txt        Block diagram + pin summary of all units
 01_main_node_raspberry_pi.txt    Wiring guide: Raspberry Pi 3B+ + Ra-02
 02_field_node_1_esp32.txt        Wiring guide: ESP32 Node 1 + sensors
 03_field_node_2_esp32.txt        Wiring guide: ESP32 Node 2 + sensors
 04_master_connection_list.txt    ONE checklist of EVERY required
                                  connection (all 3 units) + parts count
 master_connection_list.csv       Same list for Excel / LibreOffice /
                                  Google Sheets (one row per connection,
                                  "Done" column to tick off)
 05_hardware_list.txt             HARDWARE LIST / bill of materials: every
                                  module, part, cable, tool + quantities
                                  (main, per node, spares, total to buy)
 hardware_list.csv                Same hardware list for Excel with empty
                                  "Unit price" / "Line total" columns
 start_3d_viewer.py               Starts the 3D viewer (any OS)
 start_3d_viewer.bat              Windows: double-click to start
 start_3d_viewer.sh               Linux / macOS: ./start_3d_viewer.sh
 3d/connections_3d.html           Interactive 3D wiring model
 3d/connections_3d.js             3D model code
 3d/vendor/                       three.js library (offline copy, MIT)
 3d/images/*.png                  Ready-made 3D pictures + close-ups
 3d/README.md                     Details of the 3D viewer

----------------------------------------------------------------------
2. HOW TO RUN / OPEN EACH PART
----------------------------------------------------------------------

2.1 Text guides and the checklist (no software needed)
 Open any .txt file in Notepad, TextEdit, gedit, VS Code or similar.
 For printing, use a monospaced font (Courier, Consolas) so the tables line up.
 A4 tip: print 04_master_connection_list.txt and tick boxes at the bench.

2.2 Spreadsheet list
 Open master_connection_list.csv in Excel, LibreOffice Calc or Google
 Sheets (File > Import). Filter by "Unit" or "Need", and type "x" in the
 "Done" column as you wire.

2.3 3D wiring viewer
 Prerequisite: Python 3.7+ (https://www.python.org/downloads/)
               Windows: tick "Add python.exe to PATH" during installation.

 Windows:        double-click  start_3d_viewer.bat
 Linux / macOS:  open a terminal in this folder, then
                   chmod +x start_3d_viewer.sh      (first time only)
                   ./start_3d_viewer.sh
 Any OS:         python start_3d_viewer.py         (or python3 / py -3)

 The browser opens  http://localhost:8090/connections_3d.html
 (if 8090 is busy, the next free port is used and printed).

 Options:
   --view system|main|node1|node2   open a specific view
   --port 9000                      use another port
   --lan                            allow phones/laptops on the same network
                                    (prints a http://<ip>:<port>/... address)
   --no-browser                     only start the server
 Stop: Ctrl+C in the terminal (or close the window on Windows).

 In the viewer:
   - Drag to rotate, right-drag to pan, scroll to zoom.
   - Hover over a wire to see "From -> To".
   - Click a wire or a list row to highlight that one connection.
   - Buttons: System overview, Main node, Field node 1, Field node 2.
   - Checkboxes: pin labels, auto-rotate.

 No Python? Open the pictures in 3d/images/ instead.
 Do not double-click the .html file directly. Browsers block local
 scripts, so always use the launcher.

----------------------------------------------------------------------
3. WHERE AND WHEN EACH FILE IS NEEDED
----------------------------------------------------------------------
 Project phase (delivery plan)         Use these files
 ------------------------------------  --------------------------------
 Phase 0  Freeze requirements           00_index, 05_hardware_list (approved BOM)
 Phase 1  Procurement + inspection      05_hardware_list.txt (what to buy,
                                        buying checks), hardware_list.csv
                                        (add prices = cost sheet)
 Phase 2  Prepare Raspberry Pi          01_main_node (sections 1, 6, 8)
 Phase 3  Build Node 1 (sensors only)   02_field_node_1 (sections 1, 3-7),
                                        3d viewer "Field node 1",
                                        3d/images/wiring_3d_node_mq135_closeup.png
 Phase 4  Build Node 2                  03_field_node_2, tick [N2] in 04_master
 Phase 6  LoRa bench test               01 section 2-4, 02/03 section 2,
                                        3d/images/wiring_3d_main_closeup.png,
                                        3d/images/wiring_3d_node_lora_i2c_closeup.png
 Phase 12 Final hardware assembly       04_master (tick every row again on
                                        the perfboard/PCB), golden rules
 Phase 13 Field test                    00_index (system diagram)
 Phase 15 Demonstration / viva          3d viewer (rotate live),
                                        3d/images/*.png in PPT and report
 Phase 16 Deliverables / handover       Whole folder = "Hardware connections",
                                        "Circuit diagrams" and "Bill of
                                        materials and cost" documents
 Troubleshooting                        01/02/03 power-on checklists

 Before the FIRST power-on of any unit:
   1. Every "Required" row of that unit in 04_master is ticked.
   2. The power-on checklist at the end of 01 / 02 / 03 is complete.
   3. Antennas are fitted. Ra-02 is on 3.3 V. The MQ-135 junction is <= 3.3 V.

----------------------------------------------------------------------
4. HOW THIS FOLDER MATCHES THE SOFTWARE (only if you have the full project)
----------------------------------------------------------------------
 The pin numbers here are the same as in the software settings:
   ESP32 pins          -> esp32-node/include/board_config.h
   Pi RESET/DIO0/SPI   -> raspberry-pi/config/config.toml [radio]
   Radio settings      -> both files above (must be identical)
 The "Software setting" column in 04_master / the CSV names the exact
 setting that uses each pin. If you ever change a pin, update the
 setting AND these documents.

----------------------------------------------------------------------
5. GOLDEN RULES
----------------------------------------------------------------------
 1. Ra-02 VCC = 3.3 V only (Pi pin 1 / ESP32 3V3). Never 5 V.
 2. ESP32 inputs <= 3.3 V. Measure the MQ-135 divider before GPIO34.
 3. Fit the antenna on every Ra-02 BEFORE power-on.
 4. One common GND inside each unit. The three units are not wired together.
 5. Disconnect power before changing any wire.

END OF FILE
