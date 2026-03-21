"""
jobs/ingest_listings.py
────────────────────────
Cloud Run Job: Scrape land listings from LandWatch and county portals.
Run weekly. Schedule: every Monday at 3:00 AM UTC.

Usage:
  python -m jobs.ingest_listings --state NC
  python -m jobs.ingest_listings           # runs all default states
"""

import asyncio
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_STATES = ["NC", "VA", "TX", "GA", "TN", "CO", "AZ"]


async def ingest_state_listings(state: str, db_session=None):
    """Scrape and store listings for one state."""
    from app.config import settings
    from app.core.listings.landwatch_scraper import LandWatchScraper
    from app.core.listings.county_parcel_fetcher import CountyParcelFetcher

    scraper = LandWatchScraper(settings=settings)
    parcel_fetcher = CountyParcelFetcher(settings=settings)

    # LandWatch scrape
    logger.info(f"  {state}: Scraping LandWatch...")
    try:
        lw_listings = await scraper.scrape_state(state, min_acres=20.0)
        logger.info(f"  {state}: Got {len(lw_listings)} LandWatch listings")
        if db_session:
            await _upsert_listings(db_session, lw_listings)
    except Exception as e:
        logger.error(f"  {state}: LandWatch scrape failed: {e}")

    # County parcel fetch
    logger.info(f"  {state}: Fetching county parcels...")
    try:
        parcels = await parcel_fetcher.fetch_state_parcels(state, min_acres=20.0)
        logger.info(f"  {state}: Got {len(parcels)} county parcels")
        if db_session:
            await _upsert_listings(db_session, parcels)
    except Exception as e:
        logger.error(f"  {state}: County parcel fetch failed: {e}")

    await scraper.close()


async def _upsert_listings(db_session, listings: list[dict]):
    """Insert or update listings in the database."""
    from sqlalchemy import text
    import json

    for listing in listings:
        try:
            await db_session.execute(text("""
                INSERT INTO land_listings (
                    id, external_id, source, address, state, county,
                    acres, price_usd, price_per_acre, listing_url, raw_data, scraped_at,
                    point
                )
                VALUES (
                    gen_random_uuid(),
                    :external_id, :source, :address, :state, :county,
                    :acres, :price_usd, :price_per_acre, :listing_url, :raw_data::jsonb, NOW(),
                    CASE WHEN :lat IS NOT NULL AND :lng IS NOT NULL
                         THEN ST_MakePoint(:lng, :lat)::geometry
                         ELSE NULL END
                )
                ON CONFLICT (external_id) DO UPDATE SET
                    price_usd = EXCLUDED.price_usd,
                    price_per_acre = EXCLUDED.price_per_acre,
                    scraped_at = EXCLUDED.scraped_at
            """), {
                "external_id": listing.get("external_id"),
                "source": listing["source"],
                "address": listing.get("address"),
                "state": listing.get("state"),
                "county": listing.get("county"),
                "acres": listing.get("acres"),
                "price_usd": listing.get("price_usd"),
                "price_per_acre": listing.get("price_per_acre"),
                "listing_url": listing.get("listing_url"),
                "raw_data": json.dumps(listing),
                "lat": listing.get("lat"),
                "lng": listing.get("lng"),
            })
        except Exception as e:
            logger.debug(f"Upsert failed for listing: {e}")

    await db_session.commit()


async def main():
    states = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_STATES
    mock = os.getenv("MOCK_INTEGRATIONS", "false").lower() == "true"

    logger.info(f"Listing ingest job starting. States: {states}. Mock: {mock}")

    # Get DB session
    db_session = None
    if not mock:
        from app.db.session import AsyncSessionLocal
        from app.db.session import init_db
        await init_db()
        async with AsyncSessionLocal() as session:
            for state in states:
                await ingest_state_listings(state, db_session=session)
    else:
        for state in states:
            await ingest_state_listings(state, db_session=None)

    logger.info("Listing ingest job complete.")


if __name__ == "__main__":
    asyncio.run(main())
