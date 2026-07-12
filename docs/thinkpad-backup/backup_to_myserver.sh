#!/usr/bin/bash

set -euo pipefail

REMOTE_USER="marc"
REMOTE_HOST="100.100.50.50"
SOURCE_PATH="$HOME/usuari"
REMOTE_PATH="/srv/backups/thinkpad/usuari"
LOGFILE="$HOME/.local/share/thinkpad-backup.log"

mkdir -p "$(dirname "$LOGFILE")"

# Abort quickly if server is unreachable
if ! ping -c 1 -W 3 "$REMOTE_HOST" &>/dev/null; then
    echo "$(date): Backup skipped – home server unreachable" >> "$LOGFILE"
    exit 0
fi

rsync -aAX --delete --numeric-ids \
  --exclude=".cache/" \
  --exclude="Downloads/" \
  --exclude="**/__pycache__/" \
  --exclude="**/*.pyc" \
  --exclude="**/.mypy_cache/" \
  --exclude="**/.pytest_cache/" \
  --exclude="**/.ruff_cache/" \
  --exclude="**/.tox/" \
  --exclude="**/venv/" \
  --exclude="**/.venv/" \
  --exclude="**/env/" \
  --exclude="**/.env/" \
  --exclude="node_modules/" \
  "${SOURCE_PATH}/" \
  "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}/" \
  >> "$LOGFILE" 2>&1

echo "$(date): Backup completed successfully" >> "$LOGFILE"

