from dataclasses import replace
from datetime import timedelta

from app.alerts import NODE_OFFLINE, AlertEngine
from app.database import Database, utc_now
from app.processor import PacketProcessor
from app.protocol import FLAG_BME280_ERROR, FLAG_MQ135_WARMUP, encode
from conftest import make_packet


def make_processor(db, config, started_at=None):
    alerts = AlertEngine(db, config.alerts, config.receiver.offline_timeout_s, started_at)
    return PacketProcessor(db, alerts)


def send(proc, when, **fields):
    return proc.handle(encode(make_packet(**fields)), -80.0, 7.5, received_at=when)


def test_valid_packet_is_stored(db, config):
    proc = make_processor(db, config)
    result = send(proc, utc_now())
    assert result.accepted and result.reading_id
    reading = db.latest_reading(1)
    assert reading["temperature_c"] == 25.5
    assert reading["sound_raw"] == 100
    assert reading["rssi_dbm"] == -80.0
    node = db.get_node(1)
    assert node["packets_received"] == 1 and node["last_sequence"] == 10


def test_rejections_are_logged_separately(db, config):
    proc = make_processor(db, config)
    now = utc_now()
    assert proc.handle(b"garbage", -90, 1, received_at=now).reason == "bad_length"
    assert proc.handle(encode(make_packet()), -90, 1, crc_error=True, received_at=now).reason == "radio_crc_error"
    assert send(proc, now, node_id=99).reason == "unknown_node"
    assert send(proc, now).accepted
    assert send(proc, now).reason == "duplicate"
    assert db.reading_count() == 1
    reasons = {r["reason"] for r in db.recent_rejected()}
    assert reasons == {"bad_length", "radio_crc_error", "unknown_node", "duplicate"}
    assert db.get_node(1)["duplicates"] == 1


def test_disabled_node_rejected(db, config):
    nodes = tuple(replace(n, enabled=False) if n.node_id == 2 else n for n in config.nodes)
    db.sync_nodes(nodes)
    proc = make_processor(db, config)
    assert send(proc, utc_now(), node_id=2).reason == "node_disabled"


def test_packet_loss_and_reset_tracking(db, config):
    proc = make_processor(db, config)
    t = utc_now()
    send(proc, t, sequence_number=10, uptime_seconds=600)
    r = send(proc, t + timedelta(minutes=4), sequence_number=14, uptime_seconds=840)
    assert r.lost == 3
    send(proc, t + timedelta(minutes=5), sequence_number=0, uptime_seconds=10, status_flags=1 << 10)
    node = db.get_node(1)
    assert node["packets_lost"] == 3 and node["reboots"] == 1 and node["packets_received"] == 3
    assert any(e["event_type"] == "node_reset" for e in db.recent_events())


def test_sequence_state_survives_restart(db, config):
    t = utc_now()
    send(make_processor(db, config), t, sequence_number=20, uptime_seconds=1200)
    restarted = make_processor(db, config)  # simulates Pi/service restart
    assert send(restarted, t, sequence_number=20, uptime_seconds=1200).reason == "duplicate"
    assert send(restarted, t, sequence_number=22, uptime_seconds=1320).lost == 1


def test_out_of_range_values_are_dropped(db, config):
    proc = make_processor(db, config)
    send(proc, utc_now(), humidity_percent=120.0, air_quality_raw=5000)
    reading = db.latest_reading(1)
    assert reading["humidity_percent"] is None and reading["air_quality_raw"] is None
    assert reading["temperature_c"] == 25.5
    assert reading["status_flags"] & (1 << 15)


