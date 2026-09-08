#!/usr/bin/env bash

set -euo pipefail

APP_DIR="/opt/ratsboombot-uat"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="ratsboombot-uat"
DEPLOY_BRANCH="uat"
HEALTH_URL="http://127.0.0.1:4346/health"

BACKUP_DIR="$APP_DIR/.data/backups"
DATABASE_PATH="$APP_DIR/.data/tokens.db"
DEPLOYMENT_STAMP_PATH="$APP_DIR/.data/deployment.txt"
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
MAX_BACKUPS=3

echo "[UAT Deploy] Starting isolated RatsBoomBot UAT deployment."

if [ ! -d "$APP_DIR/.git" ]; then
    echo "[UAT Deploy] ERROR: $APP_DIR is not initialized. Complete deploy/linux/UAT.md first."
    exit 1
fi

if [ ! -f "$APP_DIR/.env" ]; then
    echo "[UAT Deploy] ERROR: $APP_DIR/.env is missing."
    exit 1
fi

cd "$APP_DIR"

PREVIOUS_COMMIT="$(git rev-parse HEAD)"
PREVIOUS_DEPLOYMENT_STAMP=""

if [ -f "$DEPLOYMENT_STAMP_PATH" ]; then
    PREVIOUS_DEPLOYMENT_STAMP="$(<"$DEPLOYMENT_STAMP_PATH")"
fi

mkdir -p "$BACKUP_DIR"

if [ -f "$DATABASE_PATH" ]; then
    sqlite3 "$DATABASE_PATH" ".backup '$BACKUP_DIR/tokens-$TIMESTAMP.db'"
    find "$BACKUP_DIR" -maxdepth 1 -type f -name 'tokens-*.db' -printf '%T@ %p\n' | sort -nr | tail -n +$((MAX_BACKUPS + 1)) | cut -d' ' -f2- | xargs -r rm -f
    echo "[UAT Deploy] Database backup created."
fi

git fetch origin "$DEPLOY_BRANCH"

if [ "$(git branch --show-current)" != "$DEPLOY_BRANCH" ]; then
    git checkout "$DEPLOY_BRANCH"
fi

git pull --ff-only origin "$DEPLOY_BRANCH"
NEW_COMMIT="$(git rev-parse HEAD)"

"$VENV_DIR/bin/python" -m pip install -r requirements.txt
"$VENV_DIR/bin/python" -m compileall app bot config storage web main.py

APP_VERSION="$("$VENV_DIR/bin/python" -c 'from config.version import APP_VERSION; print(APP_VERSION)')"
SHORT_COMMIT="$(git rev-parse --short=8 HEAD)"
DEPLOYMENT_STAMP="$(date '+%m.%d.%Y')-v$APP_VERSION-uat-$SHORT_COMMIT"

mkdir -p "$(dirname "$DEPLOYMENT_STAMP_PATH")"
printf '%s\n' "$DEPLOYMENT_STAMP" > "$DEPLOYMENT_STAMP_PATH"

sudo systemctl restart "$SERVICE_NAME"
sudo systemctl is-active --quiet "$SERVICE_NAME"

for attempt in {1..15}; do
    if response="$(curl --fail --silent "$HEALTH_URL")" && grep -q '"environment":"uat"' <<< "$response"; then
        echo "[UAT Deploy] Health check passed at $NEW_COMMIT."
        exit 0
    fi

    echo "[UAT Deploy] Health check attempt $attempt/15 failed; retrying in 2 seconds."
    sleep 2
done

echo "[UAT Deploy] ERROR: UAT did not become healthy. Rolling back to $PREVIOUS_COMMIT."
git reset --hard "$PREVIOUS_COMMIT"

if [ -n "$PREVIOUS_DEPLOYMENT_STAMP" ]; then
    printf '%s\n' "$PREVIOUS_DEPLOYMENT_STAMP" > "$DEPLOYMENT_STAMP_PATH"
else
    rm -f "$DEPLOYMENT_STAMP_PATH"
fi

"$VENV_DIR/bin/python" -m pip install -r requirements.txt
sudo systemctl restart "$SERVICE_NAME"

for attempt in {1..15}; do
    if response="$(curl --fail --silent "$HEALTH_URL")" && grep -q '"environment":"uat"' <<< "$response"; then
        echo "[UAT Deploy] Rollback succeeded."
        exit 1
    fi

    sleep 2
done

echo "[UAT Deploy] CRITICAL: rollback failed; manual intervention is required."
exit 2
