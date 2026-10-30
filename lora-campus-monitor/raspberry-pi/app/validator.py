"""Main-node range validation of decoded packets.

The firmware already range-checks values, but the Pi re-validates so a faulty
node or firmware bug cannot store physically impossible data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .protocol import FLAG_PI_RANGE_REJECTED, Packet

RANGES = {
    "temperature_c": (-40.0, 85.0),
    "humidity_percent": (0.0, 100.0),
    "pressure_hpa": (300.0, 1100.0),
    "light_lux": (0.0, 120_000.0),
    "air_quality_raw": (0, 4095),
    "sound_avg": (0, 4095),
    "sound_peak": (0, 4095),
    "supply_voltage": (0.0, 6.0),
}


@dataclass(frozen=True)
class ValidationResult:
    packet: Packet
    rejected_fields: tuple[str, ...]


def validate_ranges(packet: Packet) -> ValidationResult:
    """Replace out-of-range values with None and set FLAG_PI_RANGE_REJECTED."""
    changes = {}
    for name, (lo, hi) in RANGES.items():
        value = getattr(packet, name)
        if value is not None and not lo <= value <= hi:
            changes[name] = None
    if not changes:
        return ValidationResult(packet, ())
    cleaned = replace(packet, status_flags=packet.status_flags | FLAG_PI_RANGE_REJECTED, **changes)
    return ValidationResult(cleaned, tuple(sorted(changes)))
