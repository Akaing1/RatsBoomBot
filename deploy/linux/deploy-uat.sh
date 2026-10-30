#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

APP_DIR="/opt/ratsboombot-uat"
VENV_DIR="$APP_DIR/.venv"
SERVICE_NAME="ratsboombot-uat"
DEPLOY_REF="${1:-uat}"
HEALTH_URL="http://127.0.0.1:4346/health"

BACKUP_DIR="$APP_DIR/.data/backups"
DATABASE_PATH="$APP_DIR/.data/tokens.db"
DEPLOYMENT_STAMP_PATH="$APP_DIR/.data/deployment.txt"
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
MAX_BACKUPS=3

echo "[UAT Deploy] Starting isolated RatsBoomBot UAT deployment for $DEPLOY_REF."

if [ ! -d "$APP_DIR/.git" ]; then
    echo "[UAT Deploy] ERROR: $APP_DIR is not initialized. Complete deploy/linux/UAT.md first."
    exit 1
fi

if [ ! -f "$APP_DIR/.env" ]; then
    echo "[UAT Deploy] ERROR: $APP_DIR/.env is missing."
    exit 1
fi

if [ "$DEPLOY_REF" != "uat" ] && [[ ! "$DEPLOY_REF" =~ ^[0-9a-f]{40}$ ]]; then
    echo "[UAT Deploy] ERROR: deployment ref must be uat or a full commit SHA."
    exit 1
fi

# Serialize Actions and direct invocations before touching Git or backing up data.
exec 9>"$APP_DIR/.git/uat-deployment.lock"
if ! flock -w 60 9; then
    echo "[UAT Deploy] ERROR: another UAT deployment holds the deployment lock."
    exit 1
fi

wait_for_checkout_locks() {
    local deadline=$((SECONDS + 180))
    while ! python3 "$SCRIPT_DIR/recover_git_locks.py" "$APP_DIR/.git"; do
        if (( SECONDS >= deadline )); then
            echo "[UAT Deploy] ERROR: Git checkout locks did not become safe within 180 seconds."
            return 1
        fi
        echo "[UAT Deploy] Waiting for checkout locks to become safe; retrying in 10 seconds."
        sleep 10
    done
}

checkout_commit() {
    local commit="$1"
    local attempt
    for attempt in {1..3}; do
        wait_for_checkout_locks || return 1
        # A failed checkout can update files before failing to update HEAD.
        # Preserve both staged and unstaged edits before every attempt.
        if ! git diff --quiet -- || ! git diff --cached --quiet --; then
            git -c user.name="RatsBoomBot UAT deployment" -c user.email="uat-deploy@localhost" \
                stash push -m "uat-pre-deploy-$TIMESTAMP-attempt-$attempt" || return 1
            echo "[UAT Deploy] Preserved tracked checkout changes in git stash."
        fi
        if git -c core.filesRefLockTimeout=10000 checkout --detach "$commit"; then
            if [[ "$(git rev-parse HEAD)" == "$commit" ]]; then
                return 0
            fi
            echo "[UAT Deploy] ERROR: checkout did not select the validated commit."
            return 1
        fi
        # Retry only a checkout lock failure; surface other Git errors immediately.
        if [[ ! -e "$APP_DIR/.git/HEAD.lock" && ! -e "$APP_DIR/.git/index.lock" ]]; then
            return 1
        fi
        echo "[UAT Deploy] Checkout attempt $attempt/3 encountered a Git lock."
    done
    echo "[UAT Deploy] ERROR: checkout exhausted its retry limit."
    return 1
}

wait_for_checkout_locks

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

git fetch --no-tags origin "$DEPLOY_REF"
NEW_COMMIT="$(git rev-parse FETCH_HEAD)"
checkout_commit "$NEW_COMMIT"

"$VENV_DIR/bin/python" -m pip install -r requirements.txt
"$VENV_DIR/bin/python" -m compileall app bot config storage web rpg_minigame pets loyalty viewer_queue main.py

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
checkout_commit "$PREVIOUS_COMMIT"

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
