"""Alert engine: consecutive-sample debounce, hysteresis and offline detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from .config import AlertConfig, AlertRule
from .database import Database, parse_iso, utc_now
from .protocol import (
    FLAG_BH1750_ERROR,
    FLAG_BH1750_OUT_OF_RANGE,
    FLAG_BME280_ERROR,
    FLAG_BME280_OUT_OF_RANGE,
    FLAG_MQ135_WARMUP,
    Packet,
)

NODE_OFFLINE = "node_offline"
SENSOR_FAILURES = {
    "sensor_failure_bme280": ("BME280", FLAG_BME280_ERROR | FLAG_BME280_OUT_OF_RANGE),
    "sensor_failure_bh1750": ("BH1750", FLAG_BH1750_ERROR | FLAG_BH1750_OUT_OF_RANGE),
}

# Rule metric name -> Packet attribute.
_PACKET_FIELDS = {"sound_raw": "sound_avg"}

log = logging.getLogger(__name__)


@dataclass
class _Counter:
    bad: int = 0
    good: int = 0


class AlertEngine:
    def __init__(self, db: Database, config: AlertConfig, offline_timeout_s: int, started_at: datetime | None = None):
        self.db = db
        self.rules = tuple(r for r in config.rules if r.enabled)
        self.required = config.consecutive_samples
        self.offline_timeout_s = offline_timeout_s
        self.started_at = started_at or utc_now()
        self._counters: dict[tuple[int, str], _Counter] = {}
        self._active: dict[tuple[int, str], int] = {
            (a["node_id"], a["alert_type"]): a["id"] for a in db.active_alerts()
        }

    # ----------------------------------------------------------------- public
    def evaluate(self, packet: Packet, when: datetime | None = None) -> list[str]:
        """Process one stored reading. Returns human-readable change messages."""
        when = when or utc_now()
        node = packet.node_id
        changes: list[str] = []

        if (node, NODE_OFFLINE) in self._active:
            changes += self._clear(node, NODE_OFFLINE, when)

        for rule in self.rules:
            value = getattr(packet, _PACKET_FIELDS.get(rule.metric, rule.metric))
            if value is None:
                continue
            if rule.metric == "air_quality_raw" and packet.status_flags & FLAG_MQ135_WARMUP:
                continue
            changes += self._rule_sample(node, rule, float(value), when)

        for alert_type, (sensor, mask) in SENSOR_FAILURES.items():
            failing = bool(packet.status_flags & mask)
            changes += self._update(
                node,
                alert_type,
                violating=failing,
                recovered=not failing,
                when=when,
                measured=float(packet.status_flags),
                threshold=None,
                severity="critical",
                message=f"{sensor} sensor not responding or out of range",
            )
        return changes

    def check_offline(self, nodes: list[dict], now: datetime | None = None) -> list[str]:
        now = now or utc_now()
        changes: list[str] = []
        for node in nodes:
            node_id = node["node_id"]
            key = (node_id, NODE_OFFLINE)
            if not node["enabled"]:
                if key in self._active:
                    changes += self._clear(node_id, NODE_OFFLINE, now)
                continue
            reference = parse_iso(node["last_seen"]) if node["last_seen"] else self.started_at
            age = (now - reference).total_seconds()
            if age > self.offline_timeout_s and key not in self._active:
                seen = node["last_seen"] or "never"
                changes += self._open(
                    node_id,
                    NODE_OFFLINE,
                    measured=round(age),
                    threshold=self.offline_timeout_s,
                    severity="critical",
                    message=f"No packet for {round(age)} s (last seen {seen})",
                    when=now,
                )
        return changes

    def active_keys(self) -> set[tuple[int, str]]:
        return set(self._active)

    # --------------------------------------------------------------- internal
    def _rule_sample(self, node: int, rule: AlertRule, value: float, when: datetime) -> list[str]:
        if rule.direction == "high":
            violating, recovered = value > rule.threshold, value < rule.clear
            symbol = ">"
        else:
            violating, recovered = value < rule.threshold, value > rule.clear
            symbol = "<"
        return self._update(
            node,
            rule.type,
            violating=violating,
            recovered=recovered,
            when=when,
            measured=value,
            threshold=rule.threshold,
            severity=rule.severity,
            message=f"{rule.metric} {value:g} {symbol} {rule.threshold:g}",
        )

    def _update(
        self,
        node: int,
        alert_type: str,
        *,
        violating: bool,
        recovered: bool,
        when: datetime,
        measured: float | None,
        threshold: float | None,
        severity: str,
        message: str,
    ) -> list[str]:
        key = (node, alert_type)
        counter = self._counters.setdefault(key, _Counter())
        if key in self._active:
            counter.bad = 0
            counter.good = counter.good + 1 if recovered else 0
            if counter.good >= self.required:
                counter.good = 0
                return self._clear(node, alert_type, when)
        else:
            counter.good = 0
            counter.bad = counter.bad + 1 if violating else 0
            if counter.bad >= self.required:
                counter.bad = 0
                return self._open(node, alert_type, measured, threshold, severity, message, when)
        return []

    def _open(self, node, alert_type, measured, threshold, severity, message, when) -> list[str]:
        alert_id = self.db.open_alert(node, alert_type, measured, threshold, severity, message, when)
        if alert_id is None:  # already active in DB (e.g. opened by a previous run)
            existing = [a for a in self.db.active_alerts(node) if a["alert_type"] == alert_type]
            if existing:
                self._active[(node, alert_type)] = existing[0]["id"]
            return []
        self._active[(node, alert_type)] = alert_id
        text = f"ALERT OPEN node {node} {alert_type} [{severity}]: {message}"
        log.warning(text)
        self.db.log_event("alert_opened", text, when)
        return [text]

    def _clear(self, node: int, alert_type: str, when: datetime) -> list[str]:
        alert_id = self._active.pop((node, alert_type), None)
        self._counters.pop((node, alert_type), None)
        if alert_id is None or not self.db.clear_alert(alert_id, when):
            return []
        text = f"ALERT CLEARED node {node} {alert_type}"
        log.info(text)
        self.db.log_event("alert_cleared", text, when)
        return [text]
