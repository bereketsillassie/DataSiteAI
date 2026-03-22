"""
app/api/v1/analyze.py
──────────────────────
POST /api/v1/analyze — the main analysis endpoint.

Flow:
  1. Validate request (bbox, state, grid resolution)
<<<<<<< HEAD
  2. Run ScoringEngine.score_region() -> list[ScoreBundle]
  3. Persist analysis_region and location_scores to DB
  4. Build all 8 GeoJSON layers -> cache in integration_cache table
  5. If include_listings: fetch land listings in bbox
  6. Return full AnalyzeResponse
=======
  2. Generate grid of candidate cells
  3. Run ScoringEngine.score_region() -> list[ScoreBundle]
  4. Persist analysis_region and location_scores to DB
  5. Build all 8 GeoJSON layers -> cache in Redis
  6. If include_listings: fetch land listings in bbox
  7. Return full AnalyzeResponse
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
"""

import json
import logging
import time
import uuid
<<<<<<< HEAD
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
=======
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.config import settings
from app.dependencies import get_db, get_redis
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
from app.models.requests import AnalyzeRequest
from app.models.responses import (
    AnalyzeResponse,
    RegionInfo,
    AnalysisMetadata,
)
from app.core.scoring.engine import create_scoring_engine
from app.core.listings.listing_service import ListingService

logger = logging.getLogger(__name__)
router = APIRouter()

LAYER_IDS = [
<<<<<<< HEAD
    "power", "water", "geological", "climate",
    "connectivity", "economic", "environmental", "optimal",
=======
    "power",
    "water",
    "geological",
    "climate",
    "connectivity",
    "economic",
    "environmental",
    "optimal",
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
]


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze a geographic region for data center suitability",
<<<<<<< HEAD
=======
    description=(
        "Generates a grid of candidate locations within the bounding box, "
        "scores each location across 7 categories using free public data sources, "
        "builds 8 GeoJSON map layers, and optionally finds land listings for sale."
    ),
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
)
async def analyze_region(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
<<<<<<< HEAD
=======
    redis_client: Optional[aioredis.Redis] = Depends(get_redis),
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
) -> AnalyzeResponse:
    start_time = time.time()
    analysis_id = str(uuid.uuid4())

    logger.info(
        f"Starting analysis {analysis_id} for state={request.state} "
<<<<<<< HEAD
        f"bbox=({request.bbox.min_lat},{request.bbox.min_lng})-"
        f"({request.bbox.max_lat},{request.bbox.max_lng})"
    )

    from app.models.domain import BoundingBox
=======
        f"bbox=({request.bbox.min_lat},{request.bbox.min_lng})-({request.bbox.max_lat},{request.bbox.max_lng})"
    )

    # ── Step 1: Build BoundingBox domain object ────────────────────────────────
    from app.models.domain import BoundingBox

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    bbox = BoundingBox(
        min_lat=request.bbox.min_lat,
        min_lng=request.bbox.min_lng,
        max_lat=request.bbox.max_lat,
        max_lng=request.bbox.max_lng,
    )

<<<<<<< HEAD
    # ── Score the region ───────────────────────────────────────────────────────
    engine = create_scoring_engine(db_session=db, settings=settings)
    try:
        grid_cells = await engine.score_region(
            bbox, grid_resolution_km=request.grid_resolution_km
        )
    except Exception as e:
        logger.error(f"Scoring engine failed for {analysis_id}: {e}")
=======
    # ── Step 2: Run scoring engine ─────────────────────────────────────────────
    engine = create_scoring_engine(redis_client=redis_client, settings=settings)

    try:
        grid_cells = await engine.score_region(bbox, grid_resolution_km=request.grid_resolution_km)
    except Exception as e:
        logger.error(f"Scoring engine failed for analysis {analysis_id}: {e}")
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")

    if not grid_cells:
        raise HTTPException(
            status_code=422,
<<<<<<< HEAD
            detail="No grid cells could be scored for this bbox.",
        )

    logger.info(
        f"Scoring complete: {len(grid_cells)} cells, "
        f"top composite={grid_cells[0].composite_score.composite}"
    )

    # ── Persist to database ────────────────────────────────────────────────────
    try:
        await _persist_analysis(db, analysis_id, request, grid_cells, bbox)
    except Exception as e:
        logger.warning(
            f"DB persist failed for analysis {analysis_id} (continuing): {e}"
        )

    # ── Build and cache GeoJSON layers ─────────────────────────────────────────
    await _build_and_cache_layers(db, analysis_id, grid_cells)

    # ── Fetch land listings ────────────────────────────────────────────────────
