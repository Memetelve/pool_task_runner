"""Database engine and session utilities."""

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .models import Base

engine = create_async_engine(settings.database_url, echo=False, future=True)
async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields an async SQLAlchemy session."""
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Create database tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_schema_upgrades)


def _ensure_schema_upgrades(sync_conn) -> None:
    inspector = inspect(sync_conn)
    tables = set(inspector.get_table_names())
    dialect = sync_conn.dialect.name

    if "jobs" in tables:
        job_columns = {column["name"] for column in inspector.get_columns("jobs")}
        if "batch_id" not in job_columns:
            if dialect == "sqlite":
                sync_conn.execute(text("ALTER TABLE jobs ADD COLUMN batch_id TEXT"))
            else:
                sync_conn.execute(text("ALTER TABLE jobs ADD COLUMN batch_id UUID"))

    if "users" in tables:
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "max_concurrent_jobs" not in user_columns:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN max_concurrent_jobs INTEGER"))
