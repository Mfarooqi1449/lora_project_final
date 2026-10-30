"""SQLite database layer. All SQL uses parameter binding."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from .config import NodeConfig
from .protocol import Packet
from .sequence import NodeSequenceState, SequenceResult, SequenceStatus

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    node_id          INTEGER PRIMARY KEY,
    node_name        TEXT    NOT NULL,
    location         TEXT    NOT NULL DEFAULT '',
    enabled          INTEGER NOT NULL DEFAULT 1,
    last_seen        TEXT,
    last_sequence    INTEGER,
    last_uptime      INTEGER,
    last_rssi_dbm    REAL,
    last_snr_db      REAL,
    packets_received INTEGER NOT NULL DEFAULT 0,
    packets_lost     INTEGER NOT NULL DEFAULT 0,
    duplicates       INTEGER NOT NULL DEFAULT 0,
    reboots          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS readings (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at      TEXT    NOT NULL,
    node_id          INTEGER NOT NULL REFERENCES nodes(node_id),
    sequence_number  INTEGER NOT NULL,
    uptime_seconds   INTEGER,
    protocol_version INTEGER,
    temperature_c    REAL,
    humidity_percent REAL,
    pressure_hpa     REAL,
    light_lux        REAL,
    air_quality_raw  INTEGER,
    sound_raw        INTEGER,
    sound_peak       INTEGER,
    supply_voltage   REAL,
    rssi_dbm         REAL,
    snr_db           REAL,
    status_flags     INTEGER NOT NULL DEFAULT 0,
    lost_before      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_readings_node_time ON readings(node_id, received_at);
CREATE INDEX IF NOT EXISTS idx_readings_time ON readings(received_at);

CREATE TABLE IF NOT EXISTS alerts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at      TEXT    NOT NULL,
    node_id         INTEGER NOT NULL REFERENCES nodes(node_id),
    alert_type      TEXT    NOT NULL,
    measured_value  REAL,
    threshold_value REAL,
    severity        TEXT    NOT NULL,
    message         TEXT    NOT NULL DEFAULT '',
    acknowledged    INTEGER NOT NULL DEFAULT 0,
    cleared_at      TEXT
);
-- At most one active alert per node and type.
CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_one_active
    ON alerts(node_id, alert_type) WHERE cleared_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at);

CREATE TABLE IF NOT EXISTS system_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message    TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_events_created ON system_events(created_at);

CREATE TABLE IF NOT EXISTS rejected_packets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    reason      TEXT NOT NULL,
    node_id     INTEGER,
    rssi_dbm    REAL,
    snr_db      REAL,
    raw_hex     TEXT NOT NULL DEFAULT '',
    detail      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_rejected_time ON rejected_packets(received_at);

CREATE TABLE IF NOT EXISTS system_status (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL
);
"""

READING_COLUMNS = (
    "id",
    "received_at",
    "node_id",
    "sequence_number",
    "uptime_seconds",
    "temperature_c",
    "humidity_percent",
    "pressure_hpa",
    "light_lux",
    "air_quality_raw",
    "sound_raw",
    "sound_peak",
    "supply_voltage",
    "rssi_dbm",
    "snr_db",
    "status_flags",
    "lost_before",
)

