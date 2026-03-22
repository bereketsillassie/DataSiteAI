"""
app/integrations/epa.py
────────────────────────
EPA integration for Superfund sites, air quality, and wetlands.

<<<<<<< HEAD
Superfund: EPA ECHO REST API (/echo/dfr_rest_services.get_facilities)
  - Supports bbox query params without URL path encoding issues
  - No dots in URL path, no negative number parser bugs
NWI Wetlands: USFWS ArcGIS REST — no key required
AirNow: Requires AIRNOW_API_KEY (free at https://docs.airnowapi.org/account/request/)

Cache TTL: 7 days

BATCHING:
  get_air_quality_for_region(bbox) — 1 AirNow call for whole region
  get_superfund_sites / get_wetlands — already region-level, 1 call each
=======
Superfund and NWI: No API key required.
AirNow: Requires AIRNOW_API_KEY (free at https://docs.airnowapi.org/account/request/)
Cache TTL: 7 days
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
"""

import logging
from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

<<<<<<< HEAD
# EPA ECHO REST API — supports bbox as query params (no URL path encoding issues)
EPA_ECHO_FACILITIES_URL = "https://echodata.epa.gov/echo/dfr_rest_services.get_facilities"

# AirNow current observation API
AIRNOW_URL = "https://www.airnowapi.org/aq/observation/latLong/current/"

# USFWS National Wetlands Inventory ArcGIS REST service
NWI_URL = "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0/query"
=======
EPA_SUPERFUND_URL = (
    "https://enviro.epa.gov/enviro/efservice/RCRA_FACILITIES"
    "/LATITUDE83/BETWEEN/{min_lat}/{max_lat}"
    "/LONGITUDE83/BETWEEN/{min_lng}/{max_lng}/JSON"
)
AIRNOW_URL = "https://www.airnowapi.org/aq/observation/latLong/current/"
NWI_WFS_URL = "https://www.fws.gov/wetlands/arcgis/rest/services/Wetlands/MapServer/0/query"
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e


class EPAClient(BaseIntegrationClient):
    """EPA environmental data client."""

<<<<<<< HEAD
    def __init__(self, db_session=None, settings=None):
        super().__init__(db_session, settings)
=======
    def __init__(self, redis_client=None, settings=None):
        super().__init__(redis_client, settings)
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        self.source_name = "epa"

    async def get_superfund_sites(self, bbox: BoundingBox) -> list[dict]:
        """
<<<<<<< HEAD
        Returns EPA hazardous waste / Superfund sites as GeoJSON Points.
        Uses EPA ECHO facilities API with bbox query params — avoids all
        URL path encoding issues with negative numbers and dots.

        Non-fatal: returns empty list on any failure since Superfund proximity
        is one sub-metric of geological scoring and has a safe fallback.
        """
        cache_key = self._cache_key(
            "superfund",
            round(bbox.min_lat, 2), round(bbox.min_lng, 2),
            round(bbox.max_lat, 2), round(bbox.max_lng, 2),
        )
        cached = await self._get_cached(cache_key)
        if cached is not None:
