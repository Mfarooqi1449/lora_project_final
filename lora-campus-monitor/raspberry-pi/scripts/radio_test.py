#!/usr/bin/env python3
"""Bench test for the Pi LoRa module: prints every packet with RSSI/SNR.

Does not touch the database. Stop the receiver service first:
  sudo systemctl stop lora-receiver
  python scripts/radio_test.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_config  # noqa: E402
from app.protocol import ProtocolError, decode, flag_names  # noqa: E402
from app.sx1278 import SX1278, RadioError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="path to config.toml")
    args = parser.parse_args()

    config = load_config(args.config)
    radio = SX1278(config.radio)
    try:
        radio.open()
    except (RadioError, OSError) as exc:
        print(f"Radio initialisation failed: {exc}")
        return 1

    print(f"SX1278 version 0x{radio.version:02X} | {radio.describe()}")
    print("Waiting for packets (Ctrl+C to stop)...")
    try:
        while True:
            pkt = radio.receive(timeout=1.0)
            if pkt is None:
                continue
            stamp = datetime.now().strftime("%H:%M:%S")
            head = f"[{stamp}] {len(pkt.payload)} B RSSI {pkt.rssi_dbm} dBm SNR {pkt.snr_db} dB"
            if pkt.crc_error:
                print(f"{head} RADIO CRC ERROR {pkt.payload.hex().upper()}")
                continue
            try:
                p = decode(pkt.payload)
            except ProtocolError as exc:
                print(f"{head} INVALID ({exc.reason}): {pkt.payload.hex().upper()}")
                continue
            print(
                f"{head} node {p.node_id} seq {p.sequence_number} up {p.uptime_seconds}s "
                f"T={p.temperature_c} RH={p.humidity_percent} P={p.pressure_hpa} L={p.light_lux} "
                f"AQ={p.air_quality_raw} S={p.sound_avg}/{p.sound_peak} V={p.supply_voltage} "
                f"{flag_names(p.status_flags) or ''}"
            )
    except KeyboardInterrupt:
        pass
    finally:
        radio.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
