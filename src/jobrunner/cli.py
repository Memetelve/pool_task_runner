"""Command-line helpers to run the API, worker, and maintenance tasks."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

import uvicorn

from .app import create_app
from .celery_app import celery_app
from .database import init_db


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JobRunner utility commands")
    sub = parser.add_subparsers(dest="command", required=True)

    api = sub.add_parser("api", help="Run the FastAPI server")
    api.add_argument("--host", default="0.0.0.0")
    api.add_argument("--port", type=int, default=8000)

    sub.add_parser("worker", help="Run a Celery worker")
    sub.add_parser("init-db", help="Create database tables")

    return parser


def run_api(host: str = "0.0.0.0", port: int = 8000) -> None:
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


def run_worker() -> None:
    celery_app.worker_main(["worker", "-l", "INFO"])


def run_init_db() -> None:
    asyncio.run(init_db())


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "api":
        run_api(host=args.host, port=args.port)
    elif args.command == "worker":
        run_worker()
    elif args.command == "init-db":
        run_init_db()
    else:  # pragma: no cover
        parser.error("Unknown command")
