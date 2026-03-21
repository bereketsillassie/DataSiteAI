"""
app/integrations/noaa.py
─────────────────────────
NOAA Climate Data Online integration.
Provides: climate normals, cooling degree days, storm events.

Requires: NOAA_API_KEY environment variable (free at https://www.ncdc.noaa.gov/cdo-web/token)
Cache TTL: 7 days
"""

import logging
from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

NOAA_CDO_URL = "https://www.ncei.noaa.gov/cdo-web/api/v2"

# Mock climate normals by state (30-year climate normals, 1991-2020)
MOCK_CLIMATE_BY_STATE = {
    "NC": {"avg_annual_temp_c": 15.2, "avg_summer_temp_c": 26.1, "avg_humidity_pct": 71, "annual_cdd": 1850},
    "VA": {"avg_annual_temp_c": 13.8, "avg_summer_temp_c": 25.0, "avg_humidity_pct": 70, "annual_cdd": 1500},
    "SC": {"avg_annual_temp_c": 17.1, "avg_summer_temp_c": 28.2, "avg_humidity_pct": 74, "annual_cdd": 2200},
    "TX": {"avg_annual_temp_c": 19.4, "avg_summer_temp_c": 32.0, "avg_humidity_pct": 65, "annual_cdd": 3100},
    "GA": {"avg_annual_temp_c": 17.0, "avg_summer_temp_c": 27.8, "avg_humidity_pct": 73, "annual_cdd": 2100},
    "TN": {"avg_annual_temp_c": 14.5, "avg_summer_temp_c": 26.5, "avg_humidity_pct": 72, "annual_cdd": 1700},
    "CO": {"avg_annual_temp_c": 8.6, "avg_summer_temp_c": 22.0, "avg_humidity_pct": 45, "annual_cdd": 700},
    "AZ": {"avg_annual_temp_c": 17.8, "avg_summer_temp_c": 35.0, "avg_humidity_pct": 38, "annual_cdd": 3200},
    "WA": {"avg_annual_temp_c": 10.3, "avg_summer_temp_c": 20.0, "avg_humidity_pct": 73, "annual_cdd": 300},
    "OR": {"avg_annual_temp_c": 10.8, "avg_summer_temp_c": 21.5, "avg_humidity_pct": 70, "annual_cdd": 400},
    "ID": {"avg_annual_temp_c": 8.9, "avg_summer_temp_c": 23.5, "avg_humidity_pct": 52, "annual_cdd": 750},
    "NV": {"avg_annual_temp_c": 10.5, "avg_summer_temp_c": 28.0, "avg_humidity_pct": 35, "annual_cdd": 1500},
    "UT": {"avg_annual_temp_c": 9.4, "avg_summer_temp_c": 27.0, "avg_humidity_pct": 42, "annual_cdd": 1200},
}

# Mock storm events per 100 sq km over 30 years
MOCK_STORM_EVENTS = {
    "NC": {"tornado_per_100sqkm": 0.8, "hurricane_proximity_score": 0.3, "hail_per_100sqkm": 1.2},
    "TX": {"tornado_per_100sqkm": 3.5, "hurricane_proximity_score": 0.5, "hail_per_100sqkm": 4.8},
    "FL": {"tornado_per_100sqkm": 1.2, "hurricane_proximity_score": 0.9, "hail_per_100sqkm": 1.5},
    "GA": {"tornado_per_100sqkm": 1.1, "hurricane_proximity_score": 0.3, "hail_per_100sqkm": 1.4},
    "TN": {"tornado_per_100sqkm": 0.9, "hurricane_proximity_score": 0.1, "hail_per_100sqkm": 1.8},
    "SC": {"tornado_per_100sqkm": 0.7, "hurricane_proximity_score": 0.5, "hail_per_100sqkm": 1.1},
    "VA": {"tornado_per_100sqkm": 0.5, "hurricane_proximity_score": 0.3, "hail_per_100sqkm": 0.9},
    "CO": {"tornado_per_100sqkm": 0.6, "hurricane_proximity_score": 0.0, "hail_per_100sqkm": 3.2},
    "AZ": {"tornado_per_100sqkm": 0.2, "hurricane_proximity_score": 0.0, "hail_per_100sqkm": 0.8},
    "WA": {"tornado_per_100sqkm": 0.1, "hurricane_proximity_score": 0.0, "hail_per_100sqkm": 0.3},
    "OR": {"tornado_per_100sqkm": 0.1, "hurricane_proximity_score": 0.0, "hail_per_100sqkm": 0.4},
    "ID": {"tornado_per_100sqkm": 0.1, "hurricane_proximity_score": 0.0, "hail_per_100sqkm": 0.6},
}


