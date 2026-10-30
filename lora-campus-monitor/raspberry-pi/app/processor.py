"""Packet pipeline: decode -> validate -> sequence check -> store -> alerts."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from .alerts import AlertEngine
from .database import Database, utc_now
from .protocol import ProtocolError, decode, flag_names
from .sequence import NodeSequenceState, SequenceStatus, accept, classify
from .validator import validate_ranges

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessResult:
    accepted: bool
    reason: str  # "stored" or a rejection code
    node_id: int | None = None
    sequence_number: int | None = None
    lost: int = 0
    reading_id: int | None = None


class PacketProcessor:
    def __init__(self, db: Database, alerts: AlertEngine):
        self.db = db
        self.alerts = alerts
        self.states: dict[int, NodeSequenceState] = db.load_sequence_states()
        self.stats = {"received": 0, "stored": 0, "rejected": 0, "duplicates": 0}

    def _nodes(self) -> dict[int, dict]:
        return {n["node_id"]: n for n in self.db.get_nodes()}

    def _reject(self, when, reason, raw, rssi, snr, node_id=None, detail="") -> ProcessResult:
        self.stats["rejected"] += 1
        self.db.insert_rejected(when, reason, raw, rssi, snr, node_id, detail)
        log.warning("Rejected packet (%s) node=%s rssi=%s snr=%s %s", reason, node_id, rssi, snr, detail)
        return ProcessResult(False, reason, node_id)

    def handle(
        self,
        raw: bytes,
        rssi_dbm: float | None,
        snr_db: float | None,
        crc_error: bool = False,
        received_at: datetime | None = None,
    ) -> ProcessResult:
        when = received_at or utc_now()
        self.stats["received"] += 1

        if crc_error:
            return self._reject(when, "radio_crc_error", raw, rssi_dbm, snr_db)

        try:
            packet = decode(raw)
        except ProtocolError as exc:
            return self._reject(when, exc.reason, raw, rssi_dbm, snr_db, detail=str(exc))

        node = self._nodes().get(packet.node_id)
        if node is None:
            return self._reject(when, "unknown_node", raw, rssi_dbm, snr_db, packet.node_id)
        if not node["enabled"]:
            return self._reject(when, "node_disabled", raw, rssi_dbm, snr_db, packet.node_id)

        state = self.states.setdefault(packet.node_id, NodeSequenceState())
        seq = classify(state, packet.sequence_number, packet.uptime_seconds, packet.status_flags)
        if seq.status is SequenceStatus.DUPLICATE:
            self.stats["duplicates"] += 1
            self.db.record_duplicate(packet.node_id)
            return self._reject(
                when, "duplicate", raw, rssi_dbm, snr_db, packet.node_id, f"seq {packet.sequence_number}"
            )

        validation = validate_ranges(packet)
        packet = validation.packet
        if validation.rejected_fields:
            log.warning("Node %s: out-of-range values dropped: %s", packet.node_id, ", ".join(validation.rejected_fields))

        reading_id = self.db.store_reading(packet, when, rssi_dbm, snr_db, seq)
        accept(state, packet.sequence_number, packet.uptime_seconds)
        self.stats["stored"] += 1

        if seq.status is SequenceStatus.NODE_RESET:
            self.db.log_event(
                "node_reset",
                f"Node {packet.node_id} restarted (seq {packet.sequence_number}, uptime {packet.uptime_seconds} s)",
                when,
            )
        if seq.lost:
            log.info("Node %s: %d packet(s) lost before seq %d", packet.node_id, seq.lost, packet.sequence_number)

        flags = flag_names(packet.status_flags)
        log.info(
            "Node %s seq %d stored: T=%s RH=%s P=%s L=%s AQ=%s S=%s V=%s RSSI=%s SNR=%s%s",
            packet.node_id,
            packet.sequence_number,
            packet.temperature_c,
            packet.humidity_percent,
            packet.pressure_hpa,
            packet.light_lux,
            packet.air_quality_raw,
            packet.sound_avg,
            packet.supply_voltage,
            rssi_dbm,
            snr_db,
            f" flags={flags}" if flags else "",
        )

        self.alerts.evaluate(packet, when)
        return ProcessResult(True, "stored", packet.node_id, packet.sequence_number, seq.lost, reading_id)
