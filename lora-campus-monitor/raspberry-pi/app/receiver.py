"""LoRa receiver service: radio -> packet pipeline -> SQLite, plus periodic
offline checks, health heartbeat and data retention.

Run:  python -m app.receiver               (real SX1278 radio)
      python -m app.receiver --simulate    (no hardware)
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time

from . import __version__
from .alerts import AlertEngine
from .config import Config, load_config
from .database import Database, to_iso, utc_now
from .health import cpu_temperature_c
from .logging_setup import setup_logging
from .processor import PacketProcessor
from .simulator import SimulatedRadio
from .sx1278 import SX1278, RadioError

log = logging.getLogger("app.receiver")

OFFLINE_CHECK_INTERVAL_S = 10
RETENTION_INTERVAL_S = 24 * 3600
RADIO_RETRY_INTERVAL_S = 30


class Receiver:
    def __init__(self, config: Config, radio, db: Database):
        self.config = config
        self.radio = radio
        self.db = db
        self.running = True
        self.radio_ok = False
        self.started_at = utc_now()
        self.alerts = AlertEngine(db, config.alerts, config.receiver.offline_timeout_s, self.started_at)
        self.processor = PacketProcessor(db, self.alerts)
        self._last_offline_check = 0.0
        self._last_heartbeat = 0.0
        self._last_retention = 0.0
        self._last_radio_attempt = 0.0

    def stop(self, *_args) -> None:
        self.running = False

    def _open_radio(self) -> None:
        self._last_radio_attempt = time.monotonic()
        try:
            self.radio.open()
            self.radio_ok = True
            self.db.log_event("radio_ready", self.radio.describe())
        except Exception as exc:  # RadioError, SPI/GPIO errors, missing libraries
            if not isinstance(exc, (RadioError, OSError, ImportError)):
                log.debug("Radio init exception", exc_info=True)
            self.radio_ok = False
            log.error("Radio initialisation failed: %s", exc)
            self.db.log_event("radio_error", str(exc))

    def heartbeat(self) -> None:
        stats = self.processor.stats
        self.db.set_status(
            {
                "receiver_version": __version__,
                "receiver_started_at": to_iso(self.started_at),
                "receiver_heartbeat": to_iso(utc_now()),
                "radio_ok": int(self.radio_ok),
                "radio_settings": self.radio.describe(),
                "packets_received": stats["received"],
                "packets_stored": stats["stored"],
                "packets_rejected": stats["rejected"],
                "packets_duplicate": stats["duplicates"],
                "cpu_temperature_c": cpu_temperature_c(),
            }
        )

    def periodic(self) -> None:
        now = time.monotonic()
        if now - self._last_offline_check >= OFFLINE_CHECK_INTERVAL_S:
            self._last_offline_check = now
            self.alerts.check_offline(self.db.get_nodes())
        if now - self._last_heartbeat >= self.config.receiver.health_interval_s:
            self._last_heartbeat = now
            if self.radio_ok and not self.radio.health_check():
                log.error("Radio stopped responding; will re-initialise")
                self.db.log_event("radio_error", "Radio stopped responding")
                self.radio_ok = False
            self.heartbeat()
        days = self.config.database.retention_days
        if days > 0 and now - self._last_retention >= RETENTION_INTERVAL_S:
            self._last_retention = now
            removed = self.db.purge_older_than(days)
            if removed:
                self.db.log_event("retention", f"Deleted {removed} readings older than {days} days")
        if not self.radio_ok and now - self._last_radio_attempt >= RADIO_RETRY_INTERVAL_S:
            self._open_radio()

    def run(self) -> int:
        self.db.log_event("receiver_started", f"version {__version__}, {self.radio.describe()}")
        self._open_radio()
        self.heartbeat()
        try:
            while self.running:
                if self.radio_ok:
                    try:
                        packet = self.radio.receive(timeout=1.0)
                    except OSError as exc:
                        log.error("Radio read failed: %s", exc)
                        self.db.log_event("radio_error", f"read failed: {exc}")
                        self.radio_ok = False
                        packet = None
                    if packet is not None:
                        self.processor.handle(packet.payload, packet.rssi_dbm, packet.snr_db, packet.crc_error)
                else:
                    time.sleep(1.0)
                self.periodic()
        finally:
            self.db.set_status({"radio_ok": 0, "receiver_heartbeat": None})
            self.db.log_event("receiver_stopped", "clean shutdown")
            try:
                self.radio.close()
            except Exception as exc:  # shutdown must not raise
                log.warning("Radio close failed: %s", exc)
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoRa campus monitor receiver")
    parser.add_argument("--config", help="path to config.toml")
    parser.add_argument("--simulate", action="store_true", help="use simulated nodes instead of the SX1278")
    parser.add_argument("--sim-period", type=float, default=60.0, help="simulated transmit period in seconds")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    setup_logging(config.receiver.log_level, config.receiver.log_file)
    log.info("Starting receiver %s with config %s", __version__, config.source)

    db = Database(config.database.path)
    db.init_schema()
    db.sync_nodes(config.nodes)

    if args.simulate:
        radio = SimulatedRadio([n.node_id for n in config.nodes if n.enabled], period_s=args.sim_period)
    else:
        radio = SX1278(config.radio)

    receiver = Receiver(config, radio, db)
    signal.signal(signal.SIGTERM, receiver.stop)
    signal.signal(signal.SIGINT, receiver.stop)
    try:
        return receiver.run()
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
