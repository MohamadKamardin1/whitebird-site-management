# API Reference

Base path: `/api/v1` — interactive docs at `/api/v1/docs`, schema at
`/api/v1/openapi.json`.

## Authentication

All endpoints except `POST /auth/login` and `GET /health` require a bearer
token:

```
Authorization: Bearer <api_token>
```

Tokens are issued via login or created from the admin. They are revocable and
may carry an expiry.

### Obtain a token

```http
POST /api/v1/auth/login
Content-Type: application/json

{"username": "admin", "password": "…", "token_name": "my-client"}
```

Response contains `token`, `expires_at`, and the user profile. Revoke a token
with `POST /api/v1/auth/tokens/{id}/revoke`.

## Roles

| Role      | Scope                                                              |
| --------- | ------------------------------------------------------------------ |
| `admin`   | Everything.                                                        |
| `manager` | Reads: all sites. Writes: any site they are assigned to.           |
| `staff`   | Reads: only assigned sites. No writes.                             |
| `viewer`  | Reads: only assigned sites (no writes).                            |

Site writes additionally require a MANAGER platform role or a
`site_manager` assignment.

## Endpoints

### Accounts — `/auth`

| Method | Path                        | Description                         |
| ------ | --------------------------- | ----------------------------------- |
| POST   | `/auth/login`               | Exchange credentials for a token    |
| GET    | `/auth/me`                  | Current user profile                |
| GET    | `/auth/me/stats`            | Dashboard aggregates for the user   |
| GET    | `/auth/tokens`              | List my API tokens                  |
| POST   | `/auth/tokens`              | Issue a new API token               |
| POST   | `/auth/tokens/{id}/revoke`  | Revoke a token                      |
| GET    | `/auth/staff`               | Staff directory (admin/manager)     |
| POST   | `/auth/staff`               | Create a user (admin only)          |

### Sites — `/sites`

| Method | Path                              | Description                               |
| ------ | --------------------------------- | ----------------------------------------- |
| GET    | `/sites`                          | List sites (filterable, see below)        |
| POST   | `/sites`                          | Create a site (admin/manager)             |
| GET    | `/sites/{id}`                     | Site detail (cached)                      |
| PATCH  | `/sites/{id}`                     | Update a site (admin/manager)             |
| DELETE | `/sites/{id}`                     | Archive a site (soft delete)              |
| POST   | `/sites/{id}/restore`             | Restore an archived site (admin)          |
| GET    | `/sites/{id}/stats`               | Per-site statistics (cached)              |

List filters (query params): `search`, `status` (slug), `site_type` (slug),
`region`, `country`, `capacity_min`.

### Catalog — `/catalog`

| Method | Path                  | Description                 |
| ------ | --------------------- | --------------------------- |
| GET    | `/catalog/types`      | Site types (active)         |
| GET    | `/catalog/statuses`   | Site statuses (active)      |
| GET    | `/catalog/categories` | Asset categories (active)   |

### Departments — `/sites/{id}/departments`

| Method | Path                          | Description                        |
| ------ | ----------------------------- | ---------------------------------- |
| GET    | `/sites/{id}/departments`     | List departments                   |
| POST   | `/sites/{id}/departments`     | Create a department                |
| PATCH  | `/sites/{id}/departments/{d}` | Update a department                |
| DELETE | `/sites/{id}/departments/{d}` | Deactivate a department (soft)     |

### Assets — `/sites/{id}/assets`

| Method | Path                      | Description                     |
| ------ | ------------------------- | ------------------------------- |
| GET    | `/sites/{id}/assets`      | List assets (`category` filter) |
| POST   | `/sites/{id}/assets`      | Register an asset               |
| PATCH  | `/sites/{id}/assets/{a}`  | Update an asset                 |
| DELETE | `/sites/{id}/assets/{a}`  | Retire an asset (soft)          |

### Staff assignments — `/sites/{id}/assignments`

| Method | Path                                   | Description                         |
| ------ | -------------------------------------- | ----------------------------------- |
| GET    | `/sites/{id}/assignments`              | List assignments                    |
| POST   | `/sites/{id}/assignments`              | Assign staff (`user_id`, `role`)    |
| DELETE | `/sites/{id}/assignments/{id}`         | Unassign staff                      |
| POST   | `/sites/{id}/assignments/{id}/primary` | Set a user's primary site           |

### Statistics — `/stats`

| Method | Path                 | Description                           |
| ------ | -------------------- | ------------------------------------- |
| GET    | `/stats/overview`    | Cross-site aggregates (admin only)    |

### Notifications — `/notifications`

| Method | Path                            | Description                      |
| ------ | ------------------------------- | -------------------------------- |
| GET    | `/notifications`                | My notifications (`unread_only`) |
| GET    | `/notifications/unread-count`   | Unread count                     |
| POST   | `/notifications/mark-read`      | Mark notifications read          |

### Platform — `/`

| Method | Path              | Description                        |
| ------ | ----------------- | ---------------------------------- |
| GET    | `/health`         | DB + cache probes (public)         |
| GET    | `/audit-logs`     | Recent audit entries (admin/manager) |

## Worked example

```bash
# Login
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin-password","token_name":"docs"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")

# List sites with a status filter
curl -s "http://127.0.0.1:8000/api/v1/sites?status=active&region=Unguja%20North" \
  -H "Authorization: Bearer $TOKEN"

# Update a site status (triggers notifications to admins/assigned staff)
curl -s -X PATCH http://127.0.0.1:8000/api/v1/sites/1 \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"status_id":2}'

# Check the notification was produced
curl -s http://127.0.0.1:8000/api/v1/notifications -H "Authorization: Bearer $TOKEN"
```

## Errors

- `401` — missing/invalid token.
- `403` — authenticated but not permitted (role or site scope).
- `404` — resource not found.
- `422` — request body failed validation.
