# Operations

This section covers the day-to-day tasks required to keep JobRunner healthy in staging or production.

## Processes & Scaling

| Process | Command | Notes |
|---------|---------|-------|
| API server | `uv run jobrunner api --host 0.0.0.0 --port 8000` | Wrap with a process manager (systemd, supervisord, Docker). Enable HTTPS/ingress separately. |
| Celery worker | `uv run jobrunner worker` | Runs `jobrunner.tasks.execute_job`. Scale horizontally by launching multiple workers or using Celery autoscaling. |
| Init database | `uv run jobrunner init-db` | Idempotent; safe to run during deploys. |

The provided `docker-compose.yml` is production-ready for small installs. For larger loads, run PostgreSQL/Redis as managed services and point the `.env` entries accordingly.

## Configuration Reference

| Variable | Description |
|----------|-------------|
| `APP_NAME` | Branding used by FastAPI + dashboard. |
| `API_PREFIX` | Change when versioning the API (`/api/v1`). |
| `DATABASE_URL` | SQLAlchemy async connection string. |
| `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Queue plumbing. |
| `DEFAULT_WORKING_DIR` | Directory fallback for jobs. |
| `ALLOWED_WORKDIRS` | JSON array restricting where jobs may execute. |
| `COMMAND_TIMEOUT_SECONDS` | Kills long-running commands. |
| `DEFAULT_MAX_JOBS_PER_USER` | Global concurrent job cap (admins can override per-user). |
| `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Auth configuration. |

Update `.env` (or real secrets manager) and restart the affected services.

## Database Maintenance

- **Backups** – take regular snapshots of PostgreSQL (e.g., `pg_dump`). Jobs store stdout/stderr blobs, so size grows with workload.
- **Vacuuming** – if using PostgreSQL, enable autovacuum or run manual `VACUUM ANALYZE` during low traffic windows.
- **Pruning** – use the job/batch purge APIs or scheduled SQL tasks to delete data older than your retention window.

## Celery Worker Tips

- Set `CELERYD_CONCURRENCY` or `--concurrency` to match CPU/memory budgets.
- Use queues (`queue` field on jobs) to dedicate workers to specific workloads.
- Monitor worker health via Celery events or Prometheus exporters.

## Observability

- Add reverse proxy access logs (nginx/Traefik) for API traffic insight.
- Enable PostgreSQL slow query log if batch metrics grow.
- Emit custom logs from `jobrunner/tasks.py` if you need to forward stdout/stderr to another sink.
- `/api/v1/health` already checks Redis + database; hook it into your k8s/lb health checks.

## Disaster Recovery

1. Restore the PostgreSQL backup.
2. Point JobRunner’s `DATABASE_URL` at the restored instance.
3. Start Redis (stateless) and Celery workers.
4. Run `uv run jobrunner init-db` in case schema migrations were added since the backup was taken (safe when tables exist).

## Upgrading

1. `git pull` the new release.
2. `uv sync` to install updated Python deps.
3. Restart the API and worker.
4. Re-run `uv run jobrunner init-db` when migrations occur.

## Documentation Tooling

Docs live in the `docs/` directory and are built with MkDocs.

```bash
# Live preview with reload
uv run -- mkdocs serve

# Production build (outputs to site/)
uv run -- mkdocs build
```

Publish the contents of `site/` to any static host (GitHub Pages, S3 + CloudFront, etc.).
