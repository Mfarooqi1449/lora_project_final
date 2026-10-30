#!/usr/bin/env python3
"""Consistent online SQLite backup (safe while the receiver is running).

Usage:
  python scripts/backup_db.py                      # to [database].backup_dir
  python scripts/backup_db.py --dest /media/usb    # e.g. a mounted USB drive
  python scripts/backup_db.py --restore FILE       # restore (stop services first!)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_config  # noqa: E402
from app.database import Database  # noqa: E402


def backup(config, dest_dir: Path, keep: int) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = dest_dir / f"monitor-{stamp}.db"
    with Database(config.database.path) as db:
        db.backup_to(target)
        with Database(target) as copy:
            if not copy.integrity_ok():
                raise RuntimeError(f"Backup integrity check failed: {target}")
        size_mb = target.stat().st_size / 1e6
        db.log_event("backup", f"{target} ({size_mb:.2f} MB)")

    if keep > 0:
        backups = sorted(dest_dir.glob("monitor-*.db"))
        for old in backups[:-keep]:
            old.unlink()
    return target


def restore(config, source: Path) -> None:
    with Database(source) as src:
        if not src.integrity_ok():
            raise RuntimeError(f"{source} failed integrity check; not restoring")
    live = config.database.path
    if live.exists():
        safety = live.with_name(f"{live.stem}-before-restore-{datetime.now():%Y%m%d-%H%M%S}.db")
        with Database(live) as db:
            db.backup_to(safety)
        print(f"Current database saved to {safety}")
        for suffix in ("-wal", "-shm"):
            Path(str(live) + suffix).unlink(missing_ok=True)
    shutil.copy2(source, live)
    print(f"Restored {source} -> {live}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="path to config.toml")
    parser.add_argument("--dest", type=Path, help="backup directory (default: config backup_dir)")
    parser.add_argument("--keep", type=int, help="number of backups to keep in the directory")
    parser.add_argument("--restore", type=Path, help="restore this backup file (stop both services first)")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.restore:
        restore(config, args.restore)
        return 0

    dest = args.dest or config.database.backup_dir
    keep = config.database.backup_keep if args.keep is None else args.keep
    target = backup(config, dest, keep)
    print(f"Backup written: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
