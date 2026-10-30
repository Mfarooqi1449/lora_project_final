"""Flask dashboard and JSON API.

Development:  python -m app.web
Production:   waitress-serve --host 0.0.0.0 --port 5000 --call app.web:create_app
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request, stream_with_context, url_for

from . import __version__
from .config import Config, load_config
from .database import Database, parse_iso, utc_now
from .exporter import export_filename, iter_csv
from .health import cpu_temperature_c, disk_usage, file_size_mb, load_average, system_uptime_s
from .protocol import flag_names

MAX_HISTORY_HOURS = 24 * 31
METRIC_LABELS = {
    "temperature_c": ("Temperature", "°C"),
    "humidity_percent": ("Humidity", "%"),
    "pressure_hpa": ("Pressure", "hPa"),
    "light_lux": ("Light", "lx"),
    "air_quality_raw": ("MQ-135 (raw)", "ADC"),
    "sound_raw": ("Sound avg", "ADC"),
    "sound_peak": ("Sound peak", "ADC"),
    "supply_voltage": ("Supply", "V"),
    "rssi_dbm": ("RSSI", "dBm"),
    "snr_db": ("SNR", "dB"),
}


def _age_seconds(timestamp: str | None, now: datetime) -> int | None:
    if not timestamp:
        return None
    return max(0, int((now - parse_iso(timestamp)).total_seconds()))


def node_summary(db: Database, node: dict, offline_timeout_s: int, now: datetime) -> dict:
    latest = db.latest_reading(node["node_id"])
    age = _age_seconds(node["last_seen"], now)
    expected = node["packets_received"] + node["packets_lost"]
    loss = round(100.0 * node["packets_lost"] / expected, 2) if expected else None
    if latest:
        latest["status_text"] = flag_names(latest["status_flags"])
    return {
        **node,
        "enabled": bool(node["enabled"]),
        "online": bool(node["enabled"]) and age is not None and age <= offline_timeout_s,
        "last_seen_age_s": age,
        "packet_loss_percent": loss,
        "latest": latest,
        "active_alerts": len(db.active_alerts(node["node_id"])),
    }


def receiver_status(db: Database, config: Config, now: datetime) -> dict:
    status = {k: v["value"] for k, v in db.get_status().items()}
    heartbeat_age = _age_seconds(status.get("receiver_heartbeat"), now)
    running = heartbeat_age is not None and heartbeat_age <= 3 * config.receiver.health_interval_s
    return {
        "running": running,
        "heartbeat_age_s": heartbeat_age,
        "radio_ok": running and status.get("radio_ok") == "1",
        "radio_settings": status.get("radio_settings"),
        "version": status.get("receiver_version"),
        "started_at": status.get("receiver_started_at"),
        "packets_received": status.get("packets_received"),
        "packets_stored": status.get("packets_stored"),
        "packets_rejected": status.get("packets_rejected"),
    }


def _parse_time_arg(name: str) -> datetime | None:
    value = request.args.get(name, "").strip()
    if not value:
        return None
    try:
        return parse_iso(value)
    except ValueError:
        abort(400, f"Invalid {name} timestamp; use ISO 8601, e.g. 2026-10-30T10:00:00Z")


def create_app(config: Config | None = None) -> Flask:
    config = config or load_config()
    app = Flask(__name__)
    app.config["MONITOR"] = config
    app.config["JSON_SORT_KEYS"] = False

    setup_db = Database(config.database.path)
    setup_db.init_schema()
    setup_db.sync_nodes(config.nodes)
    setup_db.close()

    def db() -> Database:
        if "db" not in g:
            g.db = Database(config.database.path)
        return g.db

    @app.teardown_appcontext
    def _close_db(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    @app.context_processor
    def _inject():
        return {
            "app_version": __version__,
            "refresh_s": config.web.refresh_interval_s,
            "nav_nodes": [n for n in config.nodes],
            "metric_labels": METRIC_LABELS,
        }

    def get_node_or_404(node_id: int) -> dict:
        node = db().get_node(node_id)
        if node is None:
            abort(404, f"Unknown node {node_id}")
        return node

    # ----------------------------------------------------------------- pages
    @app.get("/")
    def overview():
        return render_template("overview.html")

    @app.get("/node/<int:node_id>")
    def node_page(node_id: int):
        node = get_node_or_404(node_id)
        return render_template("node.html", node=node, offline_timeout_s=config.receiver.offline_timeout_s)

    @app.get("/alerts")
    def alerts_page():
        return render_template(
            "alerts.html",
            active=db().active_alerts(),
            cleared=db().cleared_alerts(limit=200),
            nodes={n["node_id"]: n for n in db().get_nodes()},
        )

    @app.post("/alerts/<int:alert_id>/ack")
    def acknowledge(alert_id: int):
        db().acknowledge_alert(alert_id)
        return redirect(url_for("alerts_page"))

    @app.get("/maintenance")
    def maintenance():
        now = utc_now()
        backups = db().recent_events(limit=5, event_type="backup")
        return render_template(
            "maintenance.html",
            nodes=db().get_nodes(),
            receiver=receiver_status(db(), config, now),
            db_path=str(config.database.path),
            db_size_mb=file_size_mb(config.database.path),
            reading_count=db().reading_count(),
            rejected_count=db().rejected_count(),
            disk=disk_usage(config.database.path.parent),
            cpu_temp=cpu_temperature_c(),
            load=load_average(),
            uptime_s=system_uptime_s(),
            backups=backups,
            backup_dir=str(config.database.backup_dir),
            events=db().recent_events(limit=30),
            rejected=db().recent_rejected(limit=20),
            python_version=sys.version.split()[0],
        )

    # ------------------------------------------------------------------- API
    @app.get("/api/overview")
    def api_overview():
        now = utc_now()
        nodes = [node_summary(db(), n, config.receiver.offline_timeout_s, now) for n in db().get_nodes()]
        return jsonify(
            {
                "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "receiver": receiver_status(db(), config, now),
                "database": {"ok": True, "size_mb": file_size_mb(config.database.path)},
                "active_alerts": len(db().active_alerts()),
                "nodes": nodes,
            }
        )

    @app.get("/api/nodes/<int:node_id>")
    def api_node(node_id: int):
        node = get_node_or_404(node_id)
        now = utc_now()
        return jsonify(
            {
                "node": node_summary(db(), node, config.receiver.offline_timeout_s, now),
                "recent": db().recent_readings(node_id, limit=15),
                "alerts": db().active_alerts(node_id),
            }
        )

    @app.get("/api/nodes/<int:node_id>/history")
    def api_history(node_id: int):
        get_node_or_404(node_id)
        hours = request.args.get("hours", default=24, type=float)
        hours = min(max(hours, 0.1), MAX_HISTORY_HOURS)
        points = min(max(request.args.get("points", default=400, type=int), 10), 2000)
        end = utc_now()
        start = end - timedelta(hours=hours)
        return jsonify({"node_id": node_id, "hours": hours, "points": db().history(node_id, start, end, points)})

    @app.get("/api/alerts")
    def api_alerts():
        return jsonify({"active": db().active_alerts(), "cleared": db().cleared_alerts(limit=100)})

    @app.get("/healthz")
    def healthz():
        try:
            ok = db().integrity_ok()
        except Exception:
            ok = False
        return jsonify({"status": "ok" if ok else "error"}), 200 if ok else 503

    # ---------------------------------------------------------------- export
    @app.get("/export.csv")
    def export_csv():
        node_arg = request.args.get("node_id", "").strip()
        node_id = None
        if node_arg and node_arg != "all":
            if not node_arg.isdigit():
                abort(400, "node_id must be a number or 'all'")
            node_id = int(node_arg)
            get_node_or_404(node_id)
        start = _parse_time_arg("start")
        end = _parse_time_arg("end")
        if start and end and start > end:
            abort(400, "start must be before end")

        export_db = Database(config.database.path)  # outlives the request context

        def generate():
            try:
                yield from iter_csv(export_db, node_id, start, end)
            finally:
                export_db.close()

        filename = export_filename(node_id, start, end)
        return Response(
            stream_with_context(generate()),
            mimetype="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return app


def main() -> None:
    from .logging_setup import setup_logging

    config = load_config()
    setup_logging("INFO", config.web.log_file)
    create_app(config).run(host=config.web.host, port=config.web.port, debug=False)


if __name__ == "__main__":
    main()