=======
            detail="No grid cells could be scored for this bbox. Try a larger area or check the state parameter.",
        )

    logger.info(f"Scoring complete: {len(grid_cells)} cells, top composite={grid_cells[0].composite_score.composite}")

    # ── Step 3: Persist to database ────────────────────────────────────────────
    try:
        await _persist_analysis(db, analysis_id, request, grid_cells, bbox)
    except Exception as e:
        logger.warning(f"DB persist failed for analysis {analysis_id} (continuing without DB): {e}")

    # ── Step 4: Build and cache GeoJSON layers ─────────────────────────────────
    await _build_and_cache_layers(analysis_id, grid_cells, redis_client)

    # ── Step 5: Fetch land listings ────────────────────────────────────────────
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    listings = []
    listings_stale = False
    if request.include_listings:
        try:
            import math
<<<<<<< HEAD
            listing_service = ListingService(db_session=db, settings=settings)
            center_lat = (request.bbox.min_lat + request.bbox.max_lat) / 2
            center_lng = (request.bbox.min_lng + request.bbox.max_lng) / 2
            radius_km = math.sqrt(bbox.area_sq_km() / math.pi) * 1.2
=======

            listing_service = ListingService(db_session=db, settings=settings)
            center_lat = (request.bbox.min_lat + request.bbox.max_lat) / 2
            center_lng = (request.bbox.min_lng + request.bbox.max_lng) / 2
            # Use a radius large enough to cover the bbox
            radius_km = math.sqrt(bbox.area_sq_km() / math.pi) * 1.2

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
            listings, listings_stale = await listing_service.get_listings_near(
                lat=center_lat,
                lng=center_lng,
                radius_km=radius_km,
                min_acres=request.min_acres,
                max_acres=request.max_acres,
                limit=50,
                score_bundles=grid_cells,
            )
<<<<<<< HEAD
            logger.info(f"Found {len(listings)} listings for analysis {analysis_id}")
        except Exception as e:
            logger.warning(f"Listing fetch failed (continuing): {e}")

    # ── Build response ─────────────────────────────────────────────────────────
    processing_time_ms = int((time.time() - start_time) * 1000)
    from app.core.scoring.weights import CATEGORY_WEIGHTS

=======
            logger.info(f"Found {len(listings)} land listings for analysis {analysis_id}")
        except Exception as e:
            logger.warning(f"Listing fetch failed (continuing without listings): {e}")

    # ── Step 6: Build response ─────────────────────────────────────────────────
    processing_time_ms = int((time.time() - start_time) * 1000)

    from app.core.scoring.weights import CATEGORY_WEIGHTS

    layer_urls = {
        layer_id: f"/api/v1/layers/{layer_id}?analysis_id={analysis_id}"
        for layer_id in LAYER_IDS
    }

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    return AnalyzeResponse(
        analysis_id=analysis_id,
        region=RegionInfo(
            bbox=bbox.to_geojson_polygon(),
            state=request.state,
            grid_resolution_km=request.grid_resolution_km,
        ),
        grid_cells=grid_cells,
        listings=listings,
        layers_available=LAYER_IDS,
<<<<<<< HEAD
        layer_urls={
            lid: f"/api/v1/layers/{lid}?analysis_id={analysis_id}"
            for lid in LAYER_IDS
        },
=======
        layer_urls=layer_urls,
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        metadata=AnalysisMetadata(
            grid_cells_analyzed=len(grid_cells),
            processing_time_ms=processing_time_ms,
            weights_used=dict(CATEGORY_WEIGHTS),
            data_freshness={
<<<<<<< HEAD
                "gee":     "2023-12-01",
                "osm":     datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "listings":datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "eia":     datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "noaa":    "2023-01-01",
                "census":  "2022-01-01",
=======
                "gee": "2023-12-01",
                "osm": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "listings": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "eia": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "noaa": "2023-01-01",
                "census": "2022-01-01",
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
            },
            listings_stale=listings_stale,
        ),
    )


