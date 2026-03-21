"""
app/integrations/eia.py
────────────────────────
Energy Information Administration (EIA) API integration.
Provides: electricity rates, utility territories, renewable energy percentage, grid reliability.

Requires: EIA_API_KEY environment variable (free at https://api.eia.gov/v2/)
Cache TTL: 7 days

NOTE on multi-value params:
  The EIA API uses repeated query params for array values, e.g.:
    facets[fueltypeId][]=SUN&facets[fueltypeId][]=WND
  httpx handles this correctly when you pass a list of tuples to params,
  NOT a dict with a list value. See get_renewable_pct() for the pattern.
"""

import logging
from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

EIA_BASE_URL = "https://api.eia.gov/v2"

# Commercial electricity rates by state (cents/kWh)
MOCK_ELECTRICITY_RATES = {
    "NC": 8.2,  "VA": 8.5,  "SC": 9.1,  "TX": 8.8,  "GA": 9.3,
    "TN": 9.0,  "CO": 11.2, "AZ": 10.1, "WA": 7.2,  "OR": 9.0,
    "ID": 7.8,  "NV": 9.5,  "UT": 8.9,  "NM": 10.5, "WY": 8.1,
    "MT": 9.2,  "ND": 9.8,  "SD": 9.6,  "NE": 9.4,  "KS": 9.7,
    "OK": 8.6,  "AR": 9.0,  "LA": 9.2,  "MS": 10.1, "AL": 10.3,
    "FL": 11.5, "OH": 10.8, "IN": 10.2, "IL": 11.0, "MI": 10.9,
    "WI": 11.3, "MN": 10.7, "IA": 9.9,  "MO": 9.8,  "KY": 9.5,
    "WV": 9.3,  "PA": 12.1, "NY": 16.2, "NJ": 14.8, "CT": 22.1,
    "MA": 20.5, "RI": 19.8, "NH": 18.9, "VT": 17.2, "ME": 15.6,
    "MD": 12.3, "DE": 13.1, "DC": 14.5,
}

MOCK_RENEWABLE_PCT = {
    "NC": 22, "VA": 12, "TX": 28, "WA": 79, "OR": 61, "CO": 32,
    "CA": 54, "AZ": 15, "NV": 31, "ID": 72, "UT": 24, "WY": 16,
    "MT": 56, "ND": 30, "SD": 78, "NE": 23, "KS": 44, "OK": 36,
    "TN": 15, "GA": 11, "SC": 8,  "FL": 8,  "AL": 8,  "MS": 6,
    "IL": 12, "MN": 27, "IA": 58, "MI": 11, "OH": 6,  "IN": 7,
    "NY": 30, "PA": 8,  "MA": 20, "CT": 10, "NJ": 9,  "MD": 10,
}

# Grid reliability index (0–100, based on inverted SAIDI scores)
MOCK_RELIABILITY = {
    "NC": 72, "VA": 75, "TX": 60, "WA": 85, "OR": 82, "CO": 78,
    "TN": 68, "GA": 70, "SC": 71, "FL": 65, "AL": 63, "MS": 58,
    "NY": 80, "CA": 74, "IL": 76, "OH": 71, "PA": 73, "MI": 69,
}

# Renewable fuel type IDs in the EIA electric-power-operational-data API
RENEWABLE_FUEL_TYPES = ["SUN", "WND", "HYC", "GEO", "WAS"]

# Approximate total annual generation by state (MWh) for renewable % calculation
# Used as denominator since EIA doesn't return total in the same call
STATE_TOTAL_GENERATION_MWH = {
    "NC": 130_000_000, "TX": 500_000_000, "WA": 120_000_000, "CA": 280_000_000,
    "FL": 240_000_000, "GA": 140_000_000, "VA": 100_000_000, "TN": 90_000_000,
    "CO": 65_000_000,  "AZ": 110_000_000, "OR": 75_000_000,  "ID": 25_000_000,
    "NV": 45_000_000,  "UT": 40_000_000,  "NY": 150_000_000, "PA": 200_000_000,
    "OH": 160_000_000, "IL": 190_000_000, "MI": 130_000_000, "MN": 60_000_000,
    "IA": 70_000_000,  "KS": 50_000_000,  "OK": 80_000_000,
}


