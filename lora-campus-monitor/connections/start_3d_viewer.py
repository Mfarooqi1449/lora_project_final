#!/usr/bin/env python3
"""Start the 3D wiring viewer in your web browser.

Works on Windows, Linux and macOS with only Python 3.7+ (no extra packages,
no internet). It serves the 3d/ folder on a local web server and opens the
browser.

  python start_3d_viewer.py                 # system overview
  python start_3d_viewer.py --view node1    # system | main | node1 | node2
  python start_3d_viewer.py --port 9000     # choose another port
  python start_3d_viewer.py --no-browser    # only start the server

Stop with Ctrl+C.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socket
import sys
import threading
import webbrowser
from pathlib import Path

VIEWS = ("system", "main", "node1", "node2")
ROOT = Path(__file__).resolve().parent / "3d"


def find_free_port(start: int, host: str) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise SystemExit(f"No free port found between {start} and {start + 49}")


def lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is sent
            return s.getsockname()[0]
    except OSError:
        return None


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep the console clean
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the 3D wiring viewer")
    parser.add_argument("--view", choices=VIEWS, default="system", help="view to open first")
    parser.add_argument("--port", type=int, default=8090, help="first port to try (default 8090)")
    parser.add_argument("--lan", action="store_true", help="also allow other devices on the network")
    parser.add_argument("--no-browser", action="store_true", help="do not open the browser")
    args = parser.parse_args()

    if not (ROOT / "connections_3d.html").exists():
        print(f"ERROR: {ROOT / 'connections_3d.html'} not found. Keep this script next to the 3d/ folder.")
        return 1

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    port = find_free_port(args.port, host)
    handler = functools.partial(QuietHandler, directory=str(ROOT))
    server = http.server.ThreadingHTTPServer((host, port), handler)

    url = f"http://localhost:{port}/connections_3d.html#{args.view}"
    print("LoRa Campus Monitor - 3D wiring viewer")
    print(f"  Open:  {url}")
    if args.lan:
        ip = lan_ip()
        if ip:
            print(f"  LAN:   http://{ip}:{port}/connections_3d.html#{args.view}")
    print("  Views: #system  #main  #node1  #node2")
    print("  Stop:  Ctrl+C")

    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
