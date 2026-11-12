#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$APP_DIR/deploy/docker-compose.prod.yml" --env-file "$APP_DIR/.env")
BACKUP_DIR="$APP_DIR/backups"
STAMP="$(date +%F-%H%M)"

mkdir -p "$BACKUP_DIR"
"${COMPOSE[@]}" exec -T db2 su - db2inst1 -c \
    "mkdir -p /database/backups && db2 backup db clinic to /database/backups"
"${COMPOSE[@]}" exec -T db2 tar -C /database/backups -czf - . \
    > "$BACKUP_DIR/db2-${STAMP}.tgz"
find "$BACKUP_DIR" -type f -name 'db2-*.tgz' -mtime +7 -delete
echo "Database backup written to $BACKUP_DIR/db2-${STAMP}.tgz"
