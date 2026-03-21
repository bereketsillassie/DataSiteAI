"""
app/integrations/usgs.py
─────────────────────────
USGS APIs for seismic hazard and elevation.

No API key required.
Cache TTL: 30 days (seismic data changes only when models are updated).
"""

import logging
from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

USGS_HAZARD_URL = "https://earthquake.usgs.gov/hazards/designmaps/us/sum.json"
USGS_ELEVATION_URL = "https://epqs.nationalmap.gov/v1/json"


class USGSClient(BaseIntegrationClient):
    """USGS seismic hazard and elevation client."""

    def __init__(self, redis_client=None, settings=None):
        super().__init__(redis_client, settings)
        self.source_name = "usgs"

    async def get_seismic_hazard(self, lat: float, lng: float) -> float:
        """
        Returns USGS seismic hazard as Peak Ground Acceleration (PGA) in g units.
        Higher PGA = greater earthquake risk.

        Range in continental US: ~0.002 (stable Midwest) to ~2.0+ (California fault zones)
        NC typical: 0.05 – 0.15g

        Returns: float (PGA in units of g)
        """
        cache_key = self._cache_key("seismic", round(lat, 3), round(lng, 3))
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
            # NC has moderate-low seismic risk — realistic mock value
            result = 0.08 + (abs(lat - 35.9) + abs(lng + 78.9)) * 0.01
            result = round(min(result, 0.15), 4)
            await self._set_cached(cache_key, result, ttl_hours=30 * 24)
            return result

        try:
            params = {
                "lat": lat,
                "lng": lng,
                "riskCategory": "II",
                "siteClass": "C",
                "title": "DataCenter Site Selector Query",
            }
            data = await self._fetch_with_retry(USGS_HAZARD_URL, params=params)
            # The USGS response nests data under "parameters"
            pga = data.get("parameters", {}).get("pga", 0.1)
            result = float(pga)
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
        cache_key = self._cache_key("elevation_slope", bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng)
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
                    {"lat": center_lat, "lng": center_lng, "elevation_m": 112.5},
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
        for lat, lng in sample_points:
            try:
                params = {"x": lng, "y": lat, "units": "Meters", "output": "json"}
                data = await self._fetch_with_retry(USGS_ELEVATION_URL, params=params)
                elev = data.get("value", 100.0)
                points_data.append({"lat": lat, "lng": lng, "elevation_m": float(elev)})
            except Exception as e:
                logger.warning(f"Elevation query failed for ({lat},{lng}): {e}")
                points_data.append({"lat": lat, "lng": lng, "elevation_m": 100.0})

        result = {
            "center": points_data[-1],
            "points": points_data,
        }
        await self._set_cached(cache_key, result, ttl_hours=30 * 24)
        return result
