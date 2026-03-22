"""
app/integrations/base.py
─────────────────────────
Base class for all integration clients.

CACHING: Uses PostgreSQL (Supabase) via its OWN independent session.
  The db_session parameter accepted here is stored but NOT used for cache
  operations. Cache reads/writes create their own short-lived session via
  AsyncSessionLocal to avoid concurrent operation errors on the shared
  request session (SQLAlchemy async sessions are not thread/task safe).

  In-memory dict (_memory_cache) serves as a fast same-process layer so
  cache warming still works even if DB is temporarily unreachable.
"""

import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.models.domain import IntegrationError

logger = logging.getLogger(__name__)

# In-memory fallback cache — (data, expires_at) per key
_memory_cache: dict[str, tuple[Any, datetime]] = {}


class BaseIntegrationClient:
    """
    Base class for all external data source integrations.

    IMPORTANT: Cache operations use their own DB session (not self.db).
    This prevents concurrent operation errors when multiple scorers run
    in parallel and all try to write to the cache simultaneously.
    """

    def __init__(self, db_session=None, settings=None):
        from app.config import settings as default_settings
        self.db = db_session          # kept for reference, NOT used for cache
        self.settings = settings or default_settings
        self.mock = self.settings.MOCK_INTEGRATIONS
        self.source_name = "base"
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"User-Agent": "DataCenter-Site-Selector/1.0 (contact@example.com)"},
                follow_redirects=True,
            )
        return self._http_client

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ── Cache key ──────────────────────────────────────────────────────────────

    def _cache_key(self, operation: str, *args) -> str:
        args_str = ":".join(str(a) for a in args)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:12]
        return f"integration:{self.source_name}:{operation}:{args_hash}"

    # ── Cache read ─────────────────────────────────────────────────────────────

    async def _get_cached(self, key: str) -> Optional[Any]:
        """
        Check in-memory cache first, then PostgreSQL via its own session.
        Never raises — returns None on any failure.
        """
        now = datetime.now(timezone.utc)

        # 1. In-memory (fastest, zero DB cost)
        if key in _memory_cache:
            data, expires = _memory_cache[key]
            if expires > now:
                logger.debug(f"Memory cache HIT: {key}")
                return data
            del _memory_cache[key]

        # 2. PostgreSQL — own session, isolated from request session
        try:
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import text
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    text(
                        "SELECT data FROM integration_cache "
                        "WHERE cache_key = :key AND expires_at > NOW()"
                    ),
                    {"key": key},
                )
                row = result.fetchone()
                if row:
                    logger.debug(f"DB cache HIT: {key}")
                    data = row[0]
                    # Backfill memory cache (5 min) to avoid repeated DB hits
                    _memory_cache[key] = (data, now + timedelta(minutes=5))
                    return data
        except Exception as e:
            logger.debug(f"DB cache get failed for {key}: {e}")

        return None

    # ── Cache write ────────────────────────────────────────────────────────────

    async def _set_cached(self, key: str, data: Any, ttl_hours: int = 24) -> None:
        """
        Write to in-memory cache and PostgreSQL via its own session.
        Never raises — failures are always silent.
        """
        now     = datetime.now(timezone.utc)
        expires = now + timedelta(hours=ttl_hours)

        # Always write to memory cache for same-process speed
        _memory_cache[key] = (data, expires)

        # Write to PostgreSQL with its own dedicated session
        try:
            from app.db.session import AsyncSessionLocal
            from sqlalchemy import text
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("""
                        INSERT INTO integration_cache (cache_key, data, expires_at)
                        VALUES (:key, :data, :expires)
                        ON CONFLICT (cache_key) DO UPDATE
                            SET data       = EXCLUDED.data,
                                expires_at = EXCLUDED.expires_at
                    """),
                    {
                        "key":     key,
                        "data":    json.dumps(data),
                        "expires": expires,
                    },
                )
                await session.commit()
            logger.debug(f"Cached {key} for {ttl_hours}h")
        except Exception as e:
            logger.debug(f"DB cache set failed for {key}: {e}")

    # ── HTTP with retry ────────────────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.TransportError),
        reraise=False,
    )
    async def _fetch_with_retry(
        self,
        url: str,
        params=None,
        headers: Optional[dict] = None,
        method: str = "GET",
        json_body: Optional[dict] = None,
    ) -> dict:
        """
        Fetch a URL with automatic retry on transport errors.
        Raises IntegrationError on HTTP errors or after all retries fail.
        Treats 504 as retriable.
        """
        client = await self._get_http_client()
        try:
            if method == "GET":
                response = await client.get(url, params=params, headers=headers)
            elif method == "POST":
                response = await client.post(
                    url, params=params, headers=headers, json=json_body
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 429:
                raise IntegrationError(
                    source=self.source_name,
                    message=f"Rate limited by {url}.",
                    status_code=429,
                )
            if response.status_code == 504:
                raise IntegrationError(
                    source=self.source_name,
                    message=f"Gateway timeout from {url}.",
                    status_code=504,
                )
            if response.status_code >= 400:
                raise IntegrationError(
                    source=self.source_name,
                    message=f"HTTP {response.status_code} from {url}: {response.text[:200]}",
                    status_code=response.status_code,
                )
            return response.json()

        except IntegrationError:
            raise
        except httpx.TransportError as e:
            logger.warning(f"Transport error fetching {url}: {e}. Retrying...")
            raise
        except Exception as e:
            raise IntegrationError(
                source=self.source_name,
                message=f"Unexpected error fetching {url}: {e}",
            )

    async def _fetch_geojson(self, url: str, params=None) -> dict:
        client = await self._get_http_client()
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise IntegrationError(
                source=self.source_name,
                message=f"HTTP {e.response.status_code} fetching GeoJSON from {url}",
                status_code=e.response.status_code,
            )
        except Exception as e:
            raise IntegrationError(
                source=self.source_name,
                message=f"Error fetching GeoJSON from {url}: {e}",
            )