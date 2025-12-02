"""Job orchestration domain logic."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..celery_app import celery_app
from ..config import settings
from ..models import Job, JobBatch, JobStatus, User, UserRole
from ..schemas import JobBatchCreate, JobCreate
from .quotas import QuotaService, enforce_quota

TERMINAL_STATUSES = {
    JobStatus.success,
    JobStatus.failed,
    JobStatus.canceled,
}
CANCELABLE_STATUSES = {JobStatus.pending, JobStatus.running}


class JobService:
    """Encapsulates job persistence and dispatch logic."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.quota_service = QuotaService(session)

    async def enqueue(self, owner: User, payload: JobCreate) -> Job:
        await enforce_quota(self.quota_service, owner, 1)
        batch: JobBatch | None = None
        if payload.batch_id:
            batch = await self._get_batch(payload.batch_id, owner)
            batch.total_jobs += 1
            batch.pending_count += 1

        job = self._build_job(owner, payload, batch)
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)

        try:
            self._dispatch(job)
        except Exception as exc:  # pragma: no cover - broker issues
            job.status = JobStatus.failed
            job.error = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            job.result = job.result or _empty_result(job)
            if batch:
                _apply_batch_transition(batch, JobStatus.pending, JobStatus.failed)
            await self.session.commit()
            raise
        return job

    async def enqueue_batch(
        self, owner: User, payload: JobBatchCreate
    ) -> tuple[JobBatch, list[Job]]:
        if not payload.jobs:
            raise ValueError("Batch requires at least one job")
        await enforce_quota(self.quota_service, owner, len(payload.jobs))

        batch = JobBatch(
            name=payload.name,
            description=payload.description,
            payload=payload.payload,
            owner_id=owner.id,
            total_jobs=len(payload.jobs),
            pending_count=len(payload.jobs),
        )
        self.session.add(batch)
        await self.session.flush()
        jobs: list[Job] = []
        for job_payload in payload.jobs:
            job = self._build_job(owner, job_payload, batch)
            jobs.append(job)
            self.session.add(job)

        await self.session.commit()
        for job in jobs:
            try:
                self._dispatch(job)
            except Exception as exc:  # pragma: no cover - broker issues
                job.status = JobStatus.failed
                job.error = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                job.result = job.result or _empty_result(job)
                _apply_batch_transition(batch, JobStatus.pending, JobStatus.failed)
                await self.session.commit()
                raise

        await self.session.refresh(batch)
        return batch, jobs

    async def cancel(self, job_id: str, requester: User) -> bool:
        job = await self._get_job(job_id, requester)
        if not job:
            return False
        if job.status not in CANCELABLE_STATUSES:
            return False
        batch = None
        if job.batch_id:
            batch = await self.session.get(JobBatch, job.batch_id)
        _finalize_job_record(job, batch, JobStatus.canceled)
        await self.session.commit()
        return True

    def _normalize_working_dir(self, requested: str | None) -> str:
        candidate = (
            Path(requested or settings.default_working_dir).expanduser().resolve()
        )
        allowed = [
            Path(path).expanduser().resolve() for path in settings.allowed_workdirs
        ]
        if allowed and not any(self._is_within(candidate, base) for base in allowed):
            raise ValueError("Working directory outside allowed paths")
        return str(candidate)

    @staticmethod
    def _is_within(candidate: Path, base: Path) -> bool:
        try:
            candidate.relative_to(base)
        except ValueError:
            return False
        return True

    @staticmethod
    def _sanitize_env(env: dict[str, str] | None) -> dict[str, str] | None:
        if not env:
            return None
        return {str(key): str(value) for key, value in env.items()}

    def _build_job(
        self, owner: User, payload: JobCreate, batch: JobBatch | None
    ) -> Job:
        working_dir = self._normalize_working_dir(payload.working_dir)
        return Job(
            name=payload.name,
            payload=payload.payload,
            queue=payload.queue or settings.default_queue,
            priority=payload.priority,
            owner_id=owner.id,
            scheduled_at=payload.scheduled_at,
            command=payload.command,
            working_dir=working_dir,
            env=self._sanitize_env(payload.env),
            batch_id=batch.id if batch else payload.batch_id,
        )

    async def _get_batch(self, batch_id: UUID, owner: User) -> JobBatch:
        batch = await self.session.get(JobBatch, batch_id)
        if not batch:
            raise ValueError("Batch not found")
        if batch.owner_id != owner.id and owner.role != UserRole.admin:
            raise ValueError("Batch not accessible")
        return batch

    async def _get_batch_for_request(
        self, batch_id: str, requester: User
    ) -> JobBatch | None:
        try:
            batch_uuid = UUID(batch_id)
        except ValueError:
            return None
        try:
            return await self._get_batch(batch_uuid, requester)
        except ValueError:
            return None

    async def _get_job(self, job_id: str, requester: User) -> Job | None:
        try:
            job_uuid = UUID(job_id)
        except ValueError:
            return None
        job = await self.session.get(Job, job_uuid)
        if not job:
            return None
        if job.owner_id != requester.id and requester.role != UserRole.admin:
            return None
        return job

    def _dispatch(self, job: Job) -> None:
        celery_app.send_task(
            "jobrunner.tasks.execute_job",
            args=[str(job.id)],
            kwargs={},
            queue=job.queue,
        )

    async def delete(self, job_id: str, requester: User) -> bool:
        job = await self._get_job(job_id, requester)
        if not job:
            return False
        if job.status in CANCELABLE_STATUSES:
            raise ValueError("Cancel the job before deleting it")
        batch = None
        if job.batch_id:
            batch = await self.session.get(JobBatch, job.batch_id)
            if batch:
                _remove_job_from_batch(batch, job.status)
        await self.session.delete(job)
        await self.session.commit()
        return True

    async def force_complete(
        self,
        job_id: str,
        requester: User,
        *,
        status: JobStatus,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> Job | None:
        if status not in TERMINAL_STATUSES:
            raise ValueError("Force-complete requires a terminal status")
        job = await self._get_job(job_id, requester)
        if not job:
            return None
        batch = None
        if job.batch_id:
            batch = await self.session.get(JobBatch, job.batch_id)
        _finalize_job_record(job, batch, status, stdout=stdout, stderr=stderr)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def cancel_batch(self, batch_id: str, requester: User) -> int | None:
        batch = await self._get_batch_for_request(batch_id, requester)
        if not batch:
            return None
        jobs_result = await self.session.execute(
            select(Job).where(
                Job.batch_id == batch.id,
                Job.status.in_(tuple(CANCELABLE_STATUSES)),
            )
        )
        jobs = jobs_result.scalars().all()
        for job in jobs:
            _finalize_job_record(job, batch, JobStatus.canceled)
        await self.session.commit()
        return len(jobs)

    async def force_complete_batch(
        self,
        batch_id: str,
        requester: User,
        *,
        status: JobStatus,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> int | None:
        if status not in TERMINAL_STATUSES:
            raise ValueError("Force-complete requires a terminal status")
        batch = await self._get_batch_for_request(batch_id, requester)
        if not batch:
            return None
        jobs_result = await self.session.execute(
            select(Job).where(
                Job.batch_id == batch.id,
                Job.status.in_(tuple(CANCELABLE_STATUSES)),
            )
        )
        jobs = jobs_result.scalars().all()
        for job in jobs:
            _finalize_job_record(
                job,
                batch,
                status,
                stdout=stdout,
                stderr=stderr,
            )
        await self.session.commit()
        return len(jobs)

    async def delete_batch(self, batch_id: str, requester: User) -> bool:
        batch = await self._get_batch_for_request(batch_id, requester)
        if not batch:
            return False
        if batch.pending_count > 0 or batch.running_count > 0:
            raise ValueError("Stop the batch before deleting it")
        jobs_result = await self.session.execute(
            select(Job).where(Job.batch_id == batch.id)
        )
        for job in jobs_result.scalars().all():
            await self.session.delete(job)
        await self.session.delete(batch)
        await self.session.commit()
        return True


async def update_job_status(job_id: UUID, status: JobStatus, **fields) -> None:
    from ..database import (
        async_session_factory,
    )  # Imported lazily to avoid worker import cycles

    async with async_session_factory() as session:
        job = await session.get(Job, job_id)
        if not job:
            return
        previous_status = job.status
        job.status = status
        for key, value in fields.items():
            setattr(job, key, value)

        if job.batch_id:
            batch = await session.get(JobBatch, job.batch_id)
            if batch:
                _apply_batch_transition(batch, previous_status, status)
        await session.commit()


def _finalize_job_record(
    job: Job,
    batch: JobBatch | None,
    new_status: JobStatus,
    *,
    stdout: str | None = None,
    stderr: str | None = None,
) -> None:
    previous_status = job.status
    job.status = new_status
    now = datetime.now(timezone.utc)
    if job.started_at is None:
        job.started_at = now
    job.completed_at = now
    payload = job.result or _empty_result(job)
    if stdout is not None:
        payload["stdout"] = stdout
    if stderr is not None:
        payload["stderr"] = stderr
    job.result = payload
    if batch:
        _apply_batch_transition(batch, previous_status, new_status)


def _apply_batch_transition(
    batch: JobBatch, old_status: JobStatus, new_status: JobStatus
) -> None:
    if old_status != new_status:
        _decrement_batch(batch, old_status)
        _increment_batch(batch, new_status)

    if new_status == JobStatus.running and batch.started_at is None:
        batch.started_at = datetime.now(timezone.utc)

    if batch.pending_count == 0 and batch.running_count == 0:
        finished = batch.success_count + batch.failed_count + batch.canceled_count
        if finished >= batch.total_jobs and batch.completed_at is None:
            batch.completed_at = datetime.now(timezone.utc)


def _increment_batch(batch: JobBatch, status: JobStatus) -> None:
    attr = f"{status.value}_count"
    if hasattr(batch, attr):
        setattr(batch, attr, getattr(batch, attr) + 1)


def _decrement_batch(batch: JobBatch, status: JobStatus) -> None:
    attr = f"{status.value}_count"
    if hasattr(batch, attr):
        current = getattr(batch, attr)
        setattr(batch, attr, max(0, current - 1))


def _remove_job_from_batch(batch: JobBatch, status: JobStatus) -> None:
    _decrement_batch(batch, status)
    if batch.total_jobs > 0:
        batch.total_jobs -= 1
    if batch.total_jobs == 0:
        batch.pending_count = 0
        batch.running_count = 0
        batch.success_count = 0
        batch.failed_count = 0
        batch.canceled_count = 0
        batch.completed_at = datetime.now(timezone.utc)
    elif batch.pending_count == 0 and batch.running_count == 0:
        finished = batch.success_count + batch.failed_count + batch.canceled_count
        if finished >= batch.total_jobs:
            batch.completed_at = datetime.now(timezone.utc)


def _empty_result(job: Job) -> dict[str, Any]:
    return {
        "return_code": None,
        "stdout": "",
        "stderr": "",
        "command": job.command,
        "working_dir": job.working_dir,
    }
