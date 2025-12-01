"""Celery task implementations."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from .celery_app import celery_app
from .config import settings
from .database import async_session_factory
from .models import Job, JobStatus
from .services.jobs import update_job_status


@celery_app.task(name="jobrunner.tasks.execute_job", bind=True)
def execute_job(self, job_id: str) -> str:
    """Execute shell-based regression jobs."""
    del self  # unused but Celery includes it when bind=True
    asyncio.run(_execute_job(UUID(job_id)))
    return job_id


async def _execute_job(job_id: UUID) -> None:
    await update_job_status(
        job_id, JobStatus.running, started_at=datetime.now(timezone.utc)
    )
    async with async_session_factory() as session:
        job = await session.get(Job, job_id)

    if not job:
        return

    working_dir = Path(job.working_dir or settings.default_working_dir).expanduser()

    if not job.command:
        await update_job_status(
            job_id,
            JobStatus.failed,
            completed_at=datetime.now(timezone.utc),
            error="Job metadata missing command",
            result=_build_result_payload(job, working_dir),
        )
        return

    if not working_dir.exists() or not working_dir.is_dir():
        await update_job_status(
            job_id,
            JobStatus.failed,
            completed_at=datetime.now(timezone.utc),
            error=f"Working directory unavailable: {working_dir}",
            result=_build_result_payload(job, working_dir),
        )
        return

    env = os.environ.copy()
    if job.env:
        env.update({str(k): str(v) for k, v in job.env.items()})

    try:
        process = await asyncio.create_subprocess_exec(
            *job.command,
            cwd=str(working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=settings.command_timeout_seconds
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        await update_job_status(
            job_id,
            JobStatus.failed,
            completed_at=datetime.now(timezone.utc),
            error=f"Command timed out after {settings.command_timeout_seconds}s",
            result=_build_result_payload(job, working_dir),
        )
        return
    except FileNotFoundError as exc:
        await update_job_status(
            job_id,
            JobStatus.failed,
            completed_at=datetime.now(timezone.utc),
            error=f"Executable not found: {exc}",
            result=_build_result_payload(job, working_dir),
        )
        return
    except Exception as exc:  # pragma: no cover - unexpected worker errors
        await update_job_status(
            job_id,
            JobStatus.failed,
            completed_at=datetime.now(timezone.utc),
            error=str(exc),
            result=_build_result_payload(job, working_dir),
        )
        return

    stdout_text = stdout.decode("utf-8", errors="replace") if stdout else ""
    stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
    result_payload = _build_result_payload(
        job, working_dir, stdout_text, stderr_text, process.returncode
    )
    status = JobStatus.success if process.returncode == 0 else JobStatus.failed
    error = (
        None
        if status is JobStatus.success
        else f"Command exited with {process.returncode}"
    )
    await update_job_status(
        job_id,
        status,
        completed_at=datetime.now(timezone.utc),
        result=result_payload,
        error=error,
    )


def _build_result_payload(
    job: Job | None,
    working_dir: Path | None,
    stdout_text: str = "",
    stderr_text: str = "",
    return_code: int | None = None,
) -> dict[str, Any]:
    command = job.command if job and job.command else []
    working_dir_str = (
        str(working_dir) if working_dir else (job.working_dir if job else None)
    )
    return {
        "return_code": return_code,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "command": command,
        "working_dir": working_dir_str,
    }
