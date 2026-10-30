from app.config import RadioConfig
from app.protocol import encode
from app.sx1278 import (
    IRQ_PAYLOAD_CRC_ERROR,
    IRQ_RX_DONE,
    REG_FIFO,
    REG_FIFO_ADDR_PTR,
    REG_FIFO_RX_CURRENT_ADDR,
    REG_HOP_CHANNEL,
    REG_IRQ_FLAGS,
    REG_MODEM_CONFIG_1,
    REG_MODEM_CONFIG_2,
    REG_MODEM_CONFIG_3,
    REG_OP_MODE,
    REG_PKT_RSSI_VALUE,
    REG_PKT_SNR_VALUE,
    REG_RX_NB_BYTES,
    REG_SYNC_WORD,
    REG_VERSION,
    SX1278,
    frf_register,
    low_data_rate_optimize,
    packet_rssi,
)
from conftest import make_packet


class FakeSPI:
    """Register-level model of the SX1278 sufficient for the driver."""

    def __init__(self, version=0x12):
        self.regs = [0] * 0x80
        self.regs[REG_VERSION] = version
        self.fifo = [0] * 256
        self.fifo_ptr = 0

    def xfer2(self, data):
        reg = data[0] & 0x7F
        if data[0] & 0x80:  # write
            value = data[1]
            if reg == REG_IRQ_FLAGS:
                self.regs[reg] &= ~value & 0xFF  # write-1-to-clear
            elif reg == REG_FIFO_ADDR_PTR:
                self.fifo_ptr = value
                self.regs[reg] = value
            else:
                self.regs[reg] = value
            return [0, 0]
        if reg == REG_FIFO:
            out = [0]
            for _ in data[1:]:
                out.append(self.fifo[self.fifo_ptr])
                self.fifo_ptr = (self.fifo_ptr + 1) & 0xFF
            return out
        return [0, self.regs[reg]]

    def deliver(self, payload: bytes, crc_error=False, crc_present=True, pkt_rssi=90, snr_raw=30):
        base = 0x20
        for i, b in enumerate(payload):
            self.fifo[base + i] = b
        self.regs[REG_FIFO_RX_CURRENT_ADDR] = base
        self.regs[REG_RX_NB_BYTES] = len(payload)
        self.regs[REG_IRQ_FLAGS] = IRQ_RX_DONE | (IRQ_PAYLOAD_CRC_ERROR if crc_error else 0)
        self.regs[REG_HOP_CHANNEL] = 0x40 if crc_present else 0
        self.regs[REG_PKT_RSSI_VALUE] = pkt_rssi
        self.regs[REG_PKT_SNR_VALUE] = snr_raw & 0xFF

    def close(self):
        pass


class FakePin:
    def __init__(self):
        self.value = 1

    def on(self):
        self.value = 1

    def off(self):
        self.value = 0

    def close(self):
        pass


def make_radio(spi):
    radio = SX1278(RadioConfig(), spi=spi, reset=FakePin(), dio0=object())
    radio.open()
    return radio


def test_configuration_registers():
    spi = FakeSPI()
    make_radio(spi)
    assert spi.regs[REG_MODEM_CONFIG_1] == 0x72  # BW125, CR4/5, explicit header
    assert spi.regs[REG_MODEM_CONFIG_2] == 0x74  # SF7, CRC on
    assert spi.regs[REG_MODEM_CONFIG_3] == 0x04  # AGC on, no LDRO at SF7
    assert spi.regs[REG_SYNC_WORD] == 0x12
    assert spi.regs[REG_OP_MODE] == 0x85  # LoRa + RX continuous
    assert (spi.regs[0x06], spi.regs[0x07], spi.regs[0x08]) == (0x6C, 0x40, 0x00)  # 433 MHz


def test_wrong_version_raises():
    import pytest

    from app.sx1278 import RadioError

    with pytest.raises(RadioError):
        make_radio(FakeSPI(version=0x00))


def test_receive_packet():
    spi = FakeSPI()
    radio = make_radio(spi)
    payload = encode(make_packet())
    spi.deliver(payload, pkt_rssi=90, snr_raw=30)
    pkt = radio.receive(timeout=0.05)
    assert pkt.payload == payload
    assert pkt.snr_db == 7.5
    assert pkt.rssi_dbm == round(-164 + 90 * 16 / 15, 1)
    assert not pkt.crc_error
    assert spi.regs[REG_IRQ_FLAGS] == 0
    assert radio.receive(timeout=0.02) is None


def test_crc_error_and_missing_crc_flagged():
    spi = FakeSPI()
    radio = make_radio(spi)
    spi.deliver(b"abc", crc_error=True)
    assert radio.receive(timeout=0.05).crc_error
    spi.deliver(b"abc", crc_present=False)
    assert radio.receive(timeout=0.05).crc_error


def test_helpers():
    assert frf_register(433_000_000) == 0x6C4000
    assert not low_data_rate_optimize(7, 125_000)
    assert low_data_rate_optimize(12, 125_000)
    assert packet_rssi(50, -4.0, 433_000_000) == -164 + 50 - 4.0
