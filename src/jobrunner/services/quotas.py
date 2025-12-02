"""Quota management helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import Job, JobStatus, SystemSetting, User

GLOBAL_LIMIT_KEY = "max_jobs_per_user"
ACTIVE_STATUSES = (JobStatus.pending, JobStatus.running)


class QuotaService:
    """Reads and writes per-user job quotas."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_global_limit(self) -> int:
        record = await self.session.get(SystemSetting, GLOBAL_LIMIT_KEY)
        if not record:
            return settings.default_max_jobs_per_user
        return self._coerce_limit(record.value)

    async def set_global_limit(self, limit: int) -> int:
        self._validate_limit(limit)
        record = await self.session.get(SystemSetting, GLOBAL_LIMIT_KEY)
        payload: Any = {"limit": limit}
        if record:
            record.value = payload
        else:
            record = SystemSetting(key=GLOBAL_LIMIT_KEY, value=payload)
            self.session.add(record)
        await self.session.commit()
        return limit

    async def get_effective_limit(self, user: User) -> int:
        if user.max_concurrent_jobs is not None:
            return user.max_concurrent_jobs
        return await self.get_global_limit()

    async def count_active_jobs(self, user_id: UUID) -> int:
        query: Select[tuple[int]] = select(func.count()).select_from(Job).where(
            Job.owner_id == user_id,
            Job.status.in_(tuple(ACTIVE_STATUSES)),
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    @staticmethod
    def _coerce_limit(value: Any) -> int:
        if isinstance(value, dict):
            candidate = value.get("limit")
            if candidate is None:
                candidate = value.get("value")
            if candidate is not None:
                return int(candidate)
        if value is None:
            return settings.default_max_jobs_per_user
        return int(value)

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if limit <= 0:
            raise ValueError("Limit must be greater than zero")


async def enforce_quota(
    quota_service: QuotaService,
    user: User,
    planned_jobs: int,
) -> None:
    """Raise ValueError if the planned submission exceeds available slots."""

    effective_limit = await quota_service.get_effective_limit(user)
    active_jobs = await quota_service.count_active_jobs(user.id)
    if active_jobs + planned_jobs > effective_limit:
        raise ValueError(
            f"Quota exceeded: {active_jobs} active job(s), limit is {effective_limit},"
            f" attempted to add {planned_jobs}."
        )
