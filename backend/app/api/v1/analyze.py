"""
app/api/v1/analyze.py
──────────────────────
POST /api/v1/analyze — the main analysis endpoint.

Flow:
  1. Validate request (bbox, state, grid resolution)
  2. Run ScoringEngine.score_region() -> list[ScoreBundle]
  3. Persist analysis_region and location_scores to DB
  4. Build all 8 GeoJSON layers -> cache in integration_cache table
  5. If include_listings: fetch land listings in bbox
  6. Return full AnalyzeResponse
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
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
    "power", "water", "geological", "climate",
    "connectivity", "economic", "environmental", "optimal",
]


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    summary="Analyze a geographic region for data center suitability",
)
async def analyze_region(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
) -> AnalyzeResponse:
    start_time = time.time()
    analysis_id = str(uuid.uuid4())

    logger.info(
        f"Starting analysis {analysis_id} for state={request.state} "
        f"bbox=({request.bbox.min_lat},{request.bbox.min_lng})-"
        f"({request.bbox.max_lat},{request.bbox.max_lng})"
    )

    from app.models.domain import BoundingBox
    bbox = BoundingBox(
        min_lat=request.bbox.min_lat,
        min_lng=request.bbox.min_lng,
        max_lat=request.bbox.max_lat,
        max_lng=request.bbox.max_lng,
    )

    # ── Score the region ───────────────────────────────────────────────────────
    engine = create_scoring_engine(db_session=db, settings=settings)
    try:
        grid_cells = await engine.score_region(
            bbox, grid_resolution_km=request.grid_resolution_km
        )
    except Exception as e:
        logger.error(f"Scoring engine failed for {analysis_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")

    if not grid_cells:
        raise HTTPException(
            status_code=422,
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
    listings = []
    listings_stale = False
    if request.include_listings:
        try:
            import math
            listing_service = ListingService(db_session=db, settings=settings)
            center_lat = (request.bbox.min_lat + request.bbox.max_lat) / 2
            center_lng = (request.bbox.min_lng + request.bbox.max_lng) / 2
            radius_km = math.sqrt(bbox.area_sq_km() / math.pi) * 1.2
            listings, listings_stale = await listing_service.get_listings_near(
                lat=center_lat,
                lng=center_lng,
                radius_km=radius_km,
                min_acres=request.min_acres,
                max_acres=request.max_acres,
                limit=50,
                score_bundles=grid_cells,
            )
            logger.info(f"Found {len(listings)} listings for analysis {analysis_id}")
        except Exception as e:
            logger.warning(f"Listing fetch failed (continuing): {e}")

    # ── Build response ─────────────────────────────────────────────────────────
    processing_time_ms = int((time.time() - start_time) * 1000)
    from app.core.scoring.weights import CATEGORY_WEIGHTS

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
        layer_urls={
            lid: f"/api/v1/layers/{lid}?analysis_id={analysis_id}"
            for lid in LAYER_IDS
        },
        metadata=AnalysisMetadata(
            grid_cells_analyzed=len(grid_cells),
            processing_time_ms=processing_time_ms,
            weights_used=dict(CATEGORY_WEIGHTS),
            data_freshness={
                "gee":     "2023-12-01",
                "osm":     datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "listings":datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "eia":     datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "noaa":    "2023-01-01",
                "census":  "2022-01-01",
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
    """Persist analysis region and all scored cells to the database."""
    bbox_geojson = json.dumps(bbox.to_geojson_polygon())

    await db.execute(
        text("""
            INSERT INTO analysis_regions (id, bbox, state, grid_res_km, cache_expires_at)
            VALUES (
                :id,
                ST_GeomFromGeoJSON(:bbox_json),
                :state,
                :grid_res_km,
                NOW() + INTERVAL '24 hours'
            )
        """),
        {
            "id":          analysis_id,
            "bbox_json":   bbox_geojson,
            "state":       request.state,
            "grid_res_km": request.grid_resolution_km,
        },
    )

    for cell in grid_cells:
        await db.execute(
            text("""
                INSERT INTO location_scores (
                    id, region_id, point, cell_polygon,
                    composite_score,
                    score_power, score_water, score_geological,
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
            },
        )

    await db.commit()
    logger.info(f"Persisted {len(grid_cells)} cells for analysis {analysis_id}")


async def _build_and_cache_layers(
    db: AsyncSession,
    analysis_id: str,
    grid_cells: list,
) -> None:
    """Build all 8 GeoJSON layers and cache in integration_cache table."""
    from app.core.layers.power_layer import PowerLayerBuilder
    from app.core.layers.water_layer import WaterLayerBuilder
    from app.core.layers.geological_layer import GeologicalLayerBuilder
    from app.core.layers.climate_layer import ClimateLayerBuilder
    from app.core.layers.connectivity_layer import ConnectivityLayerBuilder
    from app.core.layers.economic_layer import EconomicLayerBuilder
    from app.core.layers.environmental_layer import EnvironmentalLayerBuilder
    from app.core.layers.optimal_layer import OptimalLayerBuilder

    builders = {
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