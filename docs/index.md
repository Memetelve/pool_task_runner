# JobRunner Documentation

JobRunner is a FastAPI + Celery based orchestration service for submitting, tracking, and operating large regression suites. These docs describe how to deploy the stack, submit workloads, and get the most out of the real-time dashboard.

## Capabilities at a Glance

- Multi-user API secured with OAuth2 password flow and JWTs.
- Batch-aware execution so hundreds of jobs appear as one logical asset.
- Celery workers that execute arbitrary shell commands with configurable working directories and environment variables.
- Rich dashboard that mirrors the API, provides per-batch drill downs, and exposes force-complete/cancel controls.
- First-class CLI (`jobrunner`) plus Docker Compose files for local parity.

## Core Components

| Component | Purpose |
|-----------|---------|
| FastAPI server (`jobrunner api`) | Serves the REST API plus the dashboard HTML pages. |
| Celery worker (`jobrunner worker`) | Executes queued jobs and streams stdout/stderr + exit codes back into the database. |
| PostgreSQL (or SQLite dev default) | Persists users, jobs, batches, and status counters. |
| Redis | Acts as Celery broker/result backend and stores short-lived signals. |
| Dashboard (`/`) | Web console layered on the API for monitoring and control. |

## How the Docs Are Organized

- **Getting Started** – install dependencies, configure `.env`, run API/worker, seed the DB.
- **Jobs & Batches** – schema reference, lifecycle, and control operations.
- **Dashboard** – tour of the UI, detail pages, and keyboard-driven workflows.
- **API Reference** – endpoint-level details and request/response examples.
- **Operations** – running services in production, tuning Celery, and maintaining the system.

Use the navigation sidebar to jump between topics. Every page is pure Markdown, so contributions follow the same PR flow as the rest of the repo.
