# Getting Started

This guide walks through installing dependencies, configuring JobRunner, and launching the API + worker locally.

## Prerequisites

- Python 3.11+ (the repo uses [uv](https://docs.astral.sh/uv/) to manage virtual environments automatically).
- Redis and PostgreSQL instances. For local dev you can rely on `docker-compose.yml` which provisions both services plus the API/worker containers.
- A `.env` file containing secrets and connection strings (see `.env.example`).

## Install Dependencies

```bash
# Install Python deps with uv (installs interpreter automatically if missing)
uv sync

# Copy baseline configuration and edit as needed
cp .env.example .env
```

Key settings in `.env`:

- `DATABASE_URL` – async SQLAlchemy connection (defaults to SQLite for dev).
- `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` – queue plumbing.
- `JWT_SECRET_KEY` / `ACCESS_TOKEN_EXPIRE_MINUTES` – auth controls.
- `DEFAULT_WORKING_DIR`, `ALLOWED_WORKDIRS` – restricts where jobs can run.

## Initialize the Database

```bash
uv run jobrunner init-db
```

This command creates tables using SQLAlchemy metadata. Run it whenever you point the service at a brand-new database.

## Launch the API and Worker

### Run directly with uv

```bash
uv run jobrunner api --host 0.0.0.0 --port 8000
uv run jobrunner worker
```

### Or via Docker Compose

```bash
docker compose up --build
```

The compose file builds the API image, launches Redis/PostgreSQL, and keeps a Celery worker online.

## Seed a User and Fetch a Token

Use the `/api/v1/users` endpoint (admin only) or the SQL seed script you prefer. The example `.env` aligns with `admin@example.com` / `ChangeMe123!` from the test fixtures.

Retrieve a JWT via the password grant:

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin@example.com&password=ChangeMe123!'
```

Use the returned `access_token` for subsequent API and dashboard calls.

## Verify the Stack

1. Hit `GET /api/v1/health` – should return `{"status":"ok"...}`.
2. Open `http://localhost:8000/`, sign in with your JWT, and confirm batches/jobs stream in.
3. Submit a smoke job:

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "smoke",
    "command": ["echo", "hello"],
    "working_dir": "."
  }'
```

The dashboard should show a single-job batch with stdout/stderr accessible once the worker finishes.
