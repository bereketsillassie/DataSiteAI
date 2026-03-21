"""
app/api/v1/health.py
─────────────────────
GET /api/v1/health — system health check endpoint.
Used by Cloud Run health checks and the frontend to verify connectivity.
"""

import logging
from fastapi import APIRouter, Depends

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.dependencies import get_db, get_redis
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
    redis: aioredis.Redis | None = Depends(get_redis),
) -> HealthResponse:
    # Check PostgreSQL
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.warning(f"DB health check failed: {e}")
        db_status = "error"

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

    # Check GEE (mock-safe)
    from app.config import settings
    gee_status = "ok" if settings.MOCK_INTEGRATIONS else _check_gee()

    return HealthResponse(
        status="ok",
        db=db_status,
        redis=redis_status,
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
