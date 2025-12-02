## JobRunner

Multi-user batch job orchestration service composed of FastAPI, Celery, Redis, and PostgreSQL. The service exposes a REST API for submitting regression test batches, monitoring progress, and administering users.

### Stack

- FastAPI for the web/API layer (+ OAuth2/JWT auth)
- Celery workers processing regression jobs via shared NFS inputs
- Redis as the broker/result backend
- PostgreSQL (async SQLAlchemy) for metadata and RBAC
- uv for dependency/runtime management

### Prerequisites

- Python 3.11+ (uv installs/boots a managed interpreter automatically)
- Redis + PostgreSQL (use `docker-compose` for local dev)

### Setup

```bash
uv sync
cp .env.example .env  # update secrets + connection strings
uv run jobrunner init-db
```

### Local development

- Run API: `uv run jobrunner api --host 0.0.0.0 --port 8000`
- Run worker: `uv run jobrunner worker`
- Bring up full stack: `docker compose up --build`

### Documentation

- Install docs tooling: `uv sync --extra docs`
- Live preview: `uv run -- mkdocs serve`
- Production build: `uv run -- mkdocs build` (outputs to `site/`)
- Docs live under `docs/` and the configuration is in `mkdocs.yml`. Contributions follow the same PR workflow as the codebase.

### Submitting shell-command jobs

Payloads now describe the command to execute plus optional working directory/env:

```json
POST /api/v1/jobs
Authorization: Bearer <token>
{
	"name": "linux-build",
	"command": ["make", "-f", "Makefile", "all"],
	"working_dir": "/workspace/project",
	"env": {"BUILD_MODE": "release"},
	"payload": {"note": "nightly regression"}
}
```

The Celery worker spawns the command locally, streams stdout/stderr, enforces `COMMAND_TIMEOUT_SECONDS`, and records the exit code in the job’s `result`. Configure safe directories via `DEFAULT_WORKING_DIR` and comma-separated `ALLOWED_WORKDIRS`.

### Job Limits

Admins can enforce concurrency caps to keep the cluster healthy.

- Default limit is controlled by `DEFAULT_MAX_JOBS_PER_USER` (100 by default).
- Visit `/admin/limits` to edit the global cap or set per-user overrides.
- API submissions return HTTP 400 if the new workload would exceed the user’s available slots.

### API Highlights

- `/api/v1/health` – readiness probe
- `/api/v1/auth/token` – OAuth2 password grant
- `/api/v1/jobs` – submit/list jobs
- `/api/v1/job-batches` – create/list grouped runs (and fetch their member jobs)
- `/api/v1/users` – admin-only user management
- `/api/v1/jobs/stats` – per-user aggregates (used by dashboard)

### Batched regression suites

Launch hundreds of tests under a single batch record and monitor progress as one asset:

```json
POST /api/v1/job-batches
Authorization: Bearer <token>
{
	"name": "nightly-ui-suite",
	"description": "500 chromium tests",
	"jobs": [
		{"name": "test-1", "command": ["pytest", "tests/test_1.py"]},
		{"name": "test-2", "command": ["pytest", "tests/test_2.py"]}
	]
}
```

Each job inherits the same validation rules (working dir/env, queue, priority). The batch stores live counters (waiting/running/failed/passed) plus timestamps, so UI clients can render progress bars or alert when suites finish. Individual jobs can still be queried via `/api/v1/jobs?batch_id=<batch>`.

### Web dashboard

- Once the API is running, open `http://localhost:8000/`.
- Sign in with your API credentials (e.g. `admin@example.com` + password).
- The page now shows:
  - Live status cards for all of your jobs
  - A batch gallery with the grey/yellow/red/green segmented progress bar and expandable tables of member jobs
	- The traditional job table (filterable via API for batch drill-downs)
	- Inline access to stdout/stderr per job via the “View logs” action (pulled from `/api/v1/jobs/{id}/logs`)

### Project Layout

- `src/jobrunner/app.py` – FastAPI factory
- `src/jobrunner/api/routes` – routers for auth, jobs, users, health
- `src/jobrunner/services/jobs.py` – orchestration logic
- `src/jobrunner/tasks.py` – Celery task entrypoints
- `docker-compose.yml` – local runtime for Redis/Postgres/API/worker

### Testing & linting

```bash
uv run pytest
uv run ruff check .
```

### Next steps

- Implement persistent NFS path validation per job payloads
- Add CLI helpers for seeding batch templates / matrix fans
- Integrate role-based UI + audit events
- Surface Slack/webhook notifications for batch completion windows
