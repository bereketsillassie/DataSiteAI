"""
app/api/v1/listings.py
───────────────────────
GET /api/v1/listings — search land listings by analysis region or point radius.

Two search modes:
  1. By analysis_id: finds listings within the analysis bbox (PostGIS ST_Within join)
  2. By lat/lng + radius_km: spatial radius search (PostGIS ST_DWithin)

Both modes attach the nearest scored grid cell's scores to each listing.
A stale-data warning is included in metadata if any listing is >14 days old.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.dependencies import get_db, get_redis
from app.models.responses import ListingsResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/listings",
    response_model=ListingsResponse,
    summary="Search land listings",
    description=(
        "Search by analysis_id (finds listings within that analysis bbox) "
        "or by lat/lng point with a radius_km. Both modes attach nearest cell "
        "scores to each listing. Provide either analysis_id OR lat+lng — not both required."
    ),
)
async def get_listings(
    analysis_id: Optional[str] = Query(
        None,
        description="Analysis ID from POST /analyze — finds listings within the analysis bbox",
    ),
    lat: Optional[float] = Query(
        None,
        ge=24.0,
        le=50.0,
        description="Latitude for point-radius search (requires lng)",
    ),
    lng: Optional[float] = Query(
        None,
        ge=-125.0,
        le=-66.0,
        description="Longitude for point-radius search (requires lat)",
    ),
    radius_km: Optional[float] = Query(
        50.0,
        ge=0.1,
        le=500.0,
        description="Search radius in km (used with lat/lng, default 50km)",
    ),
    min_acres: Optional[float] = Query(None, ge=0.1, description="Minimum parcel size in acres"),
    max_acres: Optional[float] = Query(None, ge=0.1, description="Maximum parcel size in acres"),
    max_price_usd: Optional[int] = Query(None, ge=0, description="Maximum listing price in USD"),
    state: Optional[str] = Query(
        None,
        min_length=2,
        max_length=2,
        description="Filter by 2-letter US state code",
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of listings to return"),
    db: AsyncSession = Depends(get_db),
    redis_client: Optional[aioredis.Redis] = Depends(get_redis),
) -> ListingsResponse:
    # Must provide either analysis_id or lat+lng
    if not analysis_id and (lat is None or lng is None):
        raise HTTPException(
            status_code=422,
            detail="Provide either analysis_id or both lat and lng for a point-radius search.",
        )

    # lat and lng must come together
    if (lat is None) != (lng is None):
        raise HTTPException(
            status_code=422,
            detail="lat and lng must both be provided together.",
        )

    from app.config import settings
    from app.core.listings.listing_service import ListingService

    listing_service = ListingService(db_session=db, settings=settings)

    if analysis_id:
        listings, is_stale = await listing_service.get_listings_in_region(
            analysis_id=analysis_id,
            min_acres=min_acres,
            max_acres=max_acres,
            max_price_usd=max_price_usd,
            limit=limit,
        )
    else:
        listings, is_stale = await listing_service.get_listings_near(
            lat=lat,
            lng=lng,
            radius_km=radius_km or 50.0,
            min_acres=min_acres,
            max_acres=max_acres,
            max_price_usd=max_price_usd,
            state=state.upper() if state else None,
            limit=limit,
        )

    if is_stale:
        logger.warning(
            f"Stale listing data (>14 days) returned for "
            f"analysis_id={analysis_id or 'N/A'} lat={lat} lng={lng}"
        )

    return ListingsResponse(listings=listings, total=len(listings))
