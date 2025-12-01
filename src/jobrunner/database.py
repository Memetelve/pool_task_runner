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
        await conn.run_sync(_ensure_batch_columns)


def _ensure_batch_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "jobs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("jobs")}
    if "batch_id" in columns:
        return

    dialect = sync_conn.dialect.name
    if dialect == "sqlite":
        sync_conn.execute(text("ALTER TABLE jobs ADD COLUMN batch_id TEXT"))
    else:
        sync_conn.execute(text("ALTER TABLE jobs ADD COLUMN batch_id UUID"))
