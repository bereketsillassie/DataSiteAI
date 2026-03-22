"""
app/db/session.py
──────────────────
Async SQLAlchemy engine and session factory.
<<<<<<< HEAD
PostgreSQL + PostGIS via asyncpg driver.
=======
Supports PostgreSQL + PostGIS via asyncpg driver.
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

<<<<<<< HEAD
=======
# The async engine — one per process, shared across all requests
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.LOG_LEVEL == "DEBUG"),
    pool_size=5,
    max_overflow=10,
<<<<<<< HEAD
    pool_pre_ping=True,
)

=======
    pool_pre_ping=True,  # Verify connections before use (handles DB restarts)
)

# Session factory — use this to create session instances
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

<<<<<<< HEAD
class Base(DeclarativeBase):
    pass

async def init_db():
=======

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


async def init_db():
    """Called at app startup. Verifies DB connectivity."""
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
<<<<<<< HEAD

async def close_db():
    await engine.dispose()
    logger.info("Database connection pool closed")
=======
        # Don't crash startup — health endpoint will report the error


async def close_db():
    """Called at app shutdown. Disposes the connection pool."""
    await engine.dispose()
    logger.info("Database connection pool closed")
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
