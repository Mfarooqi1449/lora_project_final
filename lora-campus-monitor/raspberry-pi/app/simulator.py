"""Simulated radio for demonstrations and testing without LoRa hardware.

Produces protocol-correct packets for each configured node at the firmware's
slot timing, with occasional packet loss and corruption.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

from .protocol import FLAG_BOOT, FLAG_MQ135_WARMUP, PROTOCOL_VERSION, Packet, encode
from .sx1278 import RadioPacket


@dataclass
class _SimNode:
    node_id: int
    next_due: float
    sequence: int = 0
    boot_time: float = field(default_factory=time.monotonic)


class SimulatedRadio:
    version = 0x12

    def __init__(
        self,
        node_ids: list[int],
        period_s: float = 60.0,
        loss_probability: float = 0.03,
        corrupt_probability: float = 0.01,
        seed: int | None = None,
    ):
        self.period_s = period_s
        self.loss_probability = loss_probability
        self.corrupt_probability = corrupt_probability
        self.rng = random.Random(seed)
        now = time.monotonic()
        self.nodes = [
            _SimNode(node_id, now + ((10 + (node_id - 1) * 30) % 60) * period_s / 60.0)
            for node_id in node_ids
        ]

    def open(self) -> None:
        pass

    def close(self) -> None:
        pass

    def health_check(self) -> bool:
        return True

    def describe(self) -> str:
        return f"SIMULATED radio, {len(self.nodes)} node(s), period {self.period_s:g} s"

    def _make_packet(self, node: _SimNode) -> Packet:
        uptime = int(time.monotonic() - node.boot_time)
        hour = time.localtime().tm_hour + time.localtime().tm_min / 60.0
        day = math.sin((hour - 6) / 24 * 2 * math.pi)  # peaks mid-afternoon
        offset = node.node_id - 1
        flags = FLAG_BOOT if node.sequence == 0 else 0
        if uptime < 180:
            flags |= FLAG_MQ135_WARMUP
        r = self.rng
        return Packet(
            protocol_version=PROTOCOL_VERSION,
            node_id=node.node_id,
            sequence_number=node.sequence,
            uptime_seconds=uptime,
            temperature_c=round(27 + 5 * day + offset + r.gauss(0, 0.2), 2),
            humidity_percent=round(min(100, max(0, 60 - 15 * day + r.gauss(0, 1))), 2),
            pressure_hpa=round(1008 + r.gauss(0, 0.3), 1),
            light_lux=round(max(0.0, 400 * max(day, 0) + r.gauss(0, 5)), 2),
            air_quality_raw=int(1200 + 150 * offset + r.gauss(0, 40)),
            sound_avg=int(max(0, 120 + r.gauss(0, 40))),
            sound_peak=int(max(0, 700 + r.gauss(0, 150))),
            supply_voltage=round(5.02 + r.gauss(0, 0.02), 3),
            status_flags=flags,
        )

    def receive(self, timeout: float = 1.0) -> RadioPacket | None:
        deadline = time.monotonic() + timeout
        while True:
            now = time.monotonic()
            due = min(self.nodes, key=lambda n: n.next_due)
            if due.next_due <= now:
                due.next_due += self.period_s
                payload = encode(self._make_packet(due))
                due.sequence += 1
                if self.rng.random() < self.loss_probability:
                    continue
                crc_error = self.rng.random() < self.corrupt_probability
                rssi = round(-70 - 25 * (due.node_id - 1) + self.rng.gauss(0, 2), 1)
                snr = round(9.5 - 3 * (due.node_id - 1) + self.rng.gauss(0, 0.5), 2)
                return RadioPacket(payload, rssi, snr, crc_error)
            if now >= deadline:
                return None
            time.sleep(min(0.05, deadline - now, max(0.0, due.next_due - now)))
