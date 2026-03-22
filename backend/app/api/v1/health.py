"""
app/api/v1/health.py
─────────────────────
GET /api/v1/health — system health check endpoint.
Used by Cloud Run health checks and the frontend to verify connectivity.
"""

import logging
from fastapi import APIRouter, Depends

<<<<<<< HEAD
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.dependencies import get_db
=======
import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.dependencies import get_db, get_redis
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
from app.models.responses import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description="Checks connectivity to PostgreSQL, Redis, and GEE. Returns 200 even if individual services are down.",
)
async def health_check(
    db: AsyncSession = Depends(get_db),
<<<<<<< HEAD
=======
    redis: aioredis.Redis | None = Depends(get_redis),
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
) -> HealthResponse:
    # Check PostgreSQL
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.warning(f"DB health check failed: {e}")
        db_status = "error"

<<<<<<< HEAD
=======
    # Check Redis
    redis_status = "ok"
    if redis is None:
        redis_status = "error"
    else:
        try:
            await redis.ping()
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            redis_status = "error"

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    # Check GEE (mock-safe)
    from app.config import settings
    gee_status = "ok" if settings.MOCK_INTEGRATIONS else _check_gee()

    return HealthResponse(
        status="ok",
        db=db_status,
<<<<<<< HEAD
=======
        redis=redis_status,
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        gee=gee_status,
    )


def _check_gee() -> str:
    """Quick GEE connectivity check — returns 'ok' or 'error'."""
    try:
        import ee
        ee.Initialize()
        return "ok"
    except Exception as e:
        logger.warning(f"GEE health check failed: {e}")
        return "error"
