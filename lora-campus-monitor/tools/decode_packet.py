#!/usr/bin/env python3
"""Decode a packet hex string (e.g. copied from the ESP32 serial '[tx ...]' line).

  python tools/decode_packet.py 4C010240E20100D21E...
"""

import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "raspberry-pi"))

from app.protocol import ProtocolError, decode, flag_names  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    try:
        packet = decode(bytes.fromhex(sys.argv[1].strip()))
    except ValueError as exc:
        reason = exc.reason if isinstance(exc, ProtocolError) else "bad_hex"
        print(f"INVALID ({reason}): {exc}")
        return 1
    for key, value in asdict(packet).items():
        print(f"{key:18} {value}")
    print(f"{'flags':18} {', '.join(flag_names(packet.status_flags)) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
