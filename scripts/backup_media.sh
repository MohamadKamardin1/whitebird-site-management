#!/usr/bin/env bash
# Archive the private media directory (signed-token files) with tar + gzip.
# Usage:  ./scripts/backup_media.sh [output_dir]
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
MEDIA_ROOT="${PRIVATE_MEDIA_ROOT:-./private_media}"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="${BACKUP_DIR}/whitebird-media-${STAMP}.tar.gz"

if [ ! -d "${MEDIA_ROOT}" ]; then
  echo "[backup] media root not found: ${MEDIA_ROOT} (nothing to do)"
  exit 0
fi

mkdir -p "${BACKUP_DIR}"
echo "[backup] archiving ${MEDIA_ROOT} -> ${FILE}"
tar -czf "${FILE}" -C "$(dirname "${MEDIA_ROOT}")" "$(basename "${MEDIA_ROOT}")"
echo "[backup] done: $(du -h "${FILE}" | cut -f1)"
