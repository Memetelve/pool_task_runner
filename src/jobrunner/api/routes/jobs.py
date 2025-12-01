"""Job submission and status endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...api import deps
from ...models import Job, JobStatus, User, UserRole
from ...schemas import (
    JobCreate,
    JobForceCompleteRequest,
    JobList,
    JobLogs,
    JobRead,
    JobStats,
    Message,
)
from ...services.jobs import JobService

router = APIRouter()


@router.post("", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    payload: JobCreate,
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> JobRead:
    service = JobService(session)
    try:
        job = await service.enqueue(owner=user, payload=payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return JobRead.model_validate(job)


@router.get("", response_model=JobList)
async def list_jobs(
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
    status_filter: JobStatus | None = Query(
        default=None, description="Optional status filter"
    ),
    batch_id: UUID | None = Query(
        default=None, description="Optional batch identifier filter"
    ),
) -> JobList:
    query: Select[tuple[Job]] = select(Job)
    if status_filter:
        query = query.where(Job.status == status_filter)
    if batch_id:
        query = query.where(Job.batch_id == batch_id)
    if user.role != UserRole.admin:
        query = query.where(Job.owner_id == user.id)

    result = await session.execute(query.order_by(Job.created_at.desc()))
    items = result.scalars().all()

    count_query = select(func.count()).select_from(Job)
    if status_filter:
        count_query = count_query.where(Job.status == status_filter)
    if batch_id:
        count_query = count_query.where(Job.batch_id == batch_id)
    if user.role != UserRole.admin:
        count_query = count_query.where(Job.owner_id == user.id)
    total = (await session.execute(count_query)).scalar_one()

    return JobList(items=[JobRead.model_validate(obj) for obj in items], total=total)


@router.get("/stats", response_model=JobStats)
async def job_stats(
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> JobStats:
    query = select(Job.status, func.count()).group_by(Job.status)
    if user.role != UserRole.admin:
        query = query.where(Job.owner_id == user.id)

    result = await session.execute(query)
    counts = {row[0]: row[1] for row in result.all()}
    total = sum(counts.values())
    return JobStats(
        pending=counts.get(JobStatus.pending, 0),
        running=counts.get(JobStatus.running, 0),
        success=counts.get(JobStatus.success, 0),
        failed=counts.get(JobStatus.failed, 0),
        canceled=counts.get(JobStatus.canceled, 0),
        total=total,
    )


@router.get("/{job_id}/logs", response_model=JobLogs)
async def job_logs(
    job_id: str,
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> JobLogs:
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    job = await session.get(Job, job_uuid)
    if not job or (job.owner_id != user.id and user.role != UserRole.admin):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    if job.status in {JobStatus.pending, JobStatus.running} or not job.result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Logs not available yet"
        )

    payload = job.result or {}
    return JobLogs(
        id=job.id,
        stdout=payload.get("stdout", ""),
        stderr=payload.get("stderr", ""),
        return_code=payload.get("return_code"),
        command=payload.get("command", []),
        working_dir=payload.get("working_dir"),
    )


@router.get("/{job_id}", response_model=JobRead)
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> JobRead:
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )

    job = await session.get(Job, job_uuid)
    if not job or (job.owner_id != user.id and user.role != UserRole.admin):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return JobRead.model_validate(job)


@router.delete("/{job_id}", response_model=Message)
async def cancel_job(
    job_id: str,
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> Message:
    service = JobService(session)
    canceled = await service.cancel(job_id=job_id, requester=user)
    if not canceled:
        raise HTTPException(status_code=404, detail="Job not cancelable or missing")
    return Message(detail="Cancel signal issued")


@router.post("/{job_id}/force-complete", response_model=JobRead)
async def force_complete_job(
    job_id: str,
    payload: JobForceCompleteRequest,
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> JobRead:
    service = JobService(session)
    try:
        job = await service.force_complete(
            job_id=job_id,
            requester=user,
            status=payload.status,
            stdout=payload.stdout,
            stderr=payload.stderr,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return JobRead.model_validate(job)


@router.delete("/{job_id}/purge", response_model=Message)
async def delete_job(
    job_id: str,
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> Message:
    service = JobService(session)
    try:
        deleted = await service.delete(job_id=job_id, requester=user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )
    return Message(detail="Job removed")
