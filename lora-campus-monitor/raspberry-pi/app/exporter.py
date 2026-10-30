"""CSV export of readings (streamed, so large exports use little memory)."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Iterator

from .database import READING_COLUMNS, Database
from .protocol import flag_names

CSV_COLUMNS = READING_COLUMNS + ("status_text",)


def iter_csv(db: Database, node_id: int | None, start: datetime | None, end: datetime | None) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def flush() -> str:
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return value

    writer.writerow(CSV_COLUMNS)
    yield flush()
    for i, row in enumerate(db.iter_readings(node_id, start, end), start=1):
        writer.writerow([row[c] for c in READING_COLUMNS] + ["; ".join(flag_names(row["status_flags"]))])
        if i % 500 == 0:
            yield flush()
    yield flush()


def export_filename(node_id: int | None, start: datetime | None, end: datetime | None) -> str:
    who = f"node{node_id}" if node_id is not None else "all-nodes"
    fmt = "%Y%m%d-%H%M"
    span = f"_{start.strftime(fmt) if start else 'begin'}_{end.strftime(fmt) if end else 'now'}"
    return f"readings_{who}{span}.csv"
