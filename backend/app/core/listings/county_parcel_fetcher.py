"""
app/core/listings/county_parcel_fetcher.py
───────────────────────────────────────────
Bulk county parcel data fetcher.
Downloads GIS parcel data from state/county open data portals.
Converts to PostGIS format via geopandas/fiona.

Priority states: NC, VA, TX, TN, GA, CO, AZ
Filters: parcels > 20 acres

In MOCK mode: returns pre-defined mock parcels without any downloads.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import settings as default_settings

logger = logging.getLogger(__name__)

# State open data portal URLs for parcel GIS data
# These are real publicly available bulk downloads (as of 2024)
STATE_PARCEL_SOURCES = {
    "NC": {
        "url": "https://www.nconemap.gov/datasets/parcels/api/download?where=1%3D1&outFields=*&f=geojson",
        "format": "geojson",
        "acres_field": "CALC_ACRES",
        "address_field": "FULL_STREE",
        "county_field": "COUNTY",
    },
    "VA": {
        "url": "https://data.virginia.gov/api/geospatial/parcels?method=export&type=GeoJSON",
        "format": "geojson",
        "acres_field": "ACREAGE",
        "address_field": "SITUS_ADDRESS",
        "county_field": "LOCALITY_NAME",
    },
    "TX": {
        "url": "https://opendata.arcgis.com/datasets/texas-parcels.geojson",
        "format": "geojson",
        "acres_field": "GIS_ACRES",
        "address_field": "SITE_ADDR",
        "county_field": "CNTY_NM",
    },
    "TN": {
        "url": "https://www.tn.gov/content/dam/tn/environment/maps/parcels-tn.geojson",
        "format": "geojson",
        "acres_field": "ACRES",
        "address_field": "SITUS_ADDR",
        "county_field": "COUNTY_NM",
    },
    "GA": {
        "url": "https://opendata.arcgis.com/datasets/georgia-parcels.geojson",
        "format": "geojson",
        "acres_field": "CALC_ACREAGE",
        "address_field": "SITUS_ADDRESS",
        "county_field": "COUNTY_NAME",
    },
    "CO": {
        "url": "https://data.colorado.gov/api/geospatial/parcels?method=export&type=GeoJSON",
        "format": "geojson",
        "acres_field": "ACRES",
        "address_field": "SITE_ADDR",
        "county_field": "COUNTY",
    },
    "AZ": {
        "url": "https://opendata.arcgis.com/datasets/arizona-parcels.geojson",
        "format": "geojson",
        "acres_field": "ACREAGE",
        "address_field": "SITE_ADDRESS",
        "county_field": "COUNTY_NAME",
    },
}


class CountyParcelFetcher:
    """Downloads and processes bulk county parcel data."""

    def __init__(self, settings=None):
        self.settings = settings or default_settings
        self.mock = self.settings.MOCK_INTEGRATIONS

    async def fetch_state_parcels(
        self,
        state: str,
        min_acres: float = 20.0,
    ) -> list[dict]:
        """
        Fetch large parcels for a state.
        Returns list of listing dicts ready for land_listings table.
        """
        state = state.upper()
        if self.mock:
            return self._mock_parcels(state, min_acres)

        if state not in STATE_PARCEL_SOURCES:
            logger.warning(f"No parcel source configured for state {state}")
            return []

        source = STATE_PARCEL_SOURCES[state]
        try:
            return await self._download_and_process(state, source, min_acres)
        except Exception as e:
            logger.error(f"County parcel fetch failed for {state}: {e}")
            return []

    async def _download_and_process(
        self,
        state: str,
        source: dict,
        min_acres: float,
    ) -> list[dict]:
        """Download GeoJSON parcel data and filter by acreage."""
        import httpx
        import geopandas as gpd
        import io

        async with httpx.AsyncClient(timeout=60.0) as client:
            logger.info(f"Downloading parcel data for {state} from {source['url'][:60]}...")
            response = await client.get(source["url"])
            response.raise_for_status()

        # Load into GeoPandas
        gdf = gpd.read_file(io.StringIO(response.text))

        # Ensure WGS84 (EPSG:4326) — reproject if necessary
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        # Filter by acreage
        acres_field = source["acres_field"]
        if acres_field in gdf.columns:
            gdf = gdf[gdf[acres_field].fillna(0) >= min_acres]

        listings = []
        now = datetime.now(timezone.utc).isoformat()
        for _, row in gdf.iterrows():
            try:
                acres = float(row.get(acres_field, 0) or 0)
                if acres < min_acres:
                    continue

                # Get centroid for point geometry
                centroid = row.geometry.centroid if row.geometry else None
                lat = centroid.y if centroid else None
                lng = centroid.x if centroid else None

                listings.append({
                    "source": "county_parcel",
                    "state": state,
                    "county": str(row.get(source["county_field"], "")),
                    "address": str(row.get(source["address_field"], "")),
                    "acres": acres,
                    "price_usd": None,
                    "price_per_acre": None,
                    "lat": lat,
                    "lng": lng,
                    "listing_url": None,
                    "scraped_at": now,
                })
            except Exception as e:
                logger.debug(f"Failed to process parcel row: {e}")

        logger.info(f"Fetched {len(listings)} parcels >= {min_acres} acres for {state}")
        return listings

    def _mock_parcels(self, state: str, min_acres: float) -> list[dict]:
        """Return mock county parcels for testing."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            {
                "source": "county_parcel",
                "external_id": "parcel_mock_001",
                "state": state,
                "county": "Wake",
                "address": "0 Industrial Tract, Wake County, NC",
                "acres": 55.0,
                "price_usd": None,
                "price_per_acre": None,
                "lat": 35.820,
                "lng": -78.670,
                "listing_url": None,
                "scraped_at": now,
            },
            {
                "source": "county_parcel",
                "external_id": "parcel_mock_002",
                "state": state,
                "county": "Durham",
                "address": "0 Research Campus Rd, Durham County, NC",
                "acres": 38.5,
                "price_usd": None,
                "price_per_acre": None,
                "lat": 35.991,
                "lng": -78.910,
                "listing_url": None,
                "scraped_at": now,
            },
            {
                "source": "county_parcel",
                "external_id": "parcel_mock_003",
                "state": state,
                "county": "Cabarrus",
                "address": "0 Concord Pkwy N, Cabarrus County, NC",
                "acres": 72.3,
                "price_usd": None,
                "price_per_acre": None,
                "lat": 35.415,
                "lng": -80.609,
                "listing_url": None,
                "scraped_at": now,
            },
            {
                "source": "county_parcel",
                "external_id": "parcel_mock_004",
                "state": state,
                "county": "Guilford",
                "address": "0 Commerce Center Blvd, Guilford County, NC",
                "acres": 44.8,
                "price_usd": None,
                "price_per_acre": None,
                "lat": 36.080,
                "lng": -79.827,
                "listing_url": None,
                "scraped_at": now,
            },
        ]
