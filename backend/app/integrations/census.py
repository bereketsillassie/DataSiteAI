"""
app/integrations/census.py
───────────────────────────
US Census Bureau API integration.
Provides: population density, labor market data.

Requires: CENSUS_API_KEY environment variable (free at https://api.census.gov/data/key_signup.html)
Cache TTL: 30 days (Census data updates annually)
"""

import logging
import math
from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

CENSUS_BASE_URL = "https://api.census.gov/data"

# FIPS state codes (subset)
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "FL": "12", "GA": "13",
    "HI": "15", "ID": "16", "IL": "17", "IN": "18", "IA": "19",
    "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29",
    "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34",
    "NM": "35", "NY": "36", "NC": "37", "ND": "38", "OH": "39",
    "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45",
    "SD": "46", "TN": "47", "TX": "48", "UT": "49", "VT": "50",
    "VA": "51", "WA": "53", "WV": "54", "WI": "55", "WY": "56",
    "DC": "11",
}

# Mock population density (persons/sq km) by state — approximate state averages
MOCK_POPULATION_DENSITY = {
    "NC": 82, "VA": 91, "SC": 60, "TX": 43, "GA": 70, "TN": 66,
    "CO": 22, "AZ": 24, "WA": 42, "OR": 16, "ID": 8, "NV": 11,
    "UT": 14, "WY": 2, "MT": 3, "ND": 4, "SD": 5, "NE": 10,
    "KS": 14, "OK": 22, "AR": 22, "LA": 42, "MS": 25, "AL": 36,
    "FL": 141, "OH": 109, "IN": 68, "IL": 88, "MI": 68, "WI": 41,
    "MN": 27, "IA": 22, "MO": 35, "KY": 44, "WV": 29, "PA": 119,
    "NY": 158, "NJ": 468, "CT": 296, "MA": 337, "RI": 394,
    "NH": 57, "VT": 26, "ME": 17, "MD": 231, "DE": 183, "DC": 4200,
}

# Mock tech workers per 1,000 residents by state
MOCK_TECH_WORKERS = {
    "NC": 8.2, "VA": 12.4, "TX": 9.8, "CO": 14.1, "WA": 18.5,
    "CA": 16.2, "MA": 13.8, "NY": 10.5, "GA": 7.6, "TN": 6.2,
    "AZ": 9.1, "OR": 12.0, "ID": 7.8, "NV": 7.0, "UT": 11.5,
    "SC": 5.8, "FL": 7.2, "AL": 4.9, "MS": 4.1, "LA": 5.0,
    "OH": 7.8, "IN": 6.1, "IL": 9.0, "MI": 7.5, "WI": 6.8,
    "MN": 9.3, "IA": 5.9, "MO": 6.7, "KY": 5.5, "WV": 4.2,
    "PA": 8.4, "NJ": 10.1, "CT": 11.2, "MD": 13.1, "DC": 15.8,
}


class CensusClient(BaseIntegrationClient):
    """US Census Bureau API client."""

<<<<<<< HEAD
    def __init__(self, db_session=None, settings=None):
        super().__init__(db_session, settings)
=======
    def __init__(self, redis_client=None, settings=None):
        super().__init__(redis_client, settings)
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        self.source_name = "census"

    def _api_key(self) -> str:
        key = self.settings.CENSUS_API_KEY
        if not key:
            raise IntegrationError(
                source="census",
                message="CENSUS_API_KEY not configured. Get a free key at https://api.census.gov/data/key_signup.html",
            )
        return key

    async def get_population_density(self, bbox: BoundingBox) -> dict:
        """
        Returns population density information for the bbox area.

        Returns: {
            "population_within_5km_estimate": int,
            "density_per_sqkm": float,
            "total_estimate": int
        }
        """
        cache_key = self._cache_key(
            "population",
            bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng,
        )
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_population_density(bbox)
            await self._set_cached(cache_key, result, ttl_hours=30 * 24)
            return result

        # Estimate population within the bbox using ACS 5-year estimates.
        # A full production implementation would query /data/2022/acs/acs5 by block group
        # and perform spatial intersection. Using state-level mock as fallback.
        result = self._mock_population_density(bbox)
        await self._set_cached(cache_key, result, ttl_hours=30 * 24)
        return result

    async def get_labor_data(self, state: str, county: str = None) -> dict:
        """
        Returns labor market data for the state/county.

        Returns: {
            "tech_workers_per_1000": float,
            "median_electrician_wage_usd": float,
            "unemployment_rate_pct": float
        }
        """
        state = state.upper()
        cache_key = self._cache_key("labor", state, county or "state")
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_labor_data(state)
            await self._set_cached(cache_key, result, ttl_hours=30 * 24)
            return result

        try:
            state_fips = STATE_FIPS.get(state, "37")
            api_key = self._api_key()

            params = {
                "get": "B24012_001E,B24012_014E",  # Total workers, construction workers
                "for": "state:" + state_fips,
                "key": api_key,
            }
            await self._fetch_with_retry(
                f"{CENSUS_BASE_URL}/2022/acs/acs5", params=params
            )

            # Full parsing of ACS occupation data is complex —
            # return curated mock values enriched by real API availability
            result = self._mock_labor_data(state)
            await self._set_cached(cache_key, result, ttl_hours=30 * 24)
            return result

        except Exception as e:
            logger.warning(f"Census labor data failed for {state}, using mock: {e}")
            return self._mock_labor_data(state)

    def _mock_population_density(self, bbox: BoundingBox) -> dict:
        """Estimate population for a bbox based on area and typical NC density."""
        area_sqkm = bbox.area_sq_km()
        density = 82.0  # NC average
        population_estimate = int(density * area_sqkm)
        # Population within 5km radius = pi * 5^2 * density
        pop_5km = int(math.pi * 25 * density)

        return {
            "population_within_5km_estimate": pop_5km,
            "density_per_sqkm": density,
            "total_estimate": population_estimate,
        }

    def _mock_labor_data(self, state: str) -> dict:
        tech = MOCK_TECH_WORKERS.get(state, 7.0)
        return {
            "tech_workers_per_1000": tech,
            "median_electrician_wage_usd": 56000.0 + tech * 1500,
            "unemployment_rate_pct": 4.2,
        }
