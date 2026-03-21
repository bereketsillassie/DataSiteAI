"""
app/config.py
─────────────
Application configuration loaded from environment variables.
Uses pydantic-settings so every variable has type validation and a clear default.

All settings are available via:
    from app.config import settings
    settings.DATABASE_URL
    settings.MOCK_INTEGRATIONS
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Literal
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    ENVIRONMENT: Literal["development", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    MOCK_INTEGRATIONS: bool = False

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/datacenter"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── Google Cloud ──────────────────────────────────────────────────────────
    GOOGLE_CLOUD_PROJECT: str = "local-dev"
    GCS_BUCKET_NAME: str = "datacenter-selector-layers"
    GEE_SERVICE_ACCOUNT: str = ""
    GEE_KEY_FILE: str = ""

    # ── External API Keys ─────────────────────────────────────────────────────
    EIA_API_KEY: str = ""
    CENSUS_API_KEY: str = ""
    NOAA_API_KEY: str = ""
    AIRNOW_API_KEY: str = ""

    # ── Caching ───────────────────────────────────────────────────────────────
    CACHE_TTL_HOURS: int = 24
    GEE_CACHE_TTL_HOURS: int = 168
    LISTINGS_CACHE_TTL_HOURS: int = 168

    # ── Analysis defaults ─────────────────────────────────────────────────────
    GRID_RESOLUTION_DEFAULT_KM: float = 5.0
    MAX_BBOX_AREA_SQ_KM: float = 50000.0

    @field_validator("MOCK_INTEGRATIONS", mode="before")
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes")
        return v


# Single shared instance — import this everywhere
settings = Settings()
