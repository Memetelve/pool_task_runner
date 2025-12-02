# Jobs & Batches

Jobs represent individual shell commands. Batches are logical containers that keep progress metrics, allow mass cancellation, and power the dashboard’s progress bars. This page explains payloads, lifecycle rules, and control operations.

## Job Payload

| Field | Required | Description |
|-------|----------|-------------|
| `name` | ✅ | Friendly identifier used throughout the UI. |
| `command` | ✅ | Array of CLI arguments (first item is the executable). |
| `payload` | ❌ | Arbitrary JSON for your own downstream tooling. |
| `queue` | ❌ | Celery queue override (defaults to `settings.default_queue`). |
| `priority` | ❌ | Integer 0–10 used by the broker. |
| `working_dir` | ❌ | Directory to execute in (validated against `DEFAULT_WORKING_DIR` / `ALLOWED_WORKDIRS`). |
| `env` | ❌ | Dict of environment variables merged into the worker’s process. |
| `scheduled_at` | ❌ | Timestamp for delayed execution (still enqueued immediately). |
| `batch_id` | ❌ | Attach the job to an existing batch. |

### Working Directory Guardrails

`JobService` normalizes `working_dir` and ensures it is either the configured default or inside one of the `allowed_workdirs`. Submissions outside these roots fail with HTTP 400.

### Environment Variables

Provide a simple dictionary; values are coerced to strings and merged with the worker’s `os.environ` before `asyncio.create_subprocess_exec` launches the command.

### Limits & Fair Use

Admins can enforce a default concurrency cap (100 jobs by default) and per-user overrides. When a user submits a job or batch, the API counts their pending + running jobs and rejects the request with HTTP 400 if it would exceed the limit.

## Job Lifecycle

Jobs move through the `JobStatus` enum:

1. `pending` – persisted but not yet picked up by Celery.
2. `running` – worker has started executing the command.
3. `success` – command exited with code 0.
4. `failed` – non-zero exit code, timeout, or worker error.
5. `canceled` – user-driven cancellation (pre-run or mid-run).

The worker writes stdout/stderr, return code, command, and working dir into `job.result` for later retrieval via `/api/v1/jobs/{id}/logs`.

## Batch Payload

```json
POST /api/v1/job-batches
Authorization: Bearer <token>
{
  "name": "nightly-ui-suite",
  "description": "500 chromium tests",
  "payload": {"channel": "main"},
  "jobs": [
    {"name": "test-1", "command": ["pytest", "tests/test_login.py"]},
    {"name": "test-2", "command": ["pytest", "tests/test_checkout.py"]}
  ]
}
```

Every nested job follows the same validation rules as standalone submissions. The API stamps `batch_id` for you, increments `total_jobs`, and sets `pending_count`.

## Batch Metrics

Each `JobBatch` tracks counters for `pending`, `running`, `success`, `failed`, and `canceled`. Transitions happen whenever a job status changes, so the dashboard and `/api/v1/job-batches/{id}` stay in sync.

Additional timestamps:

- `created_at` – submission time.
- `started_at` – when the first job entered `running`.
- `completed_at` – once all jobs reach a terminal state.

## Control Operations

| Action | Endpoint | Notes |
|--------|----------|-------|
| Cancel job | `DELETE /api/v1/jobs/{id}` | Allowed while status ∈ {pending, running}. |
| Force-complete job | `POST /api/v1/jobs/{id}/force-complete` | Supply `status`, optional `stdout`/`stderr` overrides. |
| Delete job | `DELETE /api/v1/jobs/{id}/purge` | Requires terminal state. Removes DB row + logs. |
| Cancel batch | `POST /api/v1/job-batches/{id}/cancel` | Cancels every pending/running member job. |
| Force-complete batch | `POST /api/v1/job-batches/{id}/force-complete` | Applies terminal status to all non-terminal jobs. |
| Delete batch | `DELETE /api/v1/job-batches/{id}` | Only when no jobs are pending/running. Cascade deletes member jobs. |

## Single Jobs as Virtual Batches

The dashboard treats solitary jobs as one-job batches so the UX stays consistent. These are never persisted as `JobBatch` rows; instead, the client builds an in-memory batch-like object by combining job counts. Clicking **Details** for those entries jumps straight to the `/jobs/{id}` detail page.
