"""
app/integrations/epa.py
────────────────────────
EPA integration for Superfund sites, air quality, and wetlands.

Superfund and NWI: No API key required.
AirNow: Requires AIRNOW_API_KEY (free at https://docs.airnowapi.org/account/request/)
Cache TTL: 7 days
"""

import logging
from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

EPA_SUPERFUND_URL = (
    "https://enviro.epa.gov/enviro/efservice/RCRA_FACILITIES"
    "/LATITUDE83/BETWEEN/{min_lat}/{max_lat}"
    "/LONGITUDE83/BETWEEN/{min_lng}/{max_lng}/JSON"
)
AIRNOW_URL = "https://www.airnowapi.org/aq/observation/latLong/current/"
NWI_WFS_URL = "https://www.fws.gov/wetlands/arcgis/rest/services/Wetlands/MapServer/0/query"


class EPAClient(BaseIntegrationClient):
    """EPA environmental data client."""

    def __init__(self, redis_client=None, settings=None):
        super().__init__(redis_client, settings)
        self.source_name = "epa"

    async def get_superfund_sites(self, bbox: BoundingBox) -> list[dict]:
        """
        Returns EPA Superfund (CERCLIS) hazardous waste sites as GeoJSON Points.
        Each feature has properties: site_name, status, npl_status.
        """
        cache_key = self._cache_key(
            "superfund",
            bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng,
        )
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_superfund_sites(bbox)
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        try:
            url = EPA_SUPERFUND_URL.format(
                min_lat=bbox.min_lat,
                max_lat=bbox.max_lat,
                min_lng=bbox.min_lng,
                max_lng=bbox.max_lng,
            )
            data = await self._fetch_with_retry(url)
            features = []
            for site in data if isinstance(data, list) else []:
                lat = site.get("LATITUDE83")
                lng = site.get("LONGITUDE83")
                if lat and lng:
                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [float(lng), float(lat)],
                        },
                        "properties": {
                            "site_name": site.get("FAC_NAME", "Unknown"),
                            "status": site.get("FAC_ACTIVE_FLAG", "Unknown"),
                            "npl_status": site.get("NPL_STATUS_CODE", "Not Listed"),
                        },
                    })
            await self._set_cached(cache_key, features, ttl_hours=7 * 24)
            return features

        except IntegrationError:
            raise
        except Exception as e:
            logger.warning(f"EPA Superfund fetch failed, returning empty: {e}")
            return []

    async def get_air_quality(self, lat: float, lng: float) -> float:
        """
        Returns the current AQI (Air Quality Index) for the location.
        Range: 0 (good) to 500+ (hazardous).
        Uses EPA AirNow API.
        """
        cache_key = self._cache_key("aqi", round(lat, 2), round(lng, 2))
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
            # NC typically has moderate air quality (AQI 30-60)
            result = round(42.0 + (abs(lat - 35.9) * 3), 1)
            await self._set_cached(cache_key, result, ttl_hours=4)  # AQI changes rapidly
            return result

        key = getattr(self.settings, "AIRNOW_API_KEY", None)
        if not key:
            logger.warning("AIRNOW_API_KEY not set, using default AQI of 45")
            return 45.0

        try:
            params = {
                "format": "application/json",
                "latitude": lat,
                "longitude": lng,
                "distance": 25,
                "API_KEY": key,
            }
            data = await self._fetch_with_retry(AIRNOW_URL, params=params)
            if isinstance(data, list) and data:
                # Return worst AQI across all pollutants observed
                result = float(max(obs.get("AQI", 50) for obs in data))
            else:
                result = 50.0

            await self._set_cached(cache_key, result, ttl_hours=4)
            return result

        except IntegrationError:
            raise
        except Exception as e:
            logger.warning(f"AirNow fetch failed for ({lat},{lng}), using default: {e}")
            return 50.0

    async def get_wetlands(self, bbox: BoundingBox) -> list[dict]:
        """
        Returns National Wetlands Inventory (NWI) polygons as GeoJSON Features.
        Each feature has properties: WETLAND_TYPE, ACRES.
        """
        cache_key = self._cache_key(
            "wetlands",
            bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng,
        )
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_wetlands(bbox)
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        try:
            params = {
                "geometry": f"{bbox.min_lng},{bbox.min_lat},{bbox.max_lng},{bbox.max_lat}",
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "outSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "WETLAND_TYPE,ACRES",
                "returnGeometry": "true",
                "f": "geojson",
                "resultRecordCount": 200,
            }
            data = await self._fetch_with_retry(NWI_WFS_URL, params=params)
            features = data.get("features", [])
            await self._set_cached(cache_key, features, ttl_hours=7 * 24)
            return features

        except IntegrationError:
            raise
        except Exception as e:
            logger.warning(f"NWI wetlands fetch failed, returning empty: {e}")
            return []

    # ── Mock data generators ───────────────────────────────────────────────────

    def _mock_superfund_sites(self, bbox: BoundingBox) -> list[dict]:
        """One Superfund site near the edge of the bbox (typical for NC — not many)."""
        return [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [bbox.min_lng + 0.05, bbox.min_lat + 0.08],
                },
                "properties": {
                    "site_name": "Mock Former Industrial Site",
                    "status": "Inactive",
                    "npl_status": "Not Listed",
                },
            }
        ]

    def _mock_wetlands(self, bbox: BoundingBox) -> list[dict]:
        """Small wetland area along the mock river corridor."""
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [clng - 0.025, clat - 0.04],
                        [clng + 0.025, clat - 0.04],
                        [clng + 0.02, clat + 0.04],
                        [clng - 0.02, clat + 0.04],
                        [clng - 0.025, clat - 0.04],
                    ]],
                },
                "properties": {"WETLAND_TYPE": "Riverine", "ACRES": 45.2},
            }
        ]
