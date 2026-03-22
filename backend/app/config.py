"""
app/config.py
─────────────
Application configuration loaded from environment variables.
<<<<<<< HEAD
Uses pydantic-settings for type validation and clear defaults.

Import everywhere as:
=======
Uses pydantic-settings so every variable has type validation and a clear default.

All settings are available via:
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    from app.config import settings
    settings.DATABASE_URL
    settings.MOCK_INTEGRATIONS
"""

<<<<<<< HEAD
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
=======
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Literal
import os
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

<<<<<<< HEAD
    # ── Application ───────────────────────────────────────────────────────────
=======
    # ── Application ──────────────────────────────────────────────────────────
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    ENVIRONMENT: Literal["development", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    MOCK_INTEGRATIONS: bool = False

<<<<<<< HEAD
    # ── Database (Supabase PostgreSQL) ────────────────────────────────────────
    # Get from: supabase.com → project → Settings → Database → URI connection string
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/datacenter"

=======
    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/datacenter"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    # ── Google Cloud ──────────────────────────────────────────────────────────
    GOOGLE_CLOUD_PROJECT: str = "local-dev"
    GCS_BUCKET_NAME: str = "datacenter-selector-layers"
    GEE_SERVICE_ACCOUNT: str = ""
    GEE_KEY_FILE: str = ""

<<<<<<< HEAD
    # ── External API Keys (all free) ──────────────────────────────────────────
    EIA_API_KEY: str = ""        # api.eia.gov
    CENSUS_API_KEY: str = ""     # api.census.gov
    NOAA_API_KEY: str = ""       # ncei.noaa.gov
    AIRNOW_API_KEY: str = ""     # airnowapi.org

    # ── Cache TTLs ────────────────────────────────────────────────────────────
    CACHE_TTL_HOURS: int = 24
    GEE_CACHE_TTL_HOURS: int = 168       # 7 days — GEE data changes slowly
    LISTINGS_CACHE_TTL_HOURS: int = 168  # 7 days — listing data refreshed weekly
=======
    # ── External API Keys ─────────────────────────────────────────────────────
    EIA_API_KEY: str = ""
    CENSUS_API_KEY: str = ""
    NOAA_API_KEY: str = ""
    AIRNOW_API_KEY: str = ""

    # ── Caching ───────────────────────────────────────────────────────────────
    CACHE_TTL_HOURS: int = 24
    GEE_CACHE_TTL_HOURS: int = 168
    LISTINGS_CACHE_TTL_HOURS: int = 168
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e

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
<<<<<<< HEAD
settings = Settings()
=======
settings = Settings()
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
