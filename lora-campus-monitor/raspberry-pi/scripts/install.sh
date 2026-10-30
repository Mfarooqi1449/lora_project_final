#!/usr/bin/env bash
# Install / update the LoRa campus monitor on Raspberry Pi OS (Bookworm or newer).
#   cd lora-campus-monitor
#   sudo ./raspberry-pi/scripts/install.sh
# Re-running updates the code but keeps config/config.toml, the database and logs.
set -euo pipefail

INSTALL_DIR=/opt/lora-campus-monitor
APP_DIR="$INSTALL_DIR/raspberry-pi"
SERVICE_USER=loramon
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ $EUID -ne 0 ]]; then
    echo "Run as root: sudo $0" >&2
    exit 1
fi

echo "==> Installing system packages"
apt-get update
apt-get install -y python3 python3-venv python3-pip python3-spidev python3-gpiozero python3-lgpio sqlite3 rsync git

python3 - <<'EOF'
import sys
if sys.version_info < (3, 11):
    sys.exit("Python 3.11+ required (Raspberry Pi OS Bookworm or newer).")
EOF

echo "==> Enabling SPI"
if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_spi 0
fi

echo "==> Creating service user '$SERVICE_USER'"
if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --home-dir "$INSTALL_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi
for grp in spi gpio; do
    getent group "$grp" >/dev/null && usermod -aG "$grp" "$SERVICE_USER"
done

echo "==> Copying application to $INSTALL_DIR"
mkdir -p "$APP_DIR"
rsync -a --delete \
    --exclude '.venv/' --exclude 'database/' --exclude 'logs/' \
    --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude 'config/config.toml' \
    "$SRC_DIR/raspberry-pi/" "$APP_DIR/"
cp "$SRC_DIR/README.md" "$INSTALL_DIR/README.md" 2>/dev/null || true
if [[ ! -f "$APP_DIR/config/config.toml" ]]; then
    cp "$SRC_DIR/raspberry-pi/config/config.toml" "$APP_DIR/config/config.toml"
    echo "    Installed default config: $APP_DIR/config/config.toml (edit node locations!)"
else
    echo "    Kept existing config: $APP_DIR/config/config.toml"
fi
mkdir -p "$APP_DIR/database/backups" "$APP_DIR/logs"

echo "==> Creating Python virtual environment"
if [[ ! -d "$APP_DIR/.venv" ]]; then
    python3 -m venv --system-site-packages "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --upgrade -r "$APP_DIR/requirements.txt"

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

echo "==> Initialising database"
sudo -u "$SERVICE_USER" "$APP_DIR/.venv/bin/python" "$APP_DIR/scripts/init_db.py"

echo "==> Installing systemd units"
install -m 644 "$APP_DIR"/systemd/lora-*.service "$APP_DIR"/systemd/lora-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable lora-receiver.service lora-dashboard.service lora-backup.timer
systemctl restart lora-receiver.service lora-dashboard.service
systemctl start lora-backup.timer

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
echo "Done. Dashboard: http://${IP:-<raspberry-pi-ip>}:5000"
echo "Status: systemctl status lora-receiver lora-dashboard"
echo "Logs:   journalctl -u lora-receiver -f"
echo "If SPI was just enabled, reboot once: sudo reboot"
