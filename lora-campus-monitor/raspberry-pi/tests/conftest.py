import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import load_config  # noqa: E402
from app.database import Database  # noqa: E402
from app.protocol import PROTOCOL_VERSION, Packet  # noqa: E402


@pytest.fixture
def config(tmp_path):
    cfg = load_config(ROOT / "config" / "config.toml")
    database = replace(cfg.database, path=tmp_path / "test.db", backup_dir=tmp_path / "backups")
    receiver = replace(cfg.receiver, log_file=None)
    web = replace(cfg.web, log_file=None)
    return replace(cfg, database=database, receiver=receiver, web=web)


@pytest.fixture
def db(config):
    database = Database(config.database.path)
    database.init_schema()
    database.sync_nodes(config.nodes)
    yield database
    database.close()


def make_packet(**overrides) -> Packet:
    values = dict(
        protocol_version=PROTOCOL_VERSION,
        node_id=1,
        sequence_number=10,
        uptime_seconds=600,
        temperature_c=25.5,
        humidity_percent=55.25,
        pressure_hpa=1009.4,
        light_lux=320.5,
        air_quality_raw=1200,
        sound_avg=100,
        sound_peak=700,
        supply_voltage=5.01,
        status_flags=0,
    )
    values.update(overrides)
    return Packet(**values)
