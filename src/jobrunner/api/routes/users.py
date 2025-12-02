"""User management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...api import deps
from ...auth import get_password_hash
from ...models import User
from ...schemas import Message, UserCreate, UserRead, UserUpdate

router = APIRouter()


@router.post("", response_model=UserRead, status_code=201)
async def create_user(
    payload: UserCreate,
    session: AsyncSession = Depends(deps.get_db_session),
    _: User = Depends(deps.admin_user),
) -> UserRead:
    user = User(
        email=payload.email,
        role=payload.role,
        hashed_password=get_password_hash(payload.password),
        max_concurrent_jobs=payload.max_concurrent_jobs,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(deps.current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get("", response_model=list[UserRead])
async def list_users(
    session: AsyncSession = Depends(deps.get_db_session),
    _: User = Depends(deps.admin_user),
) -> list[UserRead]:
    result = await session.execute(select(User))
    return [UserRead.model_validate(row) for row in result.scalars().all()]


@router.delete("/{user_id}", response_model=Message)
async def deactivate_user(
    user_id: str,
    session: AsyncSession = Depends(deps.get_db_session),
    _: User = Depends(deps.admin_user),
) -> Message:
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return Message(detail="User deactivated if it existed")

    target = await session.get(User, user_uuid)
    if target:
        target.is_active = False
        await session.commit()
    return Message(detail="User deactivated if it existed")


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    session: AsyncSession = Depends(deps.get_db_session),
    _: User = Depends(deps.admin_user),
) -> UserRead:
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target = await session.get(User, user_uuid)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if payload.role is not None:
        target.role = payload.role
    if payload.password is not None:
        target.hashed_password = get_password_hash(payload.password)
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if "max_concurrent_jobs" in payload.model_fields_set:
        target.max_concurrent_jobs = payload.max_concurrent_jobs

    await session.commit()
    await session.refresh(target)
    return UserRead.model_validate(target)
