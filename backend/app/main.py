"""
app/main.py
────────────
FastAPI application factory and startup/shutdown lifecycle.
All routers are registered here. CORS is configured here.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown lifecycle for the FastAPI app.
    Runs on startup: initialize DB connection pool, Redis connection.
    Runs on shutdown: close all connections cleanly.
    """
    logger.info("Starting DataCenter Site Selector API")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Mock integrations: {settings.MOCK_INTEGRATIONS}")

    # Import here to avoid circular imports
    from app.db.session import init_db, close_db
    from app.dependencies import init_redis, close_redis

    await init_db()
    await init_redis()

    logger.info("All connections initialized. Ready to serve requests.")
    yield

    # Shutdown
    logger.info("Shutting down...")
    await close_db()
    await close_redis()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="DataCenter Site Selector API",
    description=(
        "Analyzes geographic, environmental, utility, economic, and geological data "
        "to score and rank land across the USA for data center suitability. "
        "Returns scored grid cells, GeoJSON layers, and land listings."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# In development, allow all origins so the frontend partner can connect
# from any local port. In production, restrict to the deployed frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else [
        "https://datacenter-selector.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
from app.api.v1.router import router as v1_router  # noqa: E402
app.include_router(v1_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "DataCenter Site Selector API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
