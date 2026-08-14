# Restore notes

Restore both the database and the private media from the backups produced by
`scripts/backup_db.sh` and `scripts/backup_media.sh`.

## 1. Restore the database

The DB backup is a compressed PostgreSQL custom-format dump:

```bash
# Local (hosted Postgres)
gunzip -c ./backups/whitebird-YYYYMMDD-HHMMSS.sql.gz \
  | pg_restore --no-owner --dbname=whitebird

# Or, for a plain restore into an existing database:
createdb whitebird   # if needed
pg_restore --no-owner --dbname=whitebird <(gunzip -c ./backups/whitebird-YYYYMMDD-HHMMSS.sql.gz)
```

### Docker / compose restore

```bash
docker compose exec -T db pg_restore --no-owner --username=postgres --dbname=whitebird \
  <(gunzip -c ./backups/whitebird-YYYYMMDD-HHMMSS.sql.gz)
```

## 2. Restore private media

Extract the media archive into the container/service that holds `PRIVATE_MEDIA_ROOT`
(default `private_media/`):

```bash
tar -xzf ./backups/whitebird-media-YYYYMMDD-HHMMSS.tar.gz
```

Then point `PRIVATE_MEDIA_ROOT` at the restored directory (or move the contents
into the existing `private_media/`).

## 3. Verify

```bash
python manage.py migrate --check   # schema is consistent
python manage.py shell -c "from apps.core.models import AuditLog; print(AuditLog.objects.count())"
curl -s http://localhost:8000/healthz   # liveness
```

> Signed file tokens are stateless (no DB rows), so restoring media + DB together
> keeps existing signed URLs valid as long as `DJANGO_SECRET_KEY` is unchanged.
> If `DJANGO_SECRET_KEY` rotates, previously issued signed links expire — users
> must re-request a fresh download URL.
