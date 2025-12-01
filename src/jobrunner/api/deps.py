"""Shared dependencies for API routers."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user, require_admin
from ..database import get_session
from ..models import User


async def get_db_session(session: AsyncSession = Depends(get_session)) -> AsyncSession:
    return session


async def current_user(user: User = Depends(get_current_user)) -> User:
    return user


async def admin_user(user: User = Depends(require_admin)) -> User:
    return user
