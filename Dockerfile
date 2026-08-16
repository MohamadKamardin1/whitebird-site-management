# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS frontend-build

WORKDIR /app/frontend
ARG VITE_MAPBOX_ACCESS_TOKEN
ENV VITE_MAPBOX_ACCESS_TOKEN=${VITE_MAPBOX_ACCESS_TOKEN}
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

# Non-root runtime user.
RUN groupadd --system app && useradd --system --gid app --create-home app

# Install dependencies first for better layer caching.
COPY requirements/ requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

COPY --chown=app:app . .
COPY --from=frontend-build --chown=app:app /app/frontend/dist /app/static/frontend

# The entrypoint waits for the database, migrates, collects static files,
# then hands over to Gunicorn.
RUN chmod +x /app/scripts/entrypoint.sh /app/scripts/wait_for_db.py

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status==200 else 1)"]

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