HISTORY_METRICS = (
    "temperature_c",
    "humidity_percent",
    "pressure_hpa",
    "light_lux",
    "air_quality_raw",
    "sound_raw",
    "sound_peak",
    "supply_voltage",
    "rssi_dbm",
    "snr_db",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    """Canonical UTC timestamp format used in every table (sortable as text)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), timeout=15)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 15000")
        if str(path) != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA synchronous = NORMAL")

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------ schema
    def init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(SCHEMA)
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def sync_nodes(self, nodes: tuple[NodeConfig, ...] | list[NodeConfig]) -> None:
        with self.conn:
            for node in nodes:
                self.conn.execute(
                    """
                    INSERT INTO nodes (node_id, node_name, location, enabled)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(node_id) DO UPDATE SET
                        node_name = excluded.node_name,
                        location = excluded.location,
                        enabled = excluded.enabled
                    """,
                    (node.node_id, node.name, node.location, int(node.enabled)),
                )

    # ------------------------------------------------------------------- nodes
    def get_nodes(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM nodes ORDER BY node_id").fetchall()
        return [dict(r) for r in rows]

    def get_node(self, node_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM nodes WHERE node_id = ?", (node_id,)).fetchone()
        return dict(row) if row else None

    def load_sequence_states(self) -> dict[int, NodeSequenceState]:
        rows = self.conn.execute("SELECT node_id, last_sequence, last_uptime FROM nodes").fetchall()
        return {r["node_id"]: NodeSequenceState(r["last_sequence"], r["last_uptime"]) for r in rows}

    # ---------------------------------------------------------------- readings
    def store_reading(
        self,
        packet: Packet,
        received_at: datetime,
        rssi_dbm: float | None,
        snr_db: float | None,
        seq: SequenceResult,
    ) -> int:
        ts = to_iso(received_at)
        with self.conn:
            cur = self.conn.execute(
                """
                INSERT INTO readings (
                    received_at, node_id, sequence_number, uptime_seconds, protocol_version,
                    temperature_c, humidity_percent, pressure_hpa, light_lux,
                    air_quality_raw, sound_raw, sound_peak, supply_voltage,
                    rssi_dbm, snr_db, status_flags, lost_before
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    packet.node_id,
                    packet.sequence_number,
                    packet.uptime_seconds,
                    packet.protocol_version,
                    packet.temperature_c,
                    packet.humidity_percent,
                    packet.pressure_hpa,
                    packet.light_lux,
                    packet.air_quality_raw,
                    packet.sound_avg,
                    packet.sound_peak,
                    packet.supply_voltage,
                    rssi_dbm,
                    snr_db,
                    packet.status_flags,
                    seq.lost,
                ),
            )
            self.conn.execute(
                """
                UPDATE nodes SET
                    last_seen = ?, last_sequence = ?, last_uptime = ?,
                    last_rssi_dbm = ?, last_snr_db = ?,
                    packets_received = packets_received + 1,
                    packets_lost = packets_lost + ?,
                    reboots = reboots + ?
                WHERE node_id = ?
                """,
                (
                    ts,
                    packet.sequence_number,
                    packet.uptime_seconds,
                    rssi_dbm,
                    snr_db,
                    seq.lost,
                    1 if seq.status is SequenceStatus.NODE_RESET else 0,
                    packet.node_id,
                ),
            )
            return cur.lastrowid

    def record_duplicate(self, node_id: int) -> None:
        with self.conn:
            self.conn.execute("UPDATE nodes SET duplicates = duplicates + 1 WHERE node_id = ?", (node_id,))

    def latest_reading(self, node_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM readings WHERE node_id = ? ORDER BY received_at DESC, id DESC LIMIT 1",
            (node_id,),
        ).fetchone()
        return dict(row) if row else None

    def recent_readings(self, node_id: int, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM readings WHERE node_id = ? ORDER BY received_at DESC, id DESC LIMIT ?",
            (node_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def history(self, node_id: int, start: datetime, end: datetime, max_points: int = 500) -> list[dict]:
        """Readings in [start, end], averaged into at most ~max_points buckets."""
        span = max(1, int((end - start).total_seconds()))
        bucket = max(1, -(-span // max(1, max_points)))
        averages = ", ".join(f"AVG({m}) AS {m}" for m in HISTORY_METRICS)
        rows = self.conn.execute(
            f"""
            SELECT CAST(strftime('%s', received_at) AS INTEGER) / ? AS bucket,
                   MIN(received_at) AS received_at, COUNT(*) AS samples, {averages}
            FROM readings
            WHERE node_id = ? AND received_at >= ? AND received_at <= ?
            GROUP BY bucket ORDER BY bucket
            """,
            (bucket, node_id, to_iso(start), to_iso(end)),
        ).fetchall()
        return [dict(r) for r in rows]

    def iter_readings(
        self, node_id: int | None, start: datetime | None, end: datetime | None
    ) -> Iterator[sqlite3.Row]:
        clauses, params = [], []
        if node_id is not None:
            clauses.append("node_id = ?")
            params.append(node_id)
        if start is not None:
            clauses.append("received_at >= ?")
            params.append(to_iso(start))
        if end is not None:
            clauses.append("received_at <= ?")
            params.append(to_iso(end))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cols = ", ".join(READING_COLUMNS)
        cursor = self.conn.execute(f"SELECT {cols} FROM readings {where} ORDER BY received_at, id", params)
        with closing(cursor):
            yield from cursor

    def reading_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]

    def purge_older_than(self, days: int, now: datetime | None = None) -> int:
        cutoff = to_iso((now or utc_now()) - timedelta(days=days))
        with self.conn:
            readings = self.conn.execute("DELETE FROM readings WHERE received_at < ?", (cutoff,)).rowcount
            self.conn.execute("DELETE FROM rejected_packets WHERE received_at < ?", (cutoff,))
            self.conn.execute("DELETE FROM system_events WHERE created_at < ?", (cutoff,))
            self.conn.execute(
                "DELETE FROM alerts WHERE cleared_at IS NOT NULL AND cleared_at < ?", (cutoff,)
            )
        return readings

    # -------------------------------------------------------- rejected packets
    def insert_rejected(
        self,
        received_at: datetime,
        reason: str,
        raw: bytes,
        rssi_dbm: float | None = None,
        snr_db: float | None = None,
        node_id: int | None = None,
        detail: str = "",
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO rejected_packets (received_at, reason, node_id, rssi_dbm, snr_db, raw_hex, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (to_iso(received_at), reason, node_id, rssi_dbm, snr_db, raw[:255].hex().upper(), detail),
            )

    def recent_rejected(self, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM rejected_packets ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def rejected_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM rejected_packets").fetchone()[0]

    # ------------------------------------------------------- events and status
    def log_event(self, event_type: str, message: str = "", when: datetime | None = None) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO system_events (created_at, event_type, message) VALUES (?, ?, ?)",
                (to_iso(when or utc_now()), event_type, message),
            )

    def recent_events(self, limit: int = 50, event_type: str | None = None) -> list[dict]:
        if event_type:
            rows = self.conn.execute(
                "SELECT * FROM system_events WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                (event_type, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM system_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def set_status(self, values: dict[str, object], when: datetime | None = None) -> None:
        ts = to_iso(when or utc_now())
        with self.conn:
            self.conn.executemany(
                """
                INSERT INTO system_status (key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                [(k, None if v is None else str(v), ts) for k, v in values.items()],
            )

    def get_status(self) -> dict[str, dict]:
        rows = self.conn.execute("SELECT key, value, updated_at FROM system_status").fetchall()
        return {r["key"]: {"value": r["value"], "updated_at": r["updated_at"]} for r in rows}

    # ------------------------------------------------------------------ alerts
    def open_alert(
        self,
        node_id: int,
        alert_type: str,
        measured_value: float | None,
        threshold_value: float | None,
        severity: str,
        message: str,
        when: datetime | None = None,
    ) -> int | None:
        """Insert an alert; returns None if one is already active for node+type."""
        try:
            with self.conn:
                cur = self.conn.execute(
                    """
                    INSERT INTO alerts (created_at, node_id, alert_type, measured_value,
                                        threshold_value, severity, message)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (to_iso(when or utc_now()), node_id, alert_type, measured_value,
                     threshold_value, severity, message),
                )
                return cur.lastrowid
        except sqlite3.IntegrityError:
            return None

    def clear_alert(self, alert_id: int, when: datetime | None = None) -> bool:
        with self.conn:
            cur = self.conn.execute(
                "UPDATE alerts SET cleared_at = ? WHERE id = ? AND cleared_at IS NULL",
                (to_iso(when or utc_now()), alert_id),
            )
            return cur.rowcount == 1

    def acknowledge_alert(self, alert_id: int) -> bool:
        with self.conn:
            cur = self.conn.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
            return cur.rowcount == 1

    def active_alerts(self, node_id: int | None = None) -> list[dict]:
        sql = "SELECT * FROM alerts WHERE cleared_at IS NULL"
        params: tuple = ()
        if node_id is not None:
            sql += " AND node_id = ?"
            params = (node_id,)
        rows = self.conn.execute(sql + " ORDER BY created_at DESC, id DESC", params).fetchall()
        return [dict(r) for r in rows]

    def cleared_alerts(self, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM alerts WHERE cleared_at IS NOT NULL ORDER BY cleared_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ backup
    def backup_to(self, destination: str | Path) -> Path:
        """Consistent online backup (safe while the receiver is writing)."""
        dest = Path(destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(str(dest))) as target:
            self.conn.backup(target)
        return dest

    def integrity_ok(self) -> bool:
        return self.conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
