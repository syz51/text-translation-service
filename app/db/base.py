"""SQLAlchemy database setup."""

from collections.abc import AsyncGenerator
import logging
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


# Create data directory if it doesn't exist
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

# Database URL
DATABASE_URL = f"sqlite+aiosqlite:///{settings.database_path}"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.environment == "development",
    future=True,
)


# Enable foreign keys for SQLite
def _set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key constraints for SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


event.listen(engine.sync_engine, "connect", _set_sqlite_pragma)

# Create async session factory
SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Dependency for getting async database sessions."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized")
