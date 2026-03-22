"""
app/core/listings/listing_service.py
──────────────────────────────────────
High-level listing queries that combine scraped data with scoring results.

Two main methods:
  get_listings_near(lat, lng, radius_km, filters) -> list[Listing]
  get_listings_in_region(analysis_id, filters) -> list[Listing]

Both attach the nearest grid cell scores to each listing.
"""

import logging
import math
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.models.responses import Listing

logger = logging.getLogger(__name__)

# Maximum age for listing data before showing a "stale" warning
LISTING_STALE_DAYS = 14


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate great-circle distance in km between two WGS84 points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


class ListingService:
    """
    Manages queries against the land_listings table.
    Attaches nearest cell scores to each listing for context.
    """

    def __init__(self, db_session=None, settings=None):
        from app.config import settings as default_settings
        self.db = db_session
        self.settings = settings or default_settings
        self.mock = self.settings.MOCK_INTEGRATIONS

    async def get_listings_near(
        self,
        lat: float,
        lng: float,
        radius_km: float = 50.0,
        min_acres: Optional[float] = None,
        max_acres: Optional[float] = None,
        max_price_usd: Optional[int] = None,
        state: Optional[str] = None,
        limit: int = 20,
        score_bundles: Optional[list] = None,
    ) -> tuple[list[Listing], bool]:
        """
        Find land listings within radius_km of (lat, lng).
        Returns (listings, is_stale) where is_stale=True if data is >14 days old.
        """
        if self.mock or self.db is None:
            return self._mock_listings_near(lat, lng, radius_km, limit, score_bundles), False

        try:
            from sqlalchemy import text
            query = text("""
                SELECT
                    id, external_id, source, address, state, county,
                    acres, price_usd, price_per_acre, zoning, listing_url,
                    scraped_at,
                    ST_Y(point::geometry) as lat,
                    ST_X(point::geometry) as lng,
                    ST_Distance(
                        point::geography,
                        ST_MakePoint(:lng, :lat)::geography
                    ) / 1000.0 as distance_km
                FROM land_listings
                WHERE
                    point IS NOT NULL
                    AND ST_DWithin(
                        point::geography,
                        ST_MakePoint(:lng, :lat)::geography,
                        :radius_m
                    )
                    AND (cast(:min_acres as numeric) IS NULL OR acres >= cast(:min_acres as numeric))
                    AND (cast(:max_acres as numeric) IS NULL OR acres <= cast(:max_acres as numeric))
                    AND (cast(:max_price as bigint) IS NULL OR price_usd <= cast(:max_price as bigint))
                    AND (cast(:state as text) IS NULL OR state = cast(:state as text))
                ORDER BY distance_km ASC
                LIMIT :limit
            """)

            result = await self.db.execute(query, {
                "lat": lat,
                "lng": lng,
                "radius_m": radius_km * 1000,
                "min_acres": min_acres,
                "max_acres": max_acres,
                "max_price": max_price_usd,
                "state": state,
                "limit": limit,
            })
            rows = result.mappings().all()
            listings = [self._row_to_listing(row, score_bundles) for row in rows]

            is_stale = self._check_stale(listings)
            return listings, is_stale

        except Exception as e:
            logger.error(f"Listing query failed: {e}")
            return [], False

    async def get_listings_in_region(
        self,
        analysis_id: str,
        min_acres: Optional[float] = None,
        max_acres: Optional[float] = None,
        max_price_usd: Optional[int] = None,
        limit: int = 20,
        score_bundles: Optional[list] = None,
    ) -> tuple[list[Listing], bool]:
        """
        Find land listings within the bbox of an analysis.
        Looks up the bbox from analysis_regions table.
        """
        if self.mock or self.db is None:
            return self._mock_listings_for_region(analysis_id, limit, score_bundles), False

        try:
            from sqlalchemy import text
            query = text("""
                SELECT
                    ll.id, ll.external_id, ll.source, ll.address, ll.state, ll.county,
                    ll.acres, ll.price_usd, ll.price_per_acre, ll.zoning, ll.listing_url,
                    ll.scraped_at,
                    ST_Y(ll.point::geometry) as lat,
                    ST_X(ll.point::geometry) as lng
                FROM land_listings ll
                JOIN analysis_regions ar ON ST_Within(ll.point::geometry, ar.bbox::geometry)
                WHERE
                    ar.id = :analysis_id
                    AND ll.point IS NOT NULL
                    AND (:min_acres IS NULL OR ll.acres >= :min_acres)
                    AND (:max_acres IS NULL OR ll.acres <= :max_acres)
                    AND (:max_price IS NULL OR ll.price_usd <= :max_price)
                ORDER BY ll.acres DESC
                LIMIT :limit
            """)
            result = await self.db.execute(query, {
                "analysis_id": analysis_id,
                "min_acres": min_acres,
                "max_acres": max_acres,
                "max_price": max_price_usd,
                "limit": limit,
            })
            rows = result.mappings().all()
            listings = [self._row_to_listing(row, score_bundles) for row in rows]
            is_stale = self._check_stale(listings)
            return listings, is_stale

        except Exception as e:
            logger.error(f"Region listing query failed: {e}")
            return [], False

    def _row_to_listing(self, row, score_bundles: Optional[list]) -> Listing:
        """Convert a DB row to a Listing response object."""
        lat = row.get("lat")
        lng = row.get("lng")

        # Find nearest scored cell to attach scores
        nearest_scores = (
            self._find_nearest_scores(lat, lng, score_bundles)
            if (lat and lng and score_bundles)
            else {}
        )

        scraped_raw = row.get("scraped_at")
        if scraped_raw is None:
            scraped_str = datetime.now(timezone.utc).isoformat()
        elif hasattr(scraped_raw, "isoformat"):
            scraped_str = scraped_raw.isoformat()
        else:
            scraped_str = str(scraped_raw)

        return Listing(
            id=str(row["id"]),
            source=row.get("source", "unknown"),
            address=row.get("address"),
            state=row.get("state", ""),
            county=row.get("county"),
            acres=float(row.get("acres") or 0),
            price_usd=row.get("price_usd"),
            price_per_acre=float(row["price_per_acre"]) if row.get("price_per_acre") else None,
            zoning=row.get("zoning"),
            coordinates={"lat": lat, "lng": lng},
            polygon=None,
            listing_url=row.get("listing_url"),
            nearest_cell_scores=nearest_scores,
            scraped_at=scraped_str,
        )

    def _find_nearest_scores(self, lat: float, lng: float, bundles: list) -> dict[str, float]:
        """Find the nearest scored grid cell and return its scores."""
        if not bundles or lat is None or lng is None:
            return {}

        nearest = min(
            bundles,
            key=lambda b: _haversine_km(lat, lng, b.location.lat, b.location.lng),
        )
        return {
            "composite": nearest.composite_score.composite,
            **nearest.scores,
        }

    def _check_stale(self, listings: list[Listing]) -> bool:
        """Returns True if any listing data is older than LISTING_STALE_DAYS days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=LISTING_STALE_DAYS)
        for listing in listings:
            try:
                scraped = datetime.fromisoformat(listing.scraped_at.replace("Z", "+00:00"))
                if scraped < cutoff:
                    return True
            except Exception:
                pass
        return False

    def _mock_listings_near(
        self,
        lat: float,
        lng: float,
        radius_km: float,
        limit: int,
        score_bundles: Optional[list],
    ) -> list[Listing]:
        """Return mock listings near a point."""
        from app.core.listings.landwatch_scraper import LandWatchScraper
        scraper = LandWatchScraper(settings=self.settings)
        raw = scraper._mock_listings("NC")
        now = datetime.now(timezone.utc).isoformat()

        listings = []
        for i, raw_listing in enumerate(raw[:limit]):
            listing_lat = raw_listing.get("lat") or lat + (i * 0.05)
            listing_lng = raw_listing.get("lng") or lng + (i * 0.04)
            dist = _haversine_km(lat, lng, listing_lat, listing_lng)
            if dist > radius_km:
                continue

            nearest_scores = (
                self._find_nearest_scores(listing_lat, listing_lng, score_bundles)
                if score_bundles
                else {
                    "composite": 0.75,
                    "power": 0.8,
                    "water": 0.9,
                    "geological": 0.7,
                    "climate": 0.85,
                    "connectivity": 0.6,
                    "economic": 0.75,
                    "environmental": 0.5,
                }
            )

            listings.append(
                Listing(
                    id=raw_listing.get("external_id", f"mock_{i}"),
                    source=raw_listing["source"],
                    address=raw_listing.get("address"),
                    state=raw_listing["state"],
                    county=raw_listing.get("county"),
                    acres=raw_listing["acres"],
                    price_usd=raw_listing.get("price_usd"),
                    price_per_acre=raw_listing.get("price_per_acre"),
                    zoning=None,
                    coordinates={"lat": listing_lat, "lng": listing_lng},
                    polygon=None,
                    listing_url=raw_listing.get("listing_url"),
                    nearest_cell_scores=nearest_scores,
                    scraped_at=now,
                )
            )
        return listings

    def _mock_listings_for_region(
        self,
        analysis_id: str,
        limit: int,
        score_bundles: Optional[list],
    ) -> list[Listing]:
        """Return mock listings for an analysis region (centered on NC Research Triangle)."""
        return self._mock_listings_near(35.95, -78.9, 100.0, limit, score_bundles)
