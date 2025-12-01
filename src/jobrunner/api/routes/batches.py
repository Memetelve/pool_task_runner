"""Endpoints for managing job batches."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...api import deps
from ...models import Job, JobBatch, User, UserRole
from ...schemas import (
    BatchForceCompleteRequest,
    JobBatchCreate,
    JobBatchDetail,
    JobBatchList,
    JobBatchRead,
    JobRead,
    Message,
)
from ...services.jobs import JobService

router = APIRouter()


@router.post("", response_model=JobBatchDetail, status_code=status.HTTP_202_ACCEPTED)
async def create_job_batch(
    payload: JobBatchCreate,
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> JobBatchDetail:
    service = JobService(session)
    try:
        batch, jobs = await service.enqueue_batch(owner=user, payload=payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    batch_read = JobBatchRead.model_validate(batch)
    job_payloads = [JobRead.model_validate(obj) for obj in jobs]
    return JobBatchDetail(**batch_read.model_dump(), jobs=job_payloads)


@router.get("", response_model=JobBatchList)
async def list_job_batches(
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> JobBatchList:
    query: Select[tuple[JobBatch]] = select(JobBatch)
    if user.role != UserRole.admin:
        query = query.where(JobBatch.owner_id == user.id)

    result = await session.execute(query.order_by(JobBatch.created_at.desc()))
    items = result.scalars().all()

    count_query = select(func.count()).select_from(JobBatch)
    if user.role != UserRole.admin:
        count_query = count_query.where(JobBatch.owner_id == user.id)
    total = (await session.execute(count_query)).scalar_one()

    return JobBatchList(
        items=[JobBatchRead.model_validate(obj) for obj in items], total=total
    )


@router.get("/{batch_id}", response_model=JobBatchDetail)
async def get_job_batch(
    batch_id: str,
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> JobBatchDetail:
    try:
        batch_uuid = UUID(batch_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found"
        )

    batch = await session.get(JobBatch, batch_uuid)
    if not batch or (batch.owner_id != user.id and user.role != UserRole.admin):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found"
        )

    jobs_query = (
        select(Job).where(Job.batch_id == batch_uuid).order_by(Job.created_at.desc())
    )
    jobs_result = await session.execute(jobs_query)
    jobs = jobs_result.scalars().all()

    batch_read = JobBatchRead.model_validate(batch)
    job_payloads = [JobRead.model_validate(obj) for obj in jobs]
    return JobBatchDetail(**batch_read.model_dump(), jobs=job_payloads)


@router.post("/{batch_id}/cancel", response_model=Message)
async def cancel_job_batch(
    batch_id: str,
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> Message:
    service = JobService(session)
    canceled = await service.cancel_batch(batch_id=batch_id, requester=user)
    if canceled is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found"
        )
    detail = (
        "No pending or running jobs to cancel"
        if canceled == 0
        else f"Cancel signal issued for {canceled} job(s)"
    )
    return Message(detail=detail)


@router.post("/{batch_id}/force-complete", response_model=Message)
async def force_complete_job_batch(
    batch_id: str,
    payload: BatchForceCompleteRequest,
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> Message:
    service = JobService(session)
    try:
        updated = await service.force_complete_batch(
            batch_id=batch_id,
            requester=user,
            status=payload.status,
            stdout=payload.stdout,
            stderr=payload.stderr,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found"
        )
    detail = (
        "No pending or running jobs to force complete"
        if updated == 0
        else f"Forced {updated} job(s) to {payload.status}"
    )
    return Message(detail=detail)


@router.delete("/{batch_id}", response_model=Message)
async def delete_job_batch(
    batch_id: str,
    session: AsyncSession = Depends(deps.get_db_session),
    user: User = Depends(deps.current_user),
) -> Message:
    service = JobService(session)
    try:
        deleted = await service.delete_batch(batch_id=batch_id, requester=user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found"
        )
    return Message(detail="Batch deleted")
