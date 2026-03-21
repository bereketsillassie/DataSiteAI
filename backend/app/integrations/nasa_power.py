"""
app/integrations/nasa_power.py
───────────────────────────────
NASA POWER (Prediction Of Worldwide Energy Resources) API integration.
Provides: humidity, solar irradiance, temperature normals.

No API key required.
Cache TTL: 7 days

BATCHING:
  get_climate_data_for_region() fetches the bbox center once for the whole region
  and caches it. All 5km grid cells within the region share one NASA POWER call.
  Scorers should prefer this over per-cell calls.

  Per-cell get_climate_data() rounds lat/lng to 1 decimal degree (~11km) for the
  cache key as a secondary batching layer.
"""

import logging
from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"


class NASAPowerClient(BaseIntegrationClient):
    """NASA POWER climate API client."""

    def __init__(self, redis_client=None, settings=None):
        super().__init__(redis_client, settings)
        self.source_name = "nasa_power"

    # ── Region-level batch (one call per analysis region) ─────────────────────

    async def get_climate_data_for_region(self, bbox: BoundingBox) -> dict:
        """
        Fetch NASA POWER climate data once for the entire region using the center point.
        Climate data does not change meaningfully at 5km resolution within a
        county-scale analysis area. Scorers call this once and reuse for all cells.

        Returns same shape as get_climate_data().
        """
        cache_key = self._cache_key(
            "climate_region",
            round(bbox.min_lat, 1),
            round(bbox.min_lng, 1),
            round(bbox.max_lat, 1),
            round(bbox.max_lng, 1),
        )
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        center_lat, center_lng = bbox.center()
        result = await self.get_climate_data(center_lat, center_lng)
        await self._set_cached(cache_key, result, ttl_hours=7 * 24)
        return result

    # ── Per-point fetch ────────────────────────────────────────────────────────

    async def get_climate_data(self, lat: float, lng: float) -> dict:
        """
        Returns annual climatology for the given point.

        Cache key rounds to 1 decimal degree (~11km) so nearby grid cells
        share one API call.

        Returns: {
            "avg_humidity_pct": float,
            "avg_annual_temp_c": float,
            "avg_solar_kwh_m2_day": float,
            "avg_wind_speed_ms": float
        }
        """
        # Round to 1dp — climate doesn't change meaningfully within ~11km
        cache_key = self._cache_key("climate", round(lat, 1), round(lng, 1))
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_climate_data(lat, lng)
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        try:
            params = {
                "parameters": "RH2M,T2M,ALLSKY_SFC_SW_DWN,WS10M",
                "community": "RE",
                "longitude": lng,
                "latitude": lat,
                "format": "JSON",
            }
            data = await self._fetch_with_retry(NASA_POWER_URL, params=params)

            # NASA POWER returns monthly climatology — "ANN" key is the annual average
            props = data.get("properties", {}).get("parameter", {})
            rh2m  = props.get("RH2M", {}).get("ANN", 70.0)
            t2m   = props.get("T2M", {}).get("ANN", 15.0)
            solar = props.get("ALLSKY_SFC_SW_DWN", {}).get("ANN", 4.5)
            wind  = props.get("WS10M", {}).get("ANN", 4.0)

            result = {
                "avg_humidity_pct":      round(float(rh2m), 1),
                "avg_annual_temp_c":     round(float(t2m), 1),
                "avg_solar_kwh_m2_day":  round(float(solar), 2),
                "avg_wind_speed_ms":     round(float(wind), 2),
            }
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        except IntegrationError:
            raise
        except Exception as e:
            logger.warning(f"NASA POWER failed for ({lat},{lng}), using mock: {e}")
            return self._mock_climate_data(lat, lng)

    def _mock_climate_data(self, lat: float, lng: float) -> dict:
        """Latitude-adjusted mock climate data."""
        temp_c   = 28.0 - (lat - 25.0) * 0.9
        humidity = 65.0 + max(0, (lng + 80.0)) * 0.3
        solar    = 5.5  - (lat - 25.0) * 0.05
        return {
            "avg_humidity_pct":     round(min(85, max(30, humidity)), 1),
            "avg_annual_temp_c":    round(temp_c, 1),
            "avg_solar_kwh_m2_day": round(max(3.0, solar), 2),
            "avg_wind_speed_ms":    4.2,
        }