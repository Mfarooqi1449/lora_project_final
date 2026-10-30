"""Duplicate, packet-loss and node-reboot detection from sequence numbers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .protocol import FLAG_BOOT

# Gaps larger than this are treated as a node reset rather than real loss.
MAX_PLAUSIBLE_GAP = 10_000
# Tolerance when deciding whether two packets with equal sequence are duplicates.
DUPLICATE_UPTIME_TOLERANCE_S = 5


class SequenceStatus(str, Enum):
    FIRST = "first"
    OK = "ok"
    GAP = "gap"
    DUPLICATE = "duplicate"
    NODE_RESET = "node_reset"


@dataclass(frozen=True)
class SequenceResult:
    status: SequenceStatus
    lost: int  # packets estimated lost before this one


@dataclass
class NodeSequenceState:
    last_sequence: int | None = None
    last_uptime: int | None = None


def classify(state: NodeSequenceState, sequence: int, uptime: int, flags: int) -> SequenceResult:
    """Classify a packet against the last accepted packet of the same node.

    Does not modify ``state``; call ``accept`` after the packet is stored.
    """
    if state.last_sequence is None:
        return SequenceResult(SequenceStatus.FIRST, 0)

    last_seq = state.last_sequence
    last_uptime = state.last_uptime or 0

    if sequence == last_seq and abs(uptime - last_uptime) <= DUPLICATE_UPTIME_TOLERANCE_S:
        return SequenceResult(SequenceStatus.DUPLICATE, 0)

    rebooted = (
        flags & FLAG_BOOT
        or uptime + DUPLICATE_UPTIME_TOLERANCE_S < last_uptime
        or sequence <= last_seq
        or sequence - last_seq - 1 > MAX_PLAUSIBLE_GAP
    )
    if rebooted:
        # After a reboot the node counts from 0, so earlier numbers were lost.
        lost = sequence if sequence <= MAX_PLAUSIBLE_GAP else 0
        return SequenceResult(SequenceStatus.NODE_RESET, lost)

    gap = sequence - last_seq - 1
    if gap > 0:
        return SequenceResult(SequenceStatus.GAP, gap)
    return SequenceResult(SequenceStatus.OK, 0)


def accept(state: NodeSequenceState, sequence: int, uptime: int) -> None:
    state.last_sequence = sequence
    state.last_uptime = uptime
