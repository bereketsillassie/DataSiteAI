"""
app/db/session.py
──────────────────
Async SQLAlchemy engine and session factory.
Supports PostgreSQL + PostGIS via asyncpg driver.
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

# The async engine — one per process, shared across all requests
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.LOG_LEVEL == "DEBUG"),
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before use (handles DB restarts)
)

# Session factory — use this to create session instances
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def init_db():
    """Called at app startup. Verifies DB connectivity."""
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        # Don't crash startup — health endpoint will report the error


async def close_db():
    """Called at app shutdown. Disposes the connection pool."""
    await engine.dispose()
    logger.info("Database connection pool closed")