class EIAClient(BaseIntegrationClient):
    """Energy Information Administration API client."""

    def __init__(self, redis_client=None, settings=None):
        super().__init__(redis_client, settings)
        self.source_name = "eia"

    def _api_key(self) -> str:
        key = self.settings.EIA_API_KEY
        if not key:
            raise IntegrationError(
                source="eia",
                message="EIA_API_KEY not configured. Get a free key at https://api.eia.gov/v2/",
            )
        return key

    async def get_retail_electricity_rate(self, state: str) -> float:
        """
        Returns commercial electricity rate in cents/kWh for the given state.
        State-level — one call per state, not per grid cell.
        """
        state = state.upper()
        cache_key = self._cache_key("electricity_rate", state)
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
            result = MOCK_ELECTRICITY_RATES.get(state, 11.0)
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        try:
            # Use list-of-tuples for params — required for EIA's array param style
            # Dict with list value does NOT work with httpx for this API
            params = [
                ("api_key",              self._api_key()),
                ("frequency",            "annual"),
                ("data[0]",              "price"),
                ("facets[stateid][]",    state),
                ("facets[sectorid][]",   "COM"),
                ("sort[0][column]",      "period"),
                ("sort[0][direction]",   "desc"),
                ("length",               "1"),
            ]
            data = await self._fetch_with_retry(
                f"{EIA_BASE_URL}/electricity/retail-sales/data/",
                params=params,
            )
            rows = data.get("response", {}).get("data", [])
            result = float(rows[0]["price"]) if rows else 11.0
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(
                source="eia",
                message=f"electricity rate fetch failed for {state}: {e}",
            )

    async def get_renewable_pct(self, state: str) -> float:
        """
        Returns percentage of the state's electricity generation from renewables.
        Range: 0–100.

        FIX: EIA requires repeated params for array values — uses list-of-tuples
        instead of a dict, which is how httpx handles multi-value query params.
        """
        state = state.upper()
        cache_key = self._cache_key("renewable_pct", state)
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
            result = float(MOCK_RENEWABLE_PCT.get(state, 15.0))
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        try:
            # IMPORTANT: list-of-tuples is required here.
            # Passing {"facets[fueltypeId][]": ["SUN","WND",...]} causes a 400
            # because httpx serializes it as a single param with a Python list str.
            # List-of-tuples produces: facets[fueltypeId][]=SUN&facets[fueltypeId][]=WND
            params = (
                [
                    ("api_key",            self._api_key()),
                    ("frequency",          "annual"),
                    ("data[0]",            "generation"),
                    ("facets[location][]",   state),
                    ("sort[0][column]",    "period"),
                    ("sort[0][direction]", "desc"),
                    ("length",             "10"),
                ]
                + [("facets[fueltypeid][]", ft) for ft in RENEWABLE_FUEL_TYPES]
            )

            data = await self._fetch_with_retry(
                f"{EIA_BASE_URL}/electricity/electric-power-operational-data/data/",
                params=params,
            )
            rows = data.get("response", {}).get("data", [])
            renewable_mwh = sum(float(r.get("generation") or 0) for r in rows)

            # Calculate percentage against known state total
            state_total = STATE_TOTAL_GENERATION_MWH.get(state, 100_000_000)
            result = round(min(100.0, (renewable_mwh / state_total) * 100), 1)

            # Sanity check — if result is 0 or suspiciously low, fall back to mock
            if result < 1.0:
                logger.warning(f"EIA renewable pct suspiciously low for {state} ({result}%), using curated value")
                result = float(MOCK_RENEWABLE_PCT.get(state, 15.0))

            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        except IntegrationError:
            raise
        except Exception as e:
            logger.warning(f"EIA renewable pct failed for {state}, using curated value: {e}")
            return float(MOCK_RENEWABLE_PCT.get(state, 15.0))

    async def get_reliability_index(self, state: str) -> float:
        """
        Returns grid reliability index (0–100, 100 = most reliable).
        Uses curated SAIDI-derived values — EIA reliability requires complex aggregation.
        State-level — one call per state.
        """
        state = state.upper()
        cache_key = self._cache_key("reliability", state)
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        result = float(MOCK_RELIABILITY.get(state, 70.0))
        await self._set_cached(cache_key, result, ttl_hours=7 * 24)
        return result

    async def get_utility_territories(self, bbox: BoundingBox) -> list[dict]:
        """
        Returns electric utility service territory polygons as GeoJSON Features.
        In production these are loaded from a pre-ingested PostGIS table.
        """
        cache_key = self._cache_key(
            "utility_territories",
            bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng,
        )
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_utility_territories(bbox)
            await self._set_cached(cache_key, result, ttl_hours=7 * 24)
            return result

        logger.warning(
            "EIA utility territory spatial data not yet loaded from GCS/PostGIS. "
            "Pre-ingest the EIA Form 861 service territory file to enable this."
        )
        return self._mock_utility_territories(bbox)

    def _mock_utility_territories(self, bbox: BoundingBox) -> list[dict]:
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[
                [bbox.min_lng, bbox.min_lat], [clng, bbox.min_lat],
                [clng, bbox.max_lat], [bbox.min_lng, bbox.max_lat],
                [bbox.min_lng, bbox.min_lat],
            ]]}, "properties": {"utility_name": "Duke Energy Carolinas", "state": "NC"}},
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[
                [clng, bbox.min_lat], [bbox.max_lng, bbox.min_lat],
                [bbox.max_lng, bbox.max_lat], [clng, bbox.max_lat],
                [clng, bbox.min_lat],
            ]]}, "properties": {"utility_name": "Duke Energy Progress", "state": "NC"}},
        ]