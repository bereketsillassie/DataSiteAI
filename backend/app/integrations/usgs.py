"""
app/integrations/usgs.py
─────────────────────────
USGS APIs for seismic hazard and elevation.

No API key required.
Cache TTL: 30 days (seismic data changes only when models are updated).

BATCHING:
  get_seismic_hazard() rounds lat/lng to 2 decimal places (~1km) for cache key.
  get_seismic_hazard_for_region() fetches the bbox center once for the whole region.
  Scorers should prefer the region method over per-cell calls.
"""

import logging
from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

USGS_HAZARD_URL = "https://earthquake.usgs.gov/ws/designmaps/asce7-22.json"
USGS_ELEVATION_URL = "https://epqs.nationalmap.gov/v1/json"


class USGSClient(BaseIntegrationClient):
    """USGS seismic hazard and elevation client."""

<<<<<<< HEAD
    def __init__(self, db_session=None, settings=None):
        super().__init__(db_session, settings)
=======
    def __init__(self, redis_client=None, settings=None):
        super().__init__(redis_client, settings)
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        self.source_name = "usgs"

    # ── Region-level batch (one call per analysis region) ─────────────────────

    async def get_seismic_hazard_for_region(self, bbox: BoundingBox) -> float:
        """
        Fetch seismic hazard once for the entire region using the center point.
        Seismic hazard does not vary significantly at 5km resolution within a
        county-scale area. Scorers call this once and reuse for all cells.
        """
        cache_key = self._cache_key(
            "seismic_region",
            round(bbox.min_lat, 1),
            round(bbox.min_lng, 1),
            round(bbox.max_lat, 1),
            round(bbox.max_lng, 1),
        )
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        center_lat, center_lng = bbox.center()
        result = await self.get_seismic_hazard(center_lat, center_lng)
        await self._set_cached(cache_key, result, ttl_hours=30 * 24)
        return result

    # ── Per-point fetch ────────────────────────────────────────────────────────

    async def get_seismic_hazard(self, lat: float, lng: float) -> float:
        """
        Returns USGS seismic hazard as Peak Ground Acceleration (PGA) in g units.
        Higher PGA = greater earthquake risk.

        Range in continental US: ~0.002 (stable Midwest) to 2.0+ (CA fault zones)
        NC typical: 0.05-0.15g

        Cache key rounds to 2dp (~1km) so nearby cells share one API call.
        """
        cache_key = self._cache_key("seismic", round(lat, 2), round(lng, 2))
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
            result = 0.08 + (abs(lat - 35.9) + abs(lng + 78.9)) * 0.01
            result = round(min(result, 0.15), 4)
            await self._set_cached(cache_key, result, ttl_hours=30 * 24)
            return result

        try:
            # asce7-22 uses "latitude"/"longitude" not "lat"/"lng"
            # follow_redirects is on the base HTTP client globally — do NOT pass here
            params = {
                "latitude": lat,
                "longitude": lng,
                "riskCategory": "II",
                "siteClass": "C",
                "title": "DataCenter Site Selector Query",
            }
            data = await self._fetch_with_retry(USGS_HAZARD_URL, params=params)

            # Response: { "output": { "data": [ { "pgauh": float, ... } ] } }
            output = data.get("output", {})
            data_list = output.get("data", [{}])
            first = data_list[0] if data_list else {}
            pga = (
                first.get("pgauh")
                or first.get("pga")
                or data.get("parameters", {}).get("pga", 0.1)
            )
            result = round(float(pga), 4)
            await self._set_cached(cache_key, result, ttl_hours=30 * 24)
            return result

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(
                source="usgs",
                message=f"seismic hazard fetch failed for ({lat},{lng}): {e}",
            )

    async def get_elevation_slope(self, bbox: BoundingBox) -> dict:
        """
        Returns elevation and slope data for the bbox center and corners.
        Uses the USGS 3DEP Elevation Point Query Service.

        Returns: {
            "center": {"lat": float, "lng": float, "elevation_m": float},
            "points": [{"lat": float, "lng": float, "elevation_m": float}]
        }
        """
        cache_key = self._cache_key(
            "elevation_slope",
            round(bbox.min_lat, 2),
            round(bbox.min_lng, 2),
            round(bbox.max_lat, 2),
            round(bbox.max_lng, 2),
        )
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            center_lat, center_lng = bbox.center()
            result = {
                "center": {"lat": center_lat, "lng": center_lng, "elevation_m": 112.5},
                "points": [
                    {"lat": bbox.min_lat, "lng": bbox.min_lng, "elevation_m": 95.0},
                    {"lat": bbox.min_lat, "lng": bbox.max_lng, "elevation_m": 118.0},
                    {"lat": bbox.max_lat, "lng": bbox.min_lng, "elevation_m": 124.0},
                    {"lat": bbox.max_lat, "lng": bbox.max_lng, "elevation_m": 108.0},
                    {"lat": center_lat,   "lng": center_lng,   "elevation_m": 112.5},
                ],
            }
            await self._set_cached(cache_key, result, ttl_hours=30 * 24)
            return result

        center_lat, center_lng = bbox.center()
        sample_points = [
            (bbox.min_lat, bbox.min_lng),
            (bbox.min_lat, bbox.max_lng),
            (bbox.max_lat, bbox.min_lng),
            (bbox.max_lat, bbox.max_lng),
            (center_lat, center_lng),
        ]

        points_data = []
        for pt_lat, pt_lng in sample_points:
            try:
                # follow_redirects handled globally on base client — do NOT pass here
                params = {"x": pt_lng, "y": pt_lat, "units": "Meters", "output": "json"}
                data = await self._fetch_with_retry(USGS_ELEVATION_URL, params=params)
                elev = data.get("value", 100.0)
                points_data.append({"lat": pt_lat, "lng": pt_lng, "elevation_m": float(elev)})
            except Exception as e:
                logger.warning(f"Elevation query failed for ({pt_lat},{pt_lng}): {e}")
                points_data.append({"lat": pt_lat, "lng": pt_lng, "elevation_m": 100.0})

        result = {"center": points_data[-1], "points": points_data}
        await self._set_cached(cache_key, result, ttl_hours=30 * 24)
        return result