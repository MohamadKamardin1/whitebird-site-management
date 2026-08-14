#!/usr/bin/env bash
# Backup the PostgreSQL database to ./backups with a timestamped filename.
# Usage:  ./scripts/backup_db.sh [output_dir]
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="${BACKUP_DIR}/whitebird-${STAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

: "${POSTGRES_HOST:=127.0.0.1}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_DB:=whitebird}"
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_PASSWORD:=postgres}"

echo "[backup] dumping ${POSTGRES_DB} -> ${FILE}"
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
  --host="${POSTGRES_HOST}" \
  --port="${POSTGRES_PORT}" \
  --username="${POSTGRES_USER}" \
  --dbname="${POSTGRES_DB}" \
  --no-owner \
  --format=custom \
  | gzip > "${FILE}"

echo "[backup] done: $(du -h "${FILE}" | cut -f1)"
