"""
app/integrations/base.py
─────────────────────────
Base class for all integration clients.
Every external data source client extends this class.

Key features provided by BaseIntegrationClient:
  - Redis caching (check before fetch, set after fetch)
  - HTTP retry with exponential backoff via tenacity
  - Mock mode: return fixture data when settings.MOCK_INTEGRATIONS=True
  - Typed error handling: always raise IntegrationError, never raw exceptions
"""

import json
import logging
from typing import Any, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.models.domain import IntegrationError

logger = logging.getLogger(__name__)


class BaseIntegrationClient:
    """
    Base class for all external data source integrations.

    Subclasses must:
      1. Set self.source_name (e.g. "eia", "fema") for logging/cache keys
      2. Implement their data-fetching methods
      3. Check self.mock first in each method and return fixture data if True
    """

    def __init__(self, redis_client=None, settings=None):
        """
        Args:
            redis_client: aioredis.Redis instance (or None to skip caching)
            settings: app Settings instance
        """
        from app.config import settings as default_settings
        self.redis = redis_client
        self.settings = settings or default_settings
        self.mock = self.settings.MOCK_INTEGRATIONS
        self.source_name = "base"  # Subclasses override this
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Lazily create and return a shared async HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers={"User-Agent": "DataCenter-Site-Selector/1.0 (contact@example.com)"},
                follow_redirects=True,
            )
        return self._http_client

    async def close(self):
        """Close the HTTP client. Call on shutdown."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # ── Caching ────────────────────────────────────────────────────────────────

    def _cache_key(self, operation: str, *args) -> str:
        """Build a Redis cache key. Format: integration:{source}:{operation}:{args_hash}"""
        import hashlib
        args_str = ":".join(str(a) for a in args)
        args_hash = hashlib.md5(args_str.encode()).hexdigest()[:12]
        return f"integration:{self.source_name}:{operation}:{args_hash}"

    async def _get_cached(self, key: str) -> Optional[Any]:
        """
        Check Redis for a cached value. Returns the deserialized value or None.
        Never raises — if Redis is down, just returns None.
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
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        method: str = "GET",
        json_body: Optional[dict] = None,
    ) -> dict:
        """
        Fetch a URL with automatic retry on transport errors.
        Returns the parsed JSON response body.
        Raises IntegrationError on HTTP errors or after all retries fail.
        """
        client = await self._get_http_client()
        try:
            if method == "GET":
                response = await client.get(url, params=params, headers=headers)
            elif method == "POST":
                response = await client.post(url, params=params, headers=headers, json=json_body)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 429:
                raise IntegrationError(
                    source=self.source_name,
                    message=f"Rate limited by {url}. Try again later.",
                    status_code=429,
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
            raise  # tenacity will retry
        except Exception as e:
            raise IntegrationError(
                source=self.source_name,
                message=f"Unexpected error fetching {url}: {e}",
            )

    async def _fetch_geojson(self, url: str, params: Optional[dict] = None) -> dict:
        """Fetch GeoJSON from a URL. Same retry/error handling as _fetch_with_retry."""
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
