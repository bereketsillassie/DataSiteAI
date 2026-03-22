"""
app/dependencies.py
────────────────────
FastAPI dependency injection functions.

Redis has been removed — caching uses PostgreSQL (Supabase) directly.
The integration_cache table in Supabase serves as the cache store.

Usage in endpoints:
    @router.get("/example")
    async def my_endpoint(db: AsyncSession = Depends(get_db)):
        ...
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.
    Session is automatically closed when the request ends.
    """
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()