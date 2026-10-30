"""SX1278 / Ra-02 LoRa receiver driver for the Raspberry Pi (spidev + gpiozero).

Register settings mirror the sandeepmistry Arduino LoRa library used on the
ESP32 nodes, so both ends agree on modem configuration.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from .config import RadioConfig

log = logging.getLogger(__name__)

# Registers
REG_FIFO = 0x00
REG_OP_MODE = 0x01
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_LNA = 0x0C
REG_FIFO_ADDR_PTR = 0x0D
REG_FIFO_TX_BASE_ADDR = 0x0E
REG_FIFO_RX_BASE_ADDR = 0x0F
REG_FIFO_RX_CURRENT_ADDR = 0x10
REG_IRQ_FLAGS = 0x12
REG_RX_NB_BYTES = 0x13
REG_PKT_SNR_VALUE = 0x19
REG_PKT_RSSI_VALUE = 0x1A
REG_HOP_CHANNEL = 0x1C
REG_MODEM_CONFIG_1 = 0x1D
REG_MODEM_CONFIG_2 = 0x1E
REG_PREAMBLE_MSB = 0x20
REG_PREAMBLE_LSB = 0x21
REG_MODEM_CONFIG_3 = 0x26
REG_DETECTION_OPTIMIZE = 0x31
REG_DETECTION_THRESHOLD = 0x37
REG_SYNC_WORD = 0x39
REG_DIO_MAPPING_1 = 0x40
REG_VERSION = 0x42

# Modes
MODE_LONG_RANGE = 0x80
MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_RX_CONTINUOUS = 0x05

# IRQ flags
IRQ_RX_DONE = 0x40
IRQ_PAYLOAD_CRC_ERROR = 0x20
IRQ_VALID_HEADER = 0x10
CRC_ON_PAYLOAD = 0x40  # RegHopChannel bit 6

SX1278_VERSION = 0x12
FXOSC = 32_000_000

BANDWIDTH_CODES = {
    7800: 0, 10400: 1, 15600: 2, 20800: 3, 31250: 4,
    41700: 5, 62500: 6, 125000: 7, 250000: 8, 500000: 9,
}


class RadioError(RuntimeError):
    pass


@dataclass(frozen=True)
class RadioPacket:
    payload: bytes
    rssi_dbm: float
    snr_db: float
    crc_error: bool


def frf_register(frequency_hz: int) -> int:
    return (frequency_hz << 19) // FXOSC


def low_data_rate_optimize(spreading_factor: int, bandwidth_hz: int) -> bool:
    """Required when symbol duration exceeds 16 ms (same rule as Arduino LoRa)."""
    symbol_ms = 1000.0 * (1 << spreading_factor) / bandwidth_hz
    return symbol_ms > 16.0


def packet_rssi(pkt_rssi_value: int, snr_db: float, frequency_hz: int) -> float:
    """Packet RSSI per SX1276/77/78 datasheet section 5.5.5."""
    offset = -164 if frequency_hz < 525_000_000 else -157
    if snr_db < 0:
        return offset + pkt_rssi_value + snr_db
    return offset + pkt_rssi_value * 16.0 / 15.0


def to_signed8(value: int) -> int:
    return value - 256 if value > 127 else value


class SX1278:
    def __init__(self, config: RadioConfig, spi=None, reset=None, dio0=None):
        self.config = config
        self._spi = spi
        self._reset = reset
        self._dio0 = dio0
        self.version: int | None = None

    # ------------------------------------------------------------- low level
    def _read(self, register: int) -> int:
        return self._spi.xfer2([register & 0x7F, 0x00])[1]

    def _write(self, register: int, value: int) -> None:
        self._spi.xfer2([register | 0x80, value & 0xFF])

    def _read_burst(self, register: int, length: int) -> bytes:
        if length == 0:
            return b""
        return bytes(self._spi.xfer2([register & 0x7F] + [0x00] * length)[1:])

    def _set_mode(self, mode: int) -> None:
        self._write(REG_OP_MODE, MODE_LONG_RANGE | mode)

    # ----------------------------------------------------------------- setup
    def open(self) -> None:
        if self._spi is None:
            import spidev  # Raspberry Pi only

            self._spi = spidev.SpiDev()
            self._spi.open(self.config.spi_bus, self.config.spi_device)
            self._spi.max_speed_hz = self.config.spi_speed_hz
            self._spi.mode = 0
        if self._reset is None or self._dio0 is None:
            from gpiozero import DigitalInputDevice, DigitalOutputDevice  # Raspberry Pi only

            if self._reset is None:
                self._reset = DigitalOutputDevice(self.config.reset_pin, initial_value=True)
            if self._dio0 is None:
                self._dio0 = DigitalInputDevice(self.config.dio0_pin, pull_up=None, active_state=True)

        self.hardware_reset()
        self.version = self._read(REG_VERSION)
        if self.version != SX1278_VERSION:
            raise RadioError(
                f"SX1278 not detected (version register 0x{self.version:02X}, expected 0x12). "
                "Check 3.3 V power, SPI wiring, NSS on CE0 and that SPI is enabled."
            )
        self.configure()
        log.info("SX1278 ready (version 0x%02X) %s", self.version, self.describe())

    def hardware_reset(self) -> None:
        self._reset.off()
        time.sleep(0.01)
        self._reset.on()
        time.sleep(0.01)

    def configure(self) -> None:
        cfg = self.config
        self._set_mode(MODE_SLEEP)  # LoRa bit may only change in sleep
        time.sleep(0.01)

        frf = frf_register(cfg.frequency_hz)
        self._write(REG_FRF_MSB, frf >> 16)
        self._write(REG_FRF_MID, frf >> 8)
        self._write(REG_FRF_LSB, frf)

        self._write(REG_FIFO_TX_BASE_ADDR, 0x00)
        self._write(REG_FIFO_RX_BASE_ADDR, 0x00)
        self._write(REG_LNA, self._read(REG_LNA) | 0x03)  # LNA boost HF

        config1 = (BANDWIDTH_CODES[cfg.bandwidth_hz] << 4) | ((cfg.coding_rate_denominator - 4) << 1)
        self._write(REG_MODEM_CONFIG_1, config1)  # explicit header (bit 0 = 0)

        config2 = (cfg.spreading_factor << 4) | (0x04 if cfg.crc else 0x00)
        self._write(REG_MODEM_CONFIG_2, config2)

        config3 = 0x04  # AGC auto
        if low_data_rate_optimize(cfg.spreading_factor, cfg.bandwidth_hz):
            config3 |= 0x08
        self._write(REG_MODEM_CONFIG_3, config3)

        self._write(REG_DETECTION_OPTIMIZE, (self._read(REG_DETECTION_OPTIMIZE) & 0xF8) | 0x03)
        self._write(REG_DETECTION_THRESHOLD, 0x0A)  # SF7..SF12

        self._write(REG_PREAMBLE_MSB, (cfg.preamble_length >> 8) & 0xFF)
        self._write(REG_PREAMBLE_LSB, cfg.preamble_length & 0xFF)
        self._write(REG_SYNC_WORD, cfg.sync_word)
        self._write(REG_DIO_MAPPING_1, 0x00)  # DIO0 = RxDone

        self._set_mode(MODE_STDBY)
        self._write(REG_IRQ_FLAGS, 0xFF)
        self._set_mode(MODE_RX_CONTINUOUS)

    def describe(self) -> str:
        c = self.config
        return (
            f"{c.frequency_hz / 1e6:.3f} MHz BW {c.bandwidth_hz / 1000:g} kHz SF{c.spreading_factor} "
            f"CR 4/{c.coding_rate_denominator} preamble {c.preamble_length} sync 0x{c.sync_word:02X} "
            f"CRC {'on' if c.crc else 'off'}"
        )

    # --------------------------------------------------------------- receive
    def _wait_for_dio0(self, timeout: float) -> bool:
        if self._dio0 is not None and hasattr(self._dio0, "wait_for_active"):
            return bool(self._dio0.wait_for_active(timeout=timeout))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._read(REG_IRQ_FLAGS) & IRQ_RX_DONE:
                return True
            time.sleep(0.01)
        return False

    def receive(self, timeout: float = 1.0) -> RadioPacket | None:
        if not self._wait_for_dio0(timeout):
            # DIO0 edges can be missed; the IRQ register is authoritative.
            if not self._read(REG_IRQ_FLAGS) & IRQ_RX_DONE:
                self._ensure_rx_mode()
                return None

        irq = self._read(REG_IRQ_FLAGS)
        self._write(REG_IRQ_FLAGS, 0xFF)
        if not irq & IRQ_RX_DONE:
            return None

        crc_error = bool(irq & IRQ_PAYLOAD_CRC_ERROR)
        if self.config.crc and not self._read(REG_HOP_CHANNEL) & CRC_ON_PAYLOAD:
            crc_error = True  # sender did not include a CRC

        length = self._read(REG_RX_NB_BYTES)
        self._write(REG_FIFO_ADDR_PTR, self._read(REG_FIFO_RX_CURRENT_ADDR))
        payload = self._read_burst(REG_FIFO, length)

        snr = to_signed8(self._read(REG_PKT_SNR_VALUE)) / 4.0
        rssi = packet_rssi(self._read(REG_PKT_RSSI_VALUE), snr, self.config.frequency_hz)
        return RadioPacket(payload, round(rssi, 1), snr, crc_error)

    def _ensure_rx_mode(self) -> None:
        mode = self._read(REG_OP_MODE)
        if mode != (MODE_LONG_RANGE | MODE_RX_CONTINUOUS):
            log.warning("Radio left RX mode (RegOpMode=0x%02X); re-entering RX continuous", mode)
            self._set_mode(MODE_RX_CONTINUOUS)

    def health_check(self) -> bool:
        return self._read(REG_VERSION) == SX1278_VERSION

    def close(self) -> None:
        try:
            if self._spi is not None:
                self._set_mode(MODE_SLEEP)
                self._spi.close()
        finally:
            for device in (self._reset, self._dio0):
                if device is not None and hasattr(device, "close"):
                    device.close()
