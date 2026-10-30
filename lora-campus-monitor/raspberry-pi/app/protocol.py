"""Binary packet protocol v1 (must match esp32-node/include/packet_builder.h).

33 bytes, little-endian; see docs/packet_protocol.md.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = 0x4C
PROTOCOL_VERSION = 1
PACKET_SIZE = 33

INVALID_I16 = -32768
INVALID_U16 = 0xFFFF
INVALID_U32 = 0xFFFFFFFF

_BODY = struct.Struct("<BBBIIhHHIHHHHH")  # everything except the CRC
_CRC = struct.Struct("<H")
assert _BODY.size + _CRC.size == PACKET_SIZE

# Status flag bits (packet::StatusFlag in firmware).
FLAG_BME280_ERROR = 1 << 0
FLAG_BH1750_ERROR = 1 << 1
FLAG_MQ135_WARMUP = 1 << 2
FLAG_MQ135_SATURATED = 1 << 3
FLAG_SOUND_SATURATED = 1 << 4
FLAG_SUPPLY_LOW = 1 << 5
FLAG_SUPPLY_NOT_MONITORED = 1 << 6
FLAG_BME280_OUT_OF_RANGE = 1 << 7
FLAG_BH1750_OUT_OF_RANGE = 1 << 8
FLAG_LAST_TX_FAILED = 1 << 9
FLAG_BOOT = 1 << 10
# Set by the Pi validator (upper byte, never sent by nodes).
FLAG_PI_RANGE_REJECTED = 1 << 15

FLAG_NAMES = {
    FLAG_BME280_ERROR: "BME280 error",
    FLAG_BH1750_ERROR: "BH1750 error",
    FLAG_MQ135_WARMUP: "MQ-135 warm-up",
    FLAG_MQ135_SATURATED: "MQ-135 saturated",
    FLAG_SOUND_SATURATED: "Sound saturated",
    FLAG_SUPPLY_LOW: "Supply low",
    FLAG_SUPPLY_NOT_MONITORED: "Supply not monitored",
    FLAG_BME280_OUT_OF_RANGE: "BME280 out of range",
    FLAG_BH1750_OUT_OF_RANGE: "BH1750 out of range",
    FLAG_LAST_TX_FAILED: "Previous TX failed",
    FLAG_BOOT: "Node boot",
    FLAG_PI_RANGE_REJECTED: "Value rejected by main node",
}


class ProtocolError(ValueError):
    """Raised for malformed packets. ``reason`` is a short machine code."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class Packet:
    protocol_version: int
    node_id: int
    sequence_number: int
    uptime_seconds: int
    temperature_c: float | None
    humidity_percent: float | None
    pressure_hpa: float | None
    light_lux: float | None
    air_quality_raw: int | None
    sound_avg: int | None
    sound_peak: int | None
    supply_voltage: float | None
    status_flags: int


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def _or_none(value: int, invalid: int, scale: float | None = None):
    if value == invalid:
        return None
    return value / scale if scale else value


def decode(data: bytes) -> Packet:
    if len(data) != PACKET_SIZE:
        raise ProtocolError("bad_length", f"Expected {PACKET_SIZE} bytes, got {len(data)}")
    if data[0] != MAGIC:
        raise ProtocolError("bad_magic", f"Bad magic byte 0x{data[0]:02X}")
    if data[1] != PROTOCOL_VERSION:
        raise ProtocolError("bad_version", f"Unsupported protocol version {data[1]}")
    (expected_crc,) = _CRC.unpack_from(data, _BODY.size)
    actual_crc = crc16_ccitt(data[: _BODY.size])
    if expected_crc != actual_crc:
        raise ProtocolError("bad_crc", f"CRC mismatch: packet 0x{expected_crc:04X}, computed 0x{actual_crc:04X}")

    (
        _magic,
        version,
        node_id,
        seq,
        uptime,
        temp,
        hum,
        pres,
        lux,
        air,
        snd_avg,
        snd_peak,
        supply_mv,
        flags,
    ) = _BODY.unpack_from(data)

    supply = _or_none(supply_mv, INVALID_U16)
    return Packet(
        protocol_version=version,
        node_id=node_id,
        sequence_number=seq,
        uptime_seconds=uptime,
        temperature_c=_or_none(temp, INVALID_I16, 100.0),
        humidity_percent=_or_none(hum, INVALID_U16, 100.0),
        pressure_hpa=_or_none(pres, INVALID_U16, 10.0),
        light_lux=_or_none(lux, INVALID_U32, 100.0),
        air_quality_raw=_or_none(air, INVALID_U16),
        sound_avg=_or_none(snd_avg, INVALID_U16),
        sound_peak=_or_none(snd_peak, INVALID_U16),
        supply_voltage=None if supply is None else supply / 1000.0,
        status_flags=flags,
    )


def _scaled(value: float | None, scale: float, invalid: int, lo: int, hi: int) -> int:
    if value is None:
        return invalid
    scaled = round(value * scale)
    return scaled if lo <= scaled <= hi else invalid


def encode(packet: Packet) -> bytes:
    """Encode a packet exactly like the firmware (used by the simulator and tests)."""
    supply_mv = INVALID_U16 if packet.supply_voltage is None else round(packet.supply_voltage * 1000)
    body = _BODY.pack(
        MAGIC,
        packet.protocol_version,
        packet.node_id,
        packet.sequence_number & 0xFFFFFFFF,
        packet.uptime_seconds & 0xFFFFFFFF,
        _scaled(packet.temperature_c, 100, INVALID_I16, -32767, 32767),
        _scaled(packet.humidity_percent, 100, INVALID_U16, 0, 0xFFFE),
        _scaled(packet.pressure_hpa, 10, INVALID_U16, 0, 0xFFFE),
        _scaled(packet.light_lux, 100, INVALID_U32, 0, 0xFFFFFFFE),
        INVALID_U16 if packet.air_quality_raw is None else packet.air_quality_raw,
        INVALID_U16 if packet.sound_avg is None else packet.sound_avg,
        INVALID_U16 if packet.sound_peak is None else packet.sound_peak,
        min(supply_mv, INVALID_U16),
        packet.status_flags & 0xFFFF,
    )
    return body + _CRC.pack(crc16_ccitt(body))


def flag_names(flags: int) -> list[str]:
    return [name for bit, name in FLAG_NAMES.items() if flags & bit]
