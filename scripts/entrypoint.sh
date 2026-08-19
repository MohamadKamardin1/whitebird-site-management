#!/usr/bin/env bash
# Container entrypoint: wait for the database, prepare the schema and static
# assets, then serve the ASGI application with Daphne (HTTP + WebSockets).
set -euo pipefail

echo "[entrypoint] waiting for the database to accept connections..."
python /app/scripts/wait_for_db.py

echo "[entrypoint] applying migrations..."
python manage.py migrate --noinput

echo "[entrypoint] collecting static files..."
python manage.py collectstatic --noinput

echo "[entrypoint] starting Daphne (ASGI HTTP + WebSocket server)..."
exec daphne \
    --bind 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    config.asgi:application