async def _persist_analysis(
    db: AsyncSession,
    analysis_id: str,
    request: AnalyzeRequest,
    grid_cells: list,
    bbox,
) -> None:
<<<<<<< HEAD
    """Persist analysis region and all scored cells to the database."""
    bbox_geojson = json.dumps(bbox.to_geojson_polygon())

=======
    """Persist analysis region and all location scores to the database."""
    from sqlalchemy import text

    bbox_geojson = json.dumps(bbox.to_geojson_polygon())

    # Insert analysis_regions row
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    await db.execute(
        text("""
            INSERT INTO analysis_regions (id, bbox, state, grid_res_km, cache_expires_at)
            VALUES (
                :id,
<<<<<<< HEAD
                ST_GeomFromGeoJSON(:bbox_json),
=======
                ST_GeomFromGeoJSON(:bbox_json)::geometry,
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
                :state,
                :grid_res_km,
                NOW() + INTERVAL '24 hours'
            )
        """),
        {
<<<<<<< HEAD
            "id":          analysis_id,
            "bbox_json":   bbox_geojson,
            "state":       request.state,
=======
            "id": analysis_id,
            "bbox_json": bbox_geojson,
            "state": request.state,
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
            "grid_res_km": request.grid_resolution_km,
        },
    )

<<<<<<< HEAD
    for cell in grid_cells:
=======
    # Batch insert location_scores — one row per grid cell
    for cell in grid_cells:
        cell_polygon_json = json.dumps(cell.location.cell_polygon)
        metrics_json = json.dumps(cell.metrics.model_dump())
        composite_detail_json = json.dumps(cell.composite_score.model_dump())

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        await db.execute(
            text("""
                INSERT INTO location_scores (
                    id, region_id, point, cell_polygon,
                    composite_score,
                    score_power, score_water, score_geological,
<<<<<<< HEAD
                    score_climate, score_connectivity, score_economic,
                    score_environmental, metrics, composite_detail
                ) VALUES (
                    gen_random_uuid(), :region_id,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326),
                    ST_GeomFromGeoJSON(:cell_polygon),
                    :composite,
                    :power, :water, :geological,
                    :climate, :connectivity, :economic, :environmental,
                    cast(:metrics as jsonb), cast(:composite_detail as jsonb)
                )
            """),
            {
                "region_id":       analysis_id,
                "lat":             cell.location.lat,
                "lng":             cell.location.lng,
                "cell_polygon":    json.dumps(cell.location.cell_polygon),
                "composite":       cell.composite_score.composite,
                "power":           cell.scores.get("power"),
                "water":           cell.scores.get("water"),
                "geological":      cell.scores.get("geological"),
                "climate":         cell.scores.get("climate"),
                "connectivity":    cell.scores.get("connectivity"),
                "economic":        cell.scores.get("economic"),
                "environmental":   cell.scores.get("environmental"),
                "metrics":         json.dumps(cell.metrics.model_dump()),
                "composite_detail":json.dumps(cell.composite_score.model_dump()),
=======
                    score_climate, score_connectivity, score_economic, score_environmental,
                    metrics, composite_detail
                ) VALUES (
                    gen_random_uuid(), :region_id,
                    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geometry,
                    ST_GeomFromGeoJSON(:cell_polygon)::geometry,
                    :composite,
                    :power, :water, :geological,
                    :climate, :connectivity, :economic, :environmental,
                    :metrics::jsonb, :composite_detail::jsonb
                )
            """),
            {
                "region_id": analysis_id,
                "lat": cell.location.lat,
                "lng": cell.location.lng,
                "cell_polygon": cell_polygon_json,
                "composite": cell.composite_score.composite,
                "power": cell.scores.get("power"),
                "water": cell.scores.get("water"),
                "geological": cell.scores.get("geological"),
                "climate": cell.scores.get("climate"),
                "connectivity": cell.scores.get("connectivity"),
                "economic": cell.scores.get("economic"),
                "environmental": cell.scores.get("environmental"),
                "metrics": metrics_json,
                "composite_detail": composite_detail_json,
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
            },
        )

    await db.commit()
<<<<<<< HEAD
    logger.info(f"Persisted {len(grid_cells)} cells for analysis {analysis_id}")


async def _build_and_cache_layers(
    db: AsyncSession,
    analysis_id: str,
    grid_cells: list,
) -> None:
    """Build all 8 GeoJSON layers and cache in integration_cache table."""
=======
    logger.info(f"Persisted analysis {analysis_id} with {len(grid_cells)} cells to DB")


async def _build_and_cache_layers(
    analysis_id: str,
    grid_cells: list,
    redis_client: Optional[aioredis.Redis],
) -> None:
    """Build all 8 GeoJSON layers and cache in Redis."""
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    from app.core.layers.power_layer import PowerLayerBuilder
    from app.core.layers.water_layer import WaterLayerBuilder
    from app.core.layers.geological_layer import GeologicalLayerBuilder
    from app.core.layers.climate_layer import ClimateLayerBuilder
    from app.core.layers.connectivity_layer import ConnectivityLayerBuilder
    from app.core.layers.economic_layer import EconomicLayerBuilder
    from app.core.layers.environmental_layer import EnvironmentalLayerBuilder
    from app.core.layers.optimal_layer import OptimalLayerBuilder

    builders = {
<<<<<<< HEAD
        "power":         PowerLayerBuilder(),
        "water":         WaterLayerBuilder(),
        "geological":    GeologicalLayerBuilder(),
        "climate":       ClimateLayerBuilder(),
        "connectivity":  ConnectivityLayerBuilder(),
        "economic":      EconomicLayerBuilder(),
        "environmental": EnvironmentalLayerBuilder(),
        "optimal":       OptimalLayerBuilder(),
    }

    expires = datetime.now(timezone.utc) + timedelta(hours=settings.CACHE_TTL_HOURS)

    for layer_id, builder in builders.items():
        try:
            geojson = builder.build(grid_cells)
            cache_key = f"layer:{layer_id}:{analysis_id}"
            await db.execute(
                text("""
                    INSERT INTO integration_cache (cache_key, data, expires_at)
                    VALUES (:key, :data, :expires)
                    ON CONFLICT (cache_key) DO UPDATE
                        SET data = EXCLUDED.data,
                            expires_at = EXCLUDED.expires_at
                """),
                {
                    "key":     cache_key,
                    "data":    json.dumps(geojson),
                    "expires": expires,
                },
            )
            logger.debug(f"Cached layer {layer_id} for analysis {analysis_id}")
        except Exception as e:
            logger.warning(f"Layer build/cache failed for '{layer_id}': {e}")

    await db.commit()
=======
        "power": PowerLayerBuilder(),
        "water": WaterLayerBuilder(),
        "geological": GeologicalLayerBuilder(),
        "climate": ClimateLayerBuilder(),
        "connectivity": ConnectivityLayerBuilder(),
        "economic": EconomicLayerBuilder(),
        "environmental": EnvironmentalLayerBuilder(),
        "optimal": OptimalLayerBuilder(),
    }

    for layer_id, builder in builders.items():
        try:
            geojson = builder.build(grid_cells)
            if redis_client:
                cache_key = f"layer:{layer_id}:{analysis_id}"
                await redis_client.setex(
                    cache_key,
                    settings.CACHE_TTL_HOURS * 3600,
                    json.dumps(geojson),
                )
                logger.debug(f"Cached layer {layer_id} for analysis {analysis_id}")
        except Exception as e:
            logger.warning(f"Layer build/cache failed for layer '{layer_id}': {e}")
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