def test_alert_requires_consecutive_samples_and_hysteresis(db, config):
    proc = make_processor(db, config)
    t = utc_now()
    seq = iter(range(100, 200))

    def temp(value, minutes):
        send(proc, t + timedelta(minutes=minutes), sequence_number=next(seq), uptime_seconds=6000 + minutes * 60, temperature_c=value)

    temp(45, 0)
    temp(25, 1)  # noisy single sample resets the counter
    temp(45, 2)
    temp(45, 3)
    assert not [a for a in db.active_alerts() if a["alert_type"] == "high_temperature"]
    temp(45, 4)
    active = [a for a in db.active_alerts() if a["alert_type"] == "high_temperature"]
    assert len(active) == 1 and active[0]["threshold_value"] == 40.0

    # Between clear (38) and threshold (40): stays open, no duplicate alert.
    for m in range(5, 9):
        temp(39, m)
    assert len([a for a in db.active_alerts() if a["alert_type"] == "high_temperature"]) == 1

    for m in range(9, 12):
        temp(30, m)
    assert not [a for a in db.active_alerts() if a["alert_type"] == "high_temperature"]
    cleared = db.cleared_alerts()
    assert cleared[0]["alert_type"] == "high_temperature" and cleared[0]["cleared_at"]


def test_mq135_warmup_suppresses_air_alert(db, config):
    proc = make_processor(db, config)
    t = utc_now()
    for i in range(5):
        send(proc, t + timedelta(minutes=i), sequence_number=i + 1, uptime_seconds=60 + i * 60,
             air_quality_raw=3500, status_flags=FLAG_MQ135_WARMUP)
    assert not [a for a in db.active_alerts() if a["alert_type"] == "high_air_quality_raw"]


def test_sensor_failure_alert(db, config):
    proc = make_processor(db, config)
    t = utc_now()
    for i in range(3):
        send(proc, t + timedelta(minutes=i), sequence_number=i + 1, uptime_seconds=600 + i * 60,
             temperature_c=None, humidity_percent=None, pressure_hpa=None, status_flags=FLAG_BME280_ERROR)
    assert [a["alert_type"] for a in db.active_alerts()] == ["sensor_failure_bme280"]


def test_offline_detection_and_recovery(db, config):
    start = utc_now() - timedelta(hours=1)
    engine = AlertEngine(db, config.alerts, config.receiver.offline_timeout_s, start)
    proc = PacketProcessor(db, engine)
    now = utc_now()
    send(proc, now - timedelta(seconds=30), node_id=1)

    engine.check_offline(db.get_nodes(), now)
    offline = {a["node_id"] for a in db.active_alerts() if a["alert_type"] == NODE_OFFLINE}
    assert offline == {2}  # node 2 never reported, node 1 is fresh

    engine.check_offline(db.get_nodes(), now)  # no duplicate
    assert len([a for a in db.active_alerts() if a["alert_type"] == NODE_OFFLINE]) == 1

    send(proc, now, node_id=2, sequence_number=1)
    assert not [a for a in db.active_alerts() if a["alert_type"] == NODE_OFFLINE]


def test_active_alerts_reloaded_after_restart(db, config):
    engine = AlertEngine(db, config.alerts, 180, utc_now() - timedelta(hours=1))
    engine.check_offline(db.get_nodes())
    assert len(db.active_alerts()) == 2
    engine2 = AlertEngine(db, config.alerts, 180, utc_now() - timedelta(hours=1))
    engine2.check_offline(db.get_nodes())
    assert len(db.active_alerts()) == 2


def test_history_retention_and_backup(db, config, tmp_path):
    proc = make_processor(db, config)
    old = utc_now() - timedelta(days=40)
    send(proc, old, sequence_number=1, uptime_seconds=60)
    send(proc, utc_now(), sequence_number=2, uptime_seconds=120)
    history = db.history(1, utc_now() - timedelta(hours=1), utc_now() + timedelta(minutes=1))
    assert len(history) == 1 and history[0]["temperature_c"] == 25.5

    backup = db.backup_to(tmp_path / "b" / "copy.db")
    with Database(backup) as copy:
        assert copy.reading_count() == 2 and copy.integrity_ok()

    assert db.purge_older_than(30) == 1
    assert db.reading_count() == 1
