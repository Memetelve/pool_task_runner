"""Administrative utility endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...api import deps
from ...models import User
from ...schemas import QuotaSummary, QuotaUserUpdate, QuotaValue, UserQuota
from ...services import QuotaService

router = APIRouter()


@router.get("/limits", response_model=QuotaSummary)
async def read_limits(
    session: AsyncSession = Depends(deps.get_db_session),
    _: User = Depends(deps.admin_user),
) -> QuotaSummary:
    quota_service = QuotaService(session)
    default_limit = await quota_service.get_global_limit()
    result = await session.execute(
        select(User).where(User.max_concurrent_jobs.is_not(None)).order_by(User.email)
    )
    overrides = [
        UserQuota(
            id=user.id,
            email=user.email,
            role=user.role,
            max_jobs=user.max_concurrent_jobs,
        )
        for user in result.scalars().all()
    ]
    return QuotaSummary(default_limit=default_limit, overrides=overrides)


@router.post("/limits/global", response_model=QuotaValue)
async def set_global_limit(
    payload: QuotaValue,
    session: AsyncSession = Depends(deps.get_db_session),
    _: User = Depends(deps.admin_user),
) -> QuotaValue:
    quota_service = QuotaService(session)
    try:
        limit = await quota_service.set_global_limit(payload.max_jobs)
    except ValueError as exc:  # pragma: no cover - validation guard
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return QuotaValue(max_jobs=limit)


@router.post("/limits/users/{user_id}", response_model=UserQuota)
async def set_user_limit(
    user_id: str,
    payload: QuotaUserUpdate,
    session: AsyncSession = Depends(deps.get_db_session),
    _: User = Depends(deps.admin_user),
) -> UserQuota:
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target = await session.get(User, user_uuid)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.max_jobs is not None and payload.max_jobs <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Limit must be greater than zero")

    target.max_concurrent_jobs = payload.max_jobs
    await session.commit()
    await session.refresh(target)
    return UserQuota(
        id=target.id,
        email=target.email,
        role=target.role,
        max_jobs=target.max_concurrent_jobs,
    )
