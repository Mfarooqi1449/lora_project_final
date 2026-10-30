"""Configuration loader (TOML)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "config.toml"

VALID_BANDWIDTHS_HZ = (7800, 10400, 15600, 20800, 31250, 41700, 62500, 125000, 250000, 500000)
METRICS = (
    "temperature_c",
    "humidity_percent",
    "pressure_hpa",
    "light_lux",
    "air_quality_raw",
    "sound_raw",
    "sound_peak",
    "supply_voltage",
)
SEVERITIES = ("info", "warning", "critical")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RadioConfig:
    frequency_hz: int = 433_000_000
    bandwidth_hz: int = 125_000
    spreading_factor: int = 7
    coding_rate_denominator: int = 5
    preamble_length: int = 8
    sync_word: int = 0x12
    crc: bool = True
    spi_bus: int = 0
    spi_device: int = 0
    spi_speed_hz: int = 5_000_000
    reset_pin: int = 25
    dio0_pin: int = 24


@dataclass(frozen=True)
class DatabaseConfig:
    path: Path = BASE_DIR / "database" / "monitor.db"
    backup_dir: Path = BASE_DIR / "database" / "backups"
    backup_keep: int = 14
    retention_days: int = 0


@dataclass(frozen=True)
class ReceiverConfig:
    offline_timeout_s: int = 180
    health_interval_s: int = 60
    log_file: Path | None = BASE_DIR / "logs" / "receiver.log"
    log_level: str = "INFO"


@dataclass(frozen=True)
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    refresh_interval_s: int = 15
    log_file: Path | None = BASE_DIR / "logs" / "dashboard.log"


@dataclass(frozen=True)
class NodeConfig:
    node_id: int
    name: str
    location: str
    enabled: bool = True


@dataclass(frozen=True)
class AlertRule:
    type: str
    metric: str
    direction: str  # "high" or "low"
    threshold: float
    clear: float
    severity: str = "warning"
    enabled: bool = True


@dataclass(frozen=True)
class AlertConfig:
    consecutive_samples: int = 3
    rules: tuple[AlertRule, ...] = ()


@dataclass(frozen=True)
class Config:
    radio: RadioConfig = field(default_factory=RadioConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    receiver: ReceiverConfig = field(default_factory=ReceiverConfig)
    web: WebConfig = field(default_factory=WebConfig)
    nodes: tuple[NodeConfig, ...] = ()
    alerts: AlertConfig = field(default_factory=AlertConfig)
    source: Path | None = None


def _resolve(path_value: str | None, base: Path) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else base / path


def _pick(section: dict, cls, allowed: set[str]) -> dict:
    unknown = set(section) - allowed
    if unknown:
        raise ConfigError(f"Unknown {cls.__name__} keys: {', '.join(sorted(unknown))}")
    return dict(section)


def _radio(section: dict) -> RadioConfig:
    radio = RadioConfig(**_pick(section, RadioConfig, set(RadioConfig.__dataclass_fields__)))
    if radio.bandwidth_hz not in VALID_BANDWIDTHS_HZ:
        raise ConfigError(f"radio.bandwidth_hz must be one of {VALID_BANDWIDTHS_HZ}")
    if not 7 <= radio.spreading_factor <= 12:
        raise ConfigError("radio.spreading_factor must be 7..12")
    if not 5 <= radio.coding_rate_denominator <= 8:
        raise ConfigError("radio.coding_rate_denominator must be 5..8")
    if not 410_000_000 <= radio.frequency_hz <= 525_000_000:
        raise ConfigError("radio.frequency_hz must be within the SX1278 band (410-525 MHz)")
    if not 0 <= radio.sync_word <= 0xFF:
        raise ConfigError("radio.sync_word must be one byte")
    if radio.preamble_length < 6:
        raise ConfigError("radio.preamble_length must be >= 6")
    return radio


def _nodes(items: list[dict]) -> tuple[NodeConfig, ...]:
    nodes = []
    seen = set()
    for item in items:
        node = NodeConfig(**_pick(item, NodeConfig, set(NodeConfig.__dataclass_fields__)))
        if not 1 <= node.node_id <= 254:
            raise ConfigError("node_id must be 1..254")
        if node.node_id in seen:
            raise ConfigError(f"Duplicate node_id {node.node_id}")
        seen.add(node.node_id)
        nodes.append(node)
    return tuple(nodes)


def _alerts(section: dict) -> AlertConfig:
    rules = []
    seen = set()
    for item in section.get("rules", []):
        rule = AlertRule(**_pick(item, AlertRule, set(AlertRule.__dataclass_fields__)))
        if rule.metric not in METRICS:
            raise ConfigError(f"Alert {rule.type}: unknown metric {rule.metric!r}")
        if rule.direction not in ("high", "low"):
            raise ConfigError(f"Alert {rule.type}: direction must be 'high' or 'low'")
        if rule.severity not in SEVERITIES:
            raise ConfigError(f"Alert {rule.type}: severity must be one of {SEVERITIES}")
        if rule.direction == "high" and rule.clear > rule.threshold:
            raise ConfigError(f"Alert {rule.type}: clear must be <= threshold for high alerts")
        if rule.direction == "low" and rule.clear < rule.threshold:
            raise ConfigError(f"Alert {rule.type}: clear must be >= threshold for low alerts")
        if rule.type in seen:
            raise ConfigError(f"Duplicate alert type {rule.type}")
        seen.add(rule.type)
        rules.append(rule)
    consecutive = int(section.get("consecutive_samples", 3))
    if consecutive < 1:
        raise ConfigError("alerts.consecutive_samples must be >= 1")
    return AlertConfig(consecutive_samples=consecutive, rules=tuple(rules))


def load_config(path: str | os.PathLike | None = None) -> Config:
    config_path = Path(path or os.environ.get("LORA_MONITOR_CONFIG") or DEFAULT_CONFIG_PATH)
    with open(config_path, "rb") as fh:
        data = tomllib.load(fh)

    base = BASE_DIR
    db = data.get("database", {})
    rx = data.get("receiver", {})
    web = data.get("web", {})

    database = DatabaseConfig(
        path=_resolve(db.get("path", "database/monitor.db"), base),
        backup_dir=_resolve(db.get("backup_dir", "database/backups"), base),
        backup_keep=int(db.get("backup_keep", 14)),
        retention_days=int(db.get("retention_days", 0)),
    )
    receiver = ReceiverConfig(
        offline_timeout_s=int(rx.get("offline_timeout_s", 180)),
        health_interval_s=int(rx.get("health_interval_s", 60)),
        log_file=_resolve(rx.get("log_file"), base),
        log_level=str(rx.get("log_level", "INFO")).upper(),
    )
    web_cfg = WebConfig(
        host=str(web.get("host", "0.0.0.0")),
        port=int(web.get("port", 5000)),
        refresh_interval_s=int(web.get("refresh_interval_s", 15)),
        log_file=_resolve(web.get("log_file"), base),
    )
    if receiver.offline_timeout_s < 30:
        raise ConfigError("receiver.offline_timeout_s must be >= 30")

    nodes = _nodes(data.get("nodes", []))
    if not nodes:
        raise ConfigError("At least one [[nodes]] entry is required")

    return Config(
        radio=_radio(data.get("radio", {})),
        database=database,
        receiver=receiver,
        web=web_cfg,
        nodes=nodes,
        alerts=_alerts(data.get("alerts", {})),
        source=config_path,
    )
