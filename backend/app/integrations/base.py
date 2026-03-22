"""
app/integrations/base.py
─────────────────────────
Base class for all integration clients.
<<<<<<< HEAD

CACHING: Uses PostgreSQL (Supabase) via its OWN independent session.
  The db_session parameter accepted here is stored but NOT used for cache
  operations. Cache reads/writes create their own short-lived session via
  AsyncSessionLocal to avoid concurrent operation errors on the shared
  request session (SQLAlchemy async sessions are not thread/task safe).

  In-memory dict (_memory_cache) serves as a fast same-process layer so
  cache warming still works even if DB is temporarily unreachable.
=======
Every external data source client extends this class.

Key features:
  - Redis caching (check before fetch, set after fetch)
  - HTTP retry with exponential backoff via tenacity
  - Mock mode: return fixture data when settings.MOCK_INTEGRATIONS=True
  - Typed error handling: always raise IntegrationError, never raw exceptions
  - follow_redirects=True set globally on the shared HTTP client —
    do NOT pass it as a kwarg to _fetch_with_retry()
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
"""

import json
import logging
<<<<<<< HEAD
import hashlib
from datetime import datetime, timezone, timedelta
=======
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
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

<<<<<<< HEAD
# In-memory fallback cache — (data, expires_at) per key
_memory_cache: dict[str, tuple[Any, datetime]] = {}

=======
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e

class BaseIntegrationClient:
    """
    Base class for all external data source integrations.

<<<<<<< HEAD
    IMPORTANT: Cache operations use their own DB session (not self.db).
    This prevents concurrent operation errors when multiple scorers run
    in parallel and all try to write to the cache simultaneously.
    """

    def __init__(self, db_session=None, settings=None):
        from app.config import settings as default_settings
        self.db = db_session          # kept for reference, NOT used for cache
=======
    Subclasses must:
      1. Set self.source_name (e.g. "eia", "fema") for logging/cache keys
      2. Implement their data-fetching methods
      3. Check self.mock first in each method and return fixture data if True

    IMPORTANT: The shared HTTP client has follow_redirects=True globally.
    Never pass follow_redirects as a kwarg to _fetch_with_retry() — it is
    not a supported parameter and will raise a TypeError.
    """

    def __init__(self, redis_client=None, settings=None):
        from app.config import settings as default_settings

        self.redis = redis_client
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        self.settings = settings or default_settings
        self.mock = self.settings.MOCK_INTEGRATIONS
        self.source_name = "base"
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
<<<<<<< HEAD
=======
        """Lazily create and return a shared async HTTP client."""
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"User-Agent": "DataCenter-Site-Selector/1.0 (contact@example.com)"},
<<<<<<< HEAD
                follow_redirects=True,
=======
                follow_redirects=True,  # Handles all redirects globally — do not pass per-call
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
            )
        return self._http_client

    async def close(self):
<<<<<<< HEAD
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ── Cache key ──────────────────────────────────────────────────────────────

    def _cache_key(self, operation: str, *args) -> str:
=======
        """Close the HTTP client. Call on app shutdown."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ── Caching ────────────────────────────────────────────────────────────────

    def _cache_key(self, operation: str, *args) -> str:
        """Build a Redis cache key. Format: integration:{source}:{operation}:{hash}"""
        import hashlib

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        args_str = ":".join(str(a) for a in args)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:12]
        return f"integration:{self.source_name}:{operation}:{args_hash}"

<<<<<<< HEAD
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
=======
    async def _get_cached(self, key: str) -> Optional[Any]:
        """
        Check Redis for a cached value. Returns deserialized value or None.
        Never raises — if Redis is down, returns None and fetches live.
        """
        if self.redis is None:
            return None
        try:
            raw = await self.redis.get(key)
            if raw:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(raw)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.warning(f"Redis get failed for key {key}: {e}")
            return None

    async def _set_cached(self, key: str, data: Any, ttl_hours: int = 24) -> None:
        """
        Store a value in Redis with TTL. Never raises — cache failures are silent.
        """
        if self.redis is None:
            return
        try:
            await self.redis.setex(key, ttl_hours * 3600, json.dumps(data))
            logger.debug(f"Cached {key} for {ttl_hours}h")
        except Exception as e:
            logger.warning(f"Redis set failed for key {key}: {e}")
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e

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
<<<<<<< HEAD
        params=None,
=======
        params: Optional[dict] = None,
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        headers: Optional[dict] = None,
        method: str = "GET",
        json_body: Optional[dict] = None,
    ) -> dict:
        """
        Fetch a URL with automatic retry on transport errors.
<<<<<<< HEAD
        Raises IntegrationError on HTTP errors or after all retries fail.
        Treats 504 as retriable.
=======
        Returns the parsed JSON response body.
        Raises IntegrationError on HTTP errors or after all retries fail.

        NOTE: follow_redirects is handled globally on the HTTP client.
        Do NOT add it as a parameter here.
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        """
        client = await self._get_http_client()
        try:
            if method == "GET":
                response = await client.get(url, params=params, headers=headers)
            elif method == "POST":
<<<<<<< HEAD
                response = await client.post(
                    url, params=params, headers=headers, json=json_body
                )
=======
                response = await client.post(url, params=params, headers=headers, json=json_body)
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 429:
                raise IntegrationError(
                    source=self.source_name,
<<<<<<< HEAD
                    message=f"Rate limited by {url}.",
                    status_code=429,
                )
            if response.status_code == 504:
                raise IntegrationError(
                    source=self.source_name,
                    message=f"Gateway timeout from {url}.",
                    status_code=504,
                )
=======
                    message=f"Rate limited by {url}. Try again later.",
                    status_code=429,
                )
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
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
<<<<<<< HEAD
            raise
=======
            raise  # tenacity will retry
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        except Exception as e:
            raise IntegrationError(
                source=self.source_name,
                message=f"Unexpected error fetching {url}: {e}",
            )

<<<<<<< HEAD
    async def _fetch_geojson(self, url: str, params=None) -> dict:
=======
    async def _fetch_geojson(self, url: str, params: Optional[dict] = None) -> dict:
        """Fetch GeoJSON from a URL. Same retry/error handling as _fetch_with_retry."""
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
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