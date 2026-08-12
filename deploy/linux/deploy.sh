#!/usr/bin/env bash

set -euo pipefail

APP_DIR="/opt/ratsboombot"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="ratsboombot"
DEPLOY_BRANCH="feature/kamikaze-spam-protection"
HEALTH_URL="http://127.0.0.1:4345/health"

BACKUP_DIR="$APP_DIR/deploy/linux/backup"
DATABASE_PATH="$APP_DIR/.data/tokens.db"
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"

MAX_BACKUPS=3

echo "[Deploy] Starting RatsBoomBot deployment."

cd "$APP_DIR"

PREVIOUS_COMMIT="$(git rev-parse HEAD)"

echo "[Deploy] Current commit: $PREVIOUS_COMMIT"

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
git fetch origin "$DEPLOY_BRANCH"

CURRENT_BRANCH="$(git branch --show-current)"

if [ "$CURRENT_BRANCH" != "$DEPLOY_BRANCH" ]; then
    echo "[Deploy] Switching from $CURRENT_BRANCH to $DEPLOY_BRANCH."
    git checkout "$DEPLOY_BRANCH"
fi

echo "[Deploy] Updating $DEPLOY_BRANCH."
git pull --ff-only origin "$DEPLOY_BRANCH"

NEW_COMMIT="$(git rev-parse HEAD)"

echo "[Deploy] New commit: $NEW_COMMIT"

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
echo "[Deploy] Rolling back to commit $PREVIOUS_COMMIT."

git reset --hard "$PREVIOUS_COMMIT"

echo "[Deploy] Restoring dependencies for previous commit."
"$VENV_DIR/bin/python" -m pip install -r requirements.txt

echo "[Deploy] Restarting rolled-back service."
sudo systemctl restart "$SERVICE_NAME"

echo "[Deploy] Verifying rollback."

for attempt in {1..15}; do
    if curl --fail --silent "$HEALTH_URL" > /dev/null; then
        echo "[Deploy] Rollback succeeded."
        echo "[Deploy] Previous version restored: $PREVIOUS_COMMIT"
        exit 1
    fi

    echo "[Deploy] Rollback health check $attempt/15 failed; retrying in 2 seconds."
    sleep 2
done

echo "[Deploy] CRITICAL: Rollback failed."
echo "[Deploy] Manual intervention is required."

exit 2
