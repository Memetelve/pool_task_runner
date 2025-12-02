# API Reference

All endpoints live under the configurable prefix (default `/api/v1`). The service uses OAuth2 password flow with JWT access tokens.

## Authentication

```bash
POST /api/v1/auth/token
Content-Type: application/x-www-form-urlencoded

username=admin@example.com&password=ChangeMe123!
```

Response:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

Include `Authorization: Bearer <token>` on every subsequent request.

## Health

`GET /api/v1/health` – readiness probe returning Redis/database connectivity flags.

## Jobs

| Method & Path | Description |
|---------------|-------------|
| `POST /jobs` | Submit a new job (returns `202 Accepted` with `JobRead`). |
| `GET /jobs` | List current user’s jobs (admins see all). Supports `status` and `batch_id` query params. |
| `GET /jobs/stats` | Aggregate counts per status for the current user. |
| `GET /jobs/{id}` | Fetch a specific job. |
| `GET /jobs/{id}/logs` | Retrieve stdout/stderr once the job is terminal. Returns 409 if logs aren’t ready yet. |
| `PATCH /users/{id}` | Update role, password, `is_active`, or per-user job limit. |
| `POST /jobs/{id}/force-complete` | Force a job into a terminal status, optionally overriding stdout/stderr. |
## Admin Limits

The admin namespace allows changing the default concurrent job cap or setting per-account overrides.

| Method & Path | Description |
|---------------|-------------|
| `GET /admin/limits` | Returns the global limit and the list of user overrides. |
| `POST /admin/limits/global` | Sets the default max concurrent jobs for all users. |
| `POST /admin/limits/users/{id}` | Sets or clears a max job override for a specific user (send `null` to clear). |

All responses require admin authentication.

| `DELETE /jobs/{id}/purge` | Remove a finished job and its logs completely. |

### Example Submission

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "nightly-linux",
    "command": ["make", "test"],
    "working_dir": "/workspace/project",
    "env": {"BUILD_MODE": "release"},
    "payload": {"note": "Nightly smoke"}
  }'
```

## Job Batches

| Method & Path | Description |
|---------------|-------------|
| `POST /job-batches` | Create a batch plus one or more nested jobs. |
| `GET /job-batches` | List batches for the authenticated user (admins see all). |
| `GET /job-batches/{id}` | Retrieve a batch plus member jobs ordered by submission time. |
| `POST /job-batches/{id}/cancel` | Cancel all pending/running jobs in the batch. |
| `POST /job-batches/{id}/force-complete` | Mark remaining jobs as success/failed/canceled manually. |
| `DELETE /job-batches/{id}` | Delete a batch once every job is terminal. |

### Example Batch Creation

```bash
curl -X POST http://localhost:8000/api/v1/job-batches \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "nightly-ui-suite",
    "description": "Chromium smoke",
    "jobs": [
      {"name": "login", "command": ["pytest", "tests/login.py"]},
      {"name": "checkout", "command": ["pytest", "tests/checkout.py"]}
    ]
  }'
```

Response contains the saved batch plus an array of `jobs` so clients can render immediately.

## Users

Admin-only endpoints for provisioning operators/viewers.

| Method & Path | Description |
|---------------|-------------|
| `POST /users` | Create a user with role + password. |
| `GET /users` | List all users. |
| `GET /users/{id}` | Retrieve a specific user. |
| `PATCH /users/{id}` | Update role, password, or `is_active`. |

## Error Handling

- Validation issues return HTTP 422 with Pydantic detail.
- Domain errors (e.g., invalid working directory) return HTTP 400 with `{"detail": "..."}`.
- Not found resources always respond with HTTP 404 even if the requester lacks access—avoids leaking IDs.
- Logs requested too early return HTTP 409 so clients know to retry later.

## Rate Limiting & Pagination

The current API does not enforce rate limits. Job/batch list endpoints return entire result sets ordered by `created_at`; add filtering client-side as needed. Contributions adding pagination cursors are welcome.

## OpenAPI Schema

Visit `http://localhost:8000/api/v1/openapi.json` for the machine-readable spec or `http://localhost:8000/docs` for Swagger UI.
