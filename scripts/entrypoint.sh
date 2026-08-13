#!/usr/bin/env bash
# Container entrypoint: wait for the database, prepare the schema and static
# assets, then serve the application with Gunicorn.
set -euo pipefail

echo "[entrypoint] waiting for the database to accept connections..."
python /app/scripts/wait_for_db.py

echo "[entrypoint] applying migrations..."
python manage.py migrate --noinput

echo "[entrypoint] collecting static files..."
python manage.py collectstatic --noinput

echo "[entrypoint] starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
