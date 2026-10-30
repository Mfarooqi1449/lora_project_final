import shutil
import subprocess
from pathlib import Path

import pytest

from app.protocol import (
    FLAG_BOOT,
    FLAG_MQ135_WARMUP,
    PACKET_SIZE,
    ProtocolError,
    crc16_ccitt,
    decode,
    encode,
    flag_names,
)
from conftest import make_packet

FIRMWARE_DIR = Path(__file__).resolve().parents[2] / "esp32-node"


def test_crc_check_value():
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_roundtrip():
    packet = make_packet()
    raw = encode(packet)
    assert len(raw) == PACKET_SIZE
    assert decode(raw) == packet


def test_invalid_values_roundtrip_as_none():
    packet = make_packet(
        temperature_c=None, humidity_percent=None, pressure_hpa=None, light_lux=None,
        air_quality_raw=None, sound_avg=None, sound_peak=None, supply_voltage=None,
    )
    assert decode(encode(packet)) == packet


def test_negative_temperature():
    assert decode(encode(make_packet(temperature_c=-12.34))).temperature_c == -12.34


@pytest.mark.parametrize(
    "mutate, reason",
    [
        (lambda b: b[:-1], "bad_length"),
        (lambda b: b"\x00" + b[1:], "bad_magic"),
        (lambda b: b[:1] + b"\x09" + b[2:], "bad_version"),
        (lambda b: b[:20] + bytes([b[20] ^ 0xFF]) + b[21:], "bad_crc"),
    ],
)
def test_rejects_malformed(mutate, reason):
    with pytest.raises(ProtocolError) as exc:
        decode(mutate(encode(make_packet())))
    assert exc.value.reason == reason


def test_flag_names():
    assert flag_names(FLAG_BOOT | FLAG_MQ135_WARMUP) == ["MQ-135 warm-up", "Node boot"]


@pytest.mark.skipif(shutil.which("g++") is None or shutil.which("make") is None, reason="needs g++ and make")
def test_matches_firmware_encoder():
    """The C++ firmware encoder and the Python decoder must agree byte-for-byte."""
    subprocess.run(["make", "-s", "run_tests"], cwd=FIRMWARE_DIR / "test_host", check=True)
    out = subprocess.run(
        ["./run_tests", "--vector"], cwd=FIRMWARE_DIR / "test_host", check=True, capture_output=True, text=True
    ).stdout.strip()
    packet = decode(bytes.fromhex(out))
    assert packet.node_id == 2
    assert packet.sequence_number == 123456
    assert packet.uptime_seconds == 7890
    assert packet.temperature_c == -12.34
    assert packet.humidity_percent == 56.78
    assert packet.pressure_hpa == 1013.2
    assert packet.light_lux == 345.67
    assert packet.air_quality_raw == 1500
    assert packet.sound_avg == 42
    assert packet.sound_peak == 900
    assert packet.supply_voltage == 4.987
    assert packet.status_flags == FLAG_MQ135_WARMUP | FLAG_BOOT
    assert encode(packet).hex().upper() == out
