#!/bin/sh
# Open the 3D wiring viewer (Linux / macOS). Needs Python 3.7+.
#   ./start_3d_viewer.sh            or   ./start_3d_viewer.sh --view node1
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
    exec python3 start_3d_viewer.py "$@"
fi
exec python start_3d_viewer.py "$@"