=======
        Returns EPA Superfund (CERCLIS) hazardous waste sites as GeoJSON Points.
        Each feature has properties: site_name, status, npl_status.
        """
        cache_key = self._cache_key(
            "superfund",
            bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng,
        )
        cached = await self._get_cached(cache_key)
        if cached:
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
            return cached

        if self.mock:
            result = self._mock_superfund_sites(bbox)
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        try:
<<<<<<< HEAD
            # ECHO API uses query params — no URL path issues with negatives
            params = {
                "p_c1lat":  bbox.min_lat,
                "p_c1lon":  bbox.min_lng,
                "p_c2lat":  bbox.max_lat,
                "p_c2lon":  bbox.max_lng,
                "p_act":    "Y",          # Active facilities only
                "p_med":    "R",          # RCRA program (hazardous waste)
                "output":   "JSON",
                "qcolumns": "4,5,23,24",  # name, address, lat, lng
            }
            data = await self._fetch_with_retry(EPA_ECHO_FACILITIES_URL, params=params)
            facilities = data.get("Results", {}).get("Facilities", [])
            features = []
            for fac in facilities:
                try:
                    lat = float(fac.get("FacLat") or 0)
                    lng = float(fac.get("FacLong") or 0)
                    if lat == 0 or lng == 0:
                        continue
                    features.append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [lng, lat]},
                        "properties": {
                            "site_name":    fac.get("FacName", "Unknown"),
                            "program_type": "RCRA",
                        },
                    })
                except (ValueError, TypeError):
                    continue

            await self._set_cached(cache_key, features, ttl_hours=7 * 24)
            return features

        except Exception as e:
            logger.warning(f"EPA ECHO Superfund fetch failed, returning empty: {e}")
            # Return empty — geological scorer handles this gracefully
            await self._set_cached(cache_key, [], ttl_hours=1)
            return []

    # ── Region-level AQI batch ─────────────────────────────────────────────────

    async def get_air_quality_for_region(self, bbox: BoundingBox) -> float:
        """
        Fetch AQI once for the bbox center — shared across all cells.
        AQI doesn't change meaningfully at 5km grid resolution.
        """
        cache_key = self._cache_key(
            "aqi_region",
            round(bbox.min_lat, 1), round(bbox.min_lng, 1),
            round(bbox.max_lat, 1), round(bbox.max_lng, 1),
        )
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        center_lat, center_lng = bbox.center()
        result = await self.get_air_quality(center_lat, center_lng)
        await self._set_cached(cache_key, result, ttl_hours=4)
        return result

    async def get_air_quality(self, lat: float, lng: float) -> float:
        """Returns AQI via EPA AirNow. Falls back to 45 if key missing."""
        cache_key = self._cache_key("aqi", round(lat, 1), round(lng, 1))
=======
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
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
<<<<<<< HEAD
            result = round(42.0 + (abs(lat - 35.9) * 3), 1)
            await self._set_cached(cache_key, result, ttl_hours=4)
=======
            # NC typically has moderate air quality (AQI 30-60)
            result = round(42.0 + (abs(lat - 35.9) * 3), 1)
            await self._set_cached(cache_key, result, ttl_hours=4)  # AQI changes rapidly
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
            return result

        key = getattr(self.settings, "AIRNOW_API_KEY", None)
        if not key:
            logger.warning("AIRNOW_API_KEY not set, using default AQI of 45")
            return 45.0

        try:
            params = {
<<<<<<< HEAD
                "format":    "application/json",
                "latitude":  lat,
                "longitude": lng,
                "distance":  25,
                "API_KEY":   key,
            }
            data = await self._fetch_with_retry(AIRNOW_URL, params=params)
            result = (
                float(max(obs.get("AQI", 50) for obs in data))
                if isinstance(data, list) and data
                else 50.0
            )
            await self._set_cached(cache_key, result, ttl_hours=4)
            return result
        except Exception as e:
            logger.warning(f"AirNow fetch failed for ({lat},{lng}): {e}")
            return 50.0

    async def get_wetlands(self, bbox: BoundingBox) -> list[dict]:
        """Returns NWI wetland polygons as GeoJSON Features."""
=======
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
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        cache_key = self._cache_key(
            "wetlands",
            bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng,
        )
        cached = await self._get_cached(cache_key)
<<<<<<< HEAD
        if cached is not None:
=======
        if cached:
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
            return cached

        if self.mock:
            result = self._mock_wetlands(bbox)
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        try:
            params = {
<<<<<<< HEAD
                "geometry":          f"{bbox.min_lng},{bbox.min_lat},{bbox.max_lng},{bbox.max_lat}",
                "geometryType":      "esriGeometryEnvelope",
                "inSR":              "4326",
                "outSR":             "4326",
                "spatialRel":        "esriSpatialRelIntersects",
                "outFields":         "WETLAND_TYPE,ACRES",
                "returnGeometry":    "true",
                "f":                 "geojson",
                "resultRecordCount": 200,
            }
            data = await self._fetch_with_retry(NWI_URL, params=params)
            features = data.get("features", [])
            await self._set_cached(cache_key, features, ttl_hours=7 * 24)
            return features
=======
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
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        except Exception as e:
            logger.warning(f"NWI wetlands fetch failed, returning empty: {e}")
            return []

<<<<<<< HEAD
    # ── Mock data ──────────────────────────────────────────────────────────────

    def _mock_superfund_sites(self, bbox: BoundingBox) -> list[dict]:
        return [{
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [bbox.min_lng + 0.05, bbox.min_lat + 0.08],
            },
            "properties": {
                "site_name":    "Mock Former Industrial Site",
                "program_type": "RCRA",
            },
        }]

    def _mock_wetlands(self, bbox: BoundingBox) -> list[dict]:
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[
                [clng - 0.025, clat - 0.04], [clng + 0.025, clat - 0.04],
                [clng + 0.02,  clat + 0.04], [clng - 0.02,  clat + 0.04],
                [clng - 0.025, clat - 0.04],
            ]]},
            "properties": {"WETLAND_TYPE": "Riverine", "ACRES": 45.2},
        }]
=======
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
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
