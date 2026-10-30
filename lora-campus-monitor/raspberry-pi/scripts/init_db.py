#!/usr/bin/env python3
"""Create the SQLite schema and node rows, then print a short summary."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_config  # noqa: E402
from app.database import Database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="path to config.toml")
    args = parser.parse_args()

    config = load_config(args.config)
    with Database(config.database.path) as db:
        db.init_schema()
        db.sync_nodes(config.nodes)
        print(f"Database ready: {config.database.path}")
        for node in db.get_nodes():
            print(f"  node {node['node_id']}: {node['node_name']} @ {node['location']} "
                  f"(enabled={bool(node['enabled'])}, readings so far: {node['packets_received']})")
        print(f"  integrity: {'ok' if db.integrity_ok() else 'FAILED'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
