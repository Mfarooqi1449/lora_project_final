import pytest

from app.config import ConfigError, load_config
from conftest import ROOT


def test_default_config_loads():
    cfg = load_config(ROOT / "config" / "config.toml")
    assert [n.node_id for n in cfg.nodes] == [1, 2]
    assert cfg.radio.sync_word == 0x12
    assert cfg.database.path.is_absolute()
    assert {r.type for r in cfg.alerts.rules} >= {"high_temperature", "low_light", "low_supply_voltage"}


def test_invalid_hysteresis_rejected(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text(
        """
[[nodes]]
node_id = 1
name = "A"
location = "x"
[[alerts.rules]]
type = "t"
metric = "temperature_c"
direction = "high"
threshold = 30
clear = 35
"""
    )
    with pytest.raises(ConfigError):
        load_config(bad)


def test_unknown_key_rejected(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text('[radio]\nspreading_factr = 7\n[[nodes]]\nnode_id = 1\nname = "A"\nlocation = "x"\n')
    with pytest.raises(ConfigError):
        load_config(bad)
