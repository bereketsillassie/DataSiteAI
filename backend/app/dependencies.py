"""
app/dependencies.py
────────────────────
FastAPI dependency injection functions.
<<<<<<< HEAD

Redis has been removed — caching uses PostgreSQL (Supabase) directly.
The integration_cache table in Supabase serves as the cache store.

Usage in endpoints:
=======
These are used with Depends() in endpoint functions.

Example usage in an endpoint:
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    @router.get("/example")
    async def my_endpoint(db: AsyncSession = Depends(get_db)):
        ...
"""

import logging
from typing import AsyncGenerator

<<<<<<< HEAD
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

=======
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level connection instances — initialized during app lifespan startup
_redis_client: aioredis.Redis | None = None


async def init_redis():
    """Called once at startup to create the Redis connection pool."""
    global _redis_client
    try:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        # Test the connection
        await _redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Continuing without cache.")
        _redis_client = None


async def close_redis():
    """Called on shutdown to cleanly close the Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


async def get_redis() -> aioredis.Redis | None:
    """
    FastAPI dependency that yields the shared Redis client.
    Returns None if Redis is unavailable — callers must handle this.
    """
    return _redis_client

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.
<<<<<<< HEAD
    Session is automatically closed when the request ends.
    """
    from app.db.session import AsyncSessionLocal

=======
    The session is automatically closed when the request ends.
    """
    from app.db.session import AsyncSessionLocal
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
<<<<<<< HEAD
            await session.close()
=======
            await session.close()
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
