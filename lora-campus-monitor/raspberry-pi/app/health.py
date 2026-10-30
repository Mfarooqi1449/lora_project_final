"""Main-node health information (CPU temperature, disk, uptime)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def cpu_temperature_c() -> float | None:
    try:
        raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()
        return round(int(raw) / 1000.0, 1)
    except (OSError, ValueError):
        return None


def disk_usage(path: Path) -> dict | None:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return {
        "total_gb": round(usage.total / 1e9, 2),
        "free_gb": round(usage.free / 1e9, 2),
        "used_percent": round(100 * usage.used / usage.total, 1) if usage.total else None,
    }


def system_uptime_s() -> int | None:
    try:
        return int(float(Path("/proc/uptime").read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        return None


def load_average() -> float | None:
    try:
        return round(os.getloadavg()[0], 2)
    except (OSError, AttributeError):  # AttributeError: not available on Windows
        return None


def file_size_mb(path: Path) -> float | None:
    total = 0
    found = False
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(path) + suffix)
        if candidate.exists():
            total += candidate.stat().st_size
            found = True
    return round(total / 1e6, 2) if found else None
