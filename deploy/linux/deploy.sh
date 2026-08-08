#!/usr/bin/env bash

set -euo pipefail

APP_DIR="/opt/ratsboombot"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="ratsboombot"
HEALTH_URL="http://127.0.0.1:4345/health"

echo "[Deploy] Starting RatsBoomBot deployment."

cd "$APP_DIR"

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

echo "[Deploy] Waiting for service startup."
sleep 5

echo "[Deploy] Checking service status."
sudo systemctl is-active --quiet "$SERVICE_NAME"

echo "[Deploy] Checking health endpoint."
curl --fail --silent "$HEALTH_URL" > /dev/null

echo "[Deploy] RatsBoomBot deployment completed successfully."
