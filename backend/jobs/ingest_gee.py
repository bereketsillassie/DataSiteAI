"""
jobs/ingest_gee.py
────────────────────
Cloud Run Job: Export GEE raster data to GCS as Cloud-Optimized GeoTIFFs.
Run weekly. Schedule: every Sunday at 2:00 AM UTC.

Usage:
  python -m jobs.ingest_gee --state NC
  python -m jobs.ingest_gee --state TX

Cloud Run Job command:
  python -m jobs.ingest_gee
"""

import asyncio
import logging
import sys
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Default states to ingest if none specified
DEFAULT_STATES = ["NC", "VA", "TX", "GA", "TN", "CO", "AZ"]

# Bounding boxes for each state (approximate)
STATE_BBOXES = {
    "NC": {"min_lat": 33.75, "min_lng": -84.33, "max_lat": 36.59, "max_lng": -75.46},
    "VA": {"min_lat": 36.54, "min_lng": -83.68, "max_lat": 39.47, "max_lng": -75.24},
    "TX": {"min_lat": 25.84, "min_lng": -106.65, "max_lat": 36.50, "max_lng": -93.51},
    "GA": {"min_lat": 30.36, "min_lng": -85.61, "max_lat": 35.00, "max_lng": -80.84},
    "TN": {"min_lat": 34.98, "min_lng": -90.31, "max_lat": 36.68, "max_lng": -81.65},
    "CO": {"min_lat": 36.99, "min_lng": -109.06, "max_lat": 41.00, "max_lng": -102.04},
    "AZ": {"min_lat": 31.33, "min_lng": -114.82, "max_lat": 37.00, "max_lng": -109.04},
}


async def ingest_state(state: str, mock: bool = False):
    """Ingest GEE data for a single state bbox."""
    if state not in STATE_BBOXES:
        logger.warning(f"No bbox configured for state {state}")
        return

    bbox_data = STATE_BBOXES[state]
    from app.models.domain import BoundingBox
    bbox = BoundingBox(**bbox_data)

    from app.config import settings
    from app.integrations.gee import GEEClient

    client = GEEClient(redis_client=None, settings=settings)

    logger.info(f"Ingesting GEE data for {state}...")

    try:
        land_cover = await client.get_land_cover(bbox)
        logger.info(f"  {state}: land cover — {len(land_cover.get('grid', []))} points")
    except Exception as e:
        logger.error(f"  {state}: land cover failed: {e}")

    try:
        elevation = await client.get_elevation(bbox)
        logger.info(f"  {state}: elevation — {len(elevation.get('grid', []))} points")
    except Exception as e:
        logger.error(f"  {state}: elevation failed: {e}")

    try:
        ndvi = await client.get_ndvi(bbox)
        logger.info(f"  {state}: NDVI — {len(ndvi.get('grid', []))} points")
    except Exception as e:
        logger.error(f"  {state}: NDVI failed: {e}")

    logger.info(f"  {state}: GEE ingest complete")


async def main():
    states = sys.argv[2:] if len(sys.argv) > 2 and sys.argv[1] == "--state" else DEFAULT_STATES
    mock = os.getenv("MOCK_INTEGRATIONS", "false").lower() == "true"

    logger.info(f"GEE ingest job starting. States: {states}. Mock: {mock}")

    for state in states:
        await ingest_state(state, mock=mock)

    logger.info("GEE ingest job complete.")


if __name__ == "__main__":
    asyncio.run(main())
