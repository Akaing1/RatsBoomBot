#!/usr/bin/env bash

set -euo pipefail

APP_DIR="/opt/ratsboombot"
DATABASE_PATH="$APP_DIR/.data/tokens.db"
BACKUP_DIR="$APP_DIR/.data/backups"
RETENTION_DAYS=14

TIMESTAMP="$(date +"%Y-%m-%d_%H-%M-%S")"
BACKUP_FILE="$BACKUP_DIR/tokens_$TIMESTAMP.db"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DATABASE_PATH" ]; then
    echo "[Backup] Database not found: $DATABASE_PATH"
    exit 1
fi

echo "[Backup] Creating SQLite backup: $BACKUP_FILE"

sqlite3 "$DATABASE_PATH" ".backup '$BACKUP_FILE'"

echo "[Backup] Verifying backup integrity."

INTEGRITY_RESULT="$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;")"

if [ "$INTEGRITY_RESULT" != "ok" ]; then
    echo "[Backup] Integrity check failed: $INTEGRITY_RESULT"
    rm -f "$BACKUP_FILE"
    exit 1
fi

echo "[Backup] Backup verified successfully."

find "$BACKUP_DIR" -type f -name "tokens_*.db" -mtime +"$RETENTION_DAYS" -delete

echo "[Backup] Removed backups older than $RETENTION_DAYS days."
echo "[Backup] Backup completed successfully."