class NOAAClient(BaseIntegrationClient):
    """NOAA Climate Data Online API client."""

    def __init__(self, redis_client=None, settings=None):
        super().__init__(redis_client, settings)
        self.source_name = "noaa"

    def _api_headers(self) -> dict:
        key = self.settings.NOAA_API_KEY
        if not key:
            raise IntegrationError(
                source="noaa",
                message="NOAA_API_KEY not configured. Get a free token at https://www.ncdc.noaa.gov/cdo-web/token",
            )
        return {"token": key}

    async def get_climate_normals(self, lat: float, lng: float) -> dict:
        """
        Returns 30-year climate normals for the given location.

        Returns: {
            "avg_annual_temp_c": float,
            "avg_summer_temp_c": float,
            "avg_humidity_pct": float,
            "annual_cdd": float
        }
        """
        cache_key = self._cache_key("climate_normals", round(lat, 2), round(lng, 2))
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_climate_normals(lat, lng)
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        # NOAA CDO API: find nearest station and get normals
        try:
            headers = self._api_headers()
            # Find nearest station
            station_params = {
                "datasetid": "NORMAL_ANN",
                "extent": f"{lat - 1},{lng - 1},{lat + 1},{lng + 1}",
                "limit": 1,
            }
            stations = await self._fetch_with_retry(
                f"{NOAA_CDO_URL}/stations", params=station_params, headers=headers
            )
            station_list = stations.get("results", [])
            if not station_list:
                return self._mock_climate_normals(lat, lng)

            station_id = station_list[0]["id"]
            data_params = {
                "datasetid": "NORMAL_ANN",
                "stationid": station_id,
                "datatypeid": "ANN-TAVG-NORMAL,ANN-HDD-NORMAL,ANN-CDD-NORMAL",
                "limit": 10,
            }
            normals = await self._fetch_with_retry(
                f"{NOAA_CDO_URL}/data", params=data_params, headers=headers
            )
            results = normals.get("results", [])

            # Parse response
            by_type = {r["datatype"]: r["value"] for r in results}
            avg_temp_f = by_type.get("ANN-TAVG-NORMAL", 60.0)  # NOAA returns in tenths of °F
            avg_temp_c = (float(avg_temp_f) / 10.0 - 32) * 5 / 9
            cdd = float(by_type.get("ANN-CDD-NORMAL", 1500)) / 10.0

            result = {
                "avg_annual_temp_c": round(avg_temp_c, 1),
                "avg_summer_temp_c": round(avg_temp_c + 11.0, 1),  # Approximate summer offset
                "avg_humidity_pct": 70.0,  # Fallback — get from NASA POWER
                "annual_cdd": round(cdd, 0),
            }
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        except IntegrationError:
            raise
        except Exception as e:
            logger.warning(f"NOAA climate normals failed, using mock: {e}")
            return self._mock_climate_normals(lat, lng)

    async def get_cooling_degree_days(self, state: str) -> float:
        """
        Returns annual cooling degree days (CDD) for the state.
        Higher CDD = more air conditioning needed = higher energy costs for cooling.
        """
        state = state.upper()
        cache_key = self._cache_key("cdd", state)
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
            result = float(MOCK_CLIMATE_BY_STATE.get(state, {}).get("annual_cdd", 1500))
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        try:
            headers = self._api_headers()
            params = {
                "datasetid": "NORMAL_ANN",
                "datatypeid": "ANN-CDD-NORMAL",
                "stationid": f"GHCND:US{state}0001",  # Approximate — state summary station
                "limit": 1,
            }
            data = await self._fetch_with_retry(
                f"{NOAA_CDO_URL}/data", params=params, headers=headers
            )
            results = data.get("results", [])
            if results:
                result = float(results[0]["value"]) / 10.0
            else:
                result = float(MOCK_CLIMATE_BY_STATE.get(state, {}).get("annual_cdd", 1500))
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        except Exception as e:
            logger.warning(f"NOAA CDD fetch failed for {state}, using mock: {e}")
            return float(MOCK_CLIMATE_BY_STATE.get(state, {}).get("annual_cdd", 1500))

    async def get_storm_events(self, state: str) -> dict:
        """
        Returns tornado, hurricane, and hail risk metrics for the state.

        Returns: {
            "tornado_per_100sqkm": float,
            "hurricane_proximity_score": float,   # 0.0 (inland) to 1.0 (coastal)
            "hail_per_100sqkm": float
        }
        """
        state = state.upper()
        cache_key = self._cache_key("storm_events", state)
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        # NOAA storm events API requires complex processing — use curated values
        result = MOCK_STORM_EVENTS.get(state, {
            "tornado_per_100sqkm": 0.5,
            "hurricane_proximity_score": 0.1,
            "hail_per_100sqkm": 1.0,
        })
        await self._set_cached(cache_key, result, ttl_hours=7 * 24)
        return result

    def _mock_climate_normals(self, lat: float, lng: float) -> dict:
        """Generate realistic climate normals based on latitude (warmer at lower latitudes)."""
        # Approximate temperature adjustment based on latitude
        temp_c = 28.0 - (lat - 25.0) * 0.8
        humidity = 70.0 + (lng + 90.0) * 0.2  # Higher humidity near Gulf Coast
        cdd = max(300, 3500 - (lat - 25.0) * 120)

        return {
            "avg_annual_temp_c": round(temp_c, 1),
            "avg_summer_temp_c": round(temp_c + 11.0, 1),
            "avg_humidity_pct": round(min(85, humidity), 1),
            "annual_cdd": round(cdd, 0),
        }
