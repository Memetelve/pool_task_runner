# Dashboard

The dashboard (`/`) consumes the same API that CLI clients use but wraps it with a fast, keyboard-friendly UI.

## Signing In

1. Load `http://localhost:8000/`.
2. Enter the same credentials you pass to `/api/v1/auth/token`.
3. The page exchanges them for a JWT and stores it in `localStorage` (namespaced under `jobrunnerAuth`).

Use the **Sign out** button to clear local state.

## Layout Overview

- **Action Panel** – shows the currently selected batch/job and enables bulk controls (stop, force-complete, delete). Controls stay disabled until you select something.
- **Batch Queue Panel** – renders every real batch plus virtual single-job batches. Each row shows counts, a segmented progress bar, and a dedicated **Details** button.
- **Job Tables** – expanding a batch reveals its member jobs with status pills, elapsed time, working dir, log button, and a per-job **Details** link.
- **Log Modal** – invoked via **View logs** when a job is terminal and has result payloads.

## Detail Pages

Two dedicated routes provide edge-to-edge views:

- `/batches/{batch_id}` – overview metrics, payload preview, member jobs, and an event stream style log.
- `/jobs/{job_id}` – metadata, payload/env, live-refresh buttons for status + logs.

### Admin Controls

- `/admin/limits` – lightweight admin console to edit the global job cap and manage per-user overrides. Requires the same JWT token; non-admins are redirected back to the main dashboard.

Use the **Details** button in the dashboard to reach these pages without opening the accordion first—single-job batches now link directly to `/jobs/{id}`.

## Selection and Controls

- Clicking a batch row highlights it, updates the action panel, and arms batch-level actions.
- Clicking a job row highlights it, arms job-level actions, and shows the job metadata in the panel.
- Selection ignores clicks on the **Details** and **View logs** buttons so you can browse without losing context.

### Actions

| Button | Behavior |
|--------|----------|
| **Stop** | Calls `DELETE /api/v1/jobs/{id}` or `POST /api/v1/job-batches/{id}/cancel` depending on selection. |
| **Force Complete** | Uses the corresponding force-complete endpoints with a success status payload. |
| **Delete** | Calls job purge or batch delete APIs (only enabled once jobs are terminal). |

Feedback from actions surfaces under the action panel (e.g., “Batch cancel signal sent.”).

## Refresh Strategy

After signing in the page calls the jobs and job-batches endpoints, merges results, and starts a polling loop to refresh counts. Use the **Refresh** button whenever you want an immediate sync without waiting for the timer.

## Accessibility Notes

- Buttons are focusable and respond to keyboard activation (`Enter` / `Space`).
- The log modal traps focus until closed with the `×` button, outside click, or `Esc` key.
- Status colors maintain adequate contrast in both dark and light themes supplied by Material.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Unable to sign in" | Confirm the API server is reachable and the `/auth/token` endpoint returns 200 via curl/Postman. |
| Empty dashboard after login | Check browser console for 401s—expired tokens are cleared automatically, but misconfigured clocks can break JWT validation. |
| Buttons stay disabled | Ensure a batch or job is actually selected; if the DOM looks frozen, hit Refresh to rebuild the table from scratch. |
