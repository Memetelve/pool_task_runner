"""Health check endpoints."""

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...database import get_session
from ...schemas import HealthResponse

router = APIRouter()
redis_client = redis.from_url(settings.redis_url)


@router.get("/health", response_model=HealthResponse)
async def get_health(session: AsyncSession = Depends(get_session)) -> HealthResponse:
    """Report readiness of backing services."""
    db_status = "ok"
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - surfaced to API clients
        db_status = "error"

    redis_status = "ok"
    try:
        await redis_client.ping()
    except Exception:  # pragma: no cover - surfaced to API clients
        redis_status = "error"

    return HealthResponse(status="ok", redis=redis_status, database=db_status)
