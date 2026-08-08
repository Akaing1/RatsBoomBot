#!/usr/bin/env bash

set -euo pipefail

APP_DIR="/opt/ratsboombot"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="ratsboombot"
HEALTH_URL="http://127.0.0.1:4345/health"

BACKUP_DIR="$APP_DIR/deploy/linux/backup"
DATABASE_PATH="$APP_DIR/.data/tokens.db"
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"

MAX_BACKUPS=3

echo "[Deploy] Starting RatsBoomBot deployment."

cd "$APP_DIR"

echo "[Deploy] Creating pre-deployment database backup."

mkdir -p "$BACKUP_DIR"

if [ -f "$DATABASE_PATH" ]; then
    sqlite3 "$DATABASE_PATH" ".backup '$BACKUP_DIR/tokens-$TIMESTAMP.db'"
    echo "[Deploy] Database backup created: tokens-$TIMESTAMP.db"

    echo "[Deploy] Pruning old database backups."

    find "$BACKUP_DIR" \
        -maxdepth 1 \
        -type f \
        -name 'tokens-*.db' \
        -printf '%T@ %p\n' \
        | sort -nr \
        | tail -n +$((MAX_BACKUPS + 1)) \
        | cut -d' ' -f2- \
        | xargs -r rm -f
else
    echo "[Deploy] WARNING: Database not found; skipping backup."
fi

echo "[Deploy] Fetching latest code."
git fetch origin

echo "[Deploy] Updating current branch."
git pull --ff-only

echo "[Deploy] Installing dependencies."
"$VENV_DIR/bin/python" -m pip install -r requirements.txt

echo "[Deploy] Running compile checks."
"$VENV_DIR/bin/python" -m compileall app bot config storage web main.py

echo "[Deploy] Restarting systemd service."
sudo systemctl restart "$SERVICE_NAME"

echo "[Deploy] Checking service status."
sudo systemctl is-active --quiet "$SERVICE_NAME"

echo "[Deploy] Waiting for health endpoint."

for attempt in {1..15}; do
    if curl --fail --silent "$HEALTH_URL" > /dev/null; then
        echo "[Deploy] Health check passed."
        echo "[Deploy] RatsBoomBot deployment completed successfully."
        exit 0
    fi

    echo "[Deploy] Health check attempt $attempt/15 failed; retrying in 2 seconds."
    sleep 2
done

echo "[Deploy] ERROR: RatsBoomBot did not become healthy."
exit 1
