import csv
import io
from datetime import timedelta

import pytest

from app.alerts import AlertEngine
from app.database import utc_now
from app.processor import PacketProcessor
from app.protocol import encode
from app.web import create_app
from conftest import make_packet


@pytest.fixture
def client(config, db):
    alerts = AlertEngine(db, config.alerts, config.receiver.offline_timeout_s, utc_now() - timedelta(hours=1))
    proc = PacketProcessor(db, alerts)
    now = utc_now()
    for i in range(5):
        proc.handle(encode(make_packet(sequence_number=i + 1, uptime_seconds=60 * (i + 1))), -75.0, 8.0,
                    received_at=now - timedelta(minutes=5 - i))
    alerts.check_offline(db.get_nodes(), now)  # node 2 offline
    db.set_status({"receiver_heartbeat": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "radio_ok": 1, "receiver_version": "1.0.0"})
    app = create_app(config)
    app.testing = True
    return app.test_client()


@pytest.mark.parametrize("path", ["/", "/node/1", "/node/2", "/alerts", "/maintenance"])
def test_pages_render(client, path):
    assert client.get(path).status_code == 200


def test_unknown_node_404(client):
    assert client.get("/node/9").status_code == 404
    assert client.get("/api/nodes/9/history").status_code == 404


def test_api_overview(client):
    data = client.get("/api/overview").get_json()
    nodes = {n["node_id"]: n for n in data["nodes"]}
    assert nodes[1]["online"] and not nodes[2]["online"]
    assert nodes[1]["latest"]["temperature_c"] == 25.5
    assert nodes[1]["packet_loss_percent"] == 0.0
    assert data["receiver"]["running"] and data["receiver"]["radio_ok"]
    assert data["active_alerts"] == 1


def test_api_history(client):
    data = client.get("/api/nodes/1/history?hours=1").get_json()
    assert len(data["points"]) == 5
    assert data["points"][0]["rssi_dbm"] == -75.0


def test_csv_export(client):
    res = client.get("/export.csv?node_id=1")
    assert res.status_code == 200
    assert "attachment" in res.headers["Content-Disposition"]
    rows = list(csv.DictReader(io.StringIO(res.get_data(as_text=True))))
    assert len(rows) == 5
    assert rows[0]["node_id"] == "1" and float(rows[0]["temperature_c"]) == 25.5


def test_csv_export_time_filter(client):
    start = (utc_now() - timedelta(minutes=2, seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = client.get(f"/export.csv?node_id=all&start={start}")
    rows = list(csv.DictReader(io.StringIO(res.get_data(as_text=True))))
    assert len(rows) == 2


def test_csv_export_bad_input(client):
    assert client.get("/export.csv?start=yesterday").status_code == 400
    assert client.get("/export.csv?node_id=abc").status_code == 400


def test_acknowledge_alert(client, db):
    alert = db.active_alerts()[0]
    res = client.post(f"/alerts/{alert['id']}/ack")
    assert res.status_code == 302
    assert db.active_alerts()[0]["acknowledged"] == 1


def test_healthz(client):
    assert client.get("/healthz").get_json()["status"] == "ok"
