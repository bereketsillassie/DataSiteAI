"""
app/api/v1/layers.py
─────────────────────
GET /api/v1/layers — list available layers for an analysis
GET /api/v1/layers/{layer_id} — return GeoJSON for a specific layer

Layer build flow:
  1. Check Redis cache (key: layer:{layer_id}:{analysis_id})
  2. If miss, reload ScoreBundles from DB and rebuild the layer
  3. Cache rebuilt layer back to Redis
  4. Return GeoJSON FeatureCollection
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.dependencies import get_db, get_redis
from app.models.responses import LayersListResponse, LayerMetadata

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_LAYER_IDS = [
    "power",
    "water",
    "geological",
    "climate",
    "connectivity",
    "economic",
    "environmental",
    "optimal",
]

# Human-readable metadata for each layer — shown in GET /layers response
LAYER_METADATA = {
    "power": (
        "Power & Energy",
        "Scores based on grid proximity, electricity cost, and renewable energy percentage.",
    ),
    "water": (
        "Water & Flood Risk",
        "Scores based on FEMA flood zones, water body proximity, and drought risk.",
    ),
    "geological": (
        "Geological & Terrain",
        "Scores based on seismic hazard (USGS PGA), terrain slope, and soil stability.",
    ),
    "climate": (
        "Climate & Weather Risk",
        "Scores based on cooling degree days, humidity, tornado, hurricane, and hail risk.",
    ),
    "connectivity": (
        "Connectivity & Access",
        "Scores based on fiber optic density, internet exchange proximity, and highway access.",
    ),
    "economic": (
        "Economic Environment",
        "Scores based on state corporate taxes, land cost, labor availability, and permitting ease.",
    ),
    "environmental": (
        "Environmental Impact",
        "Scores based on population proximity, air quality, and protected land adjacency.",
    ),
    "optimal": (
        "Optimal Data Center Score",
        "Composite weighted score combining all 7 categories per weights.py configuration.",
    ),
}

# Module-to-class mapping for dynamic layer builder imports
_LAYER_BUILDER_MAP = {
    "power": ("app.core.layers.power_layer", "PowerLayerBuilder"),
    "water": ("app.core.layers.water_layer", "WaterLayerBuilder"),
    "geological": ("app.core.layers.geological_layer", "GeologicalLayerBuilder"),
    "climate": ("app.core.layers.climate_layer", "ClimateLayerBuilder"),
    "connectivity": ("app.core.layers.connectivity_layer", "ConnectivityLayerBuilder"),
    "economic": ("app.core.layers.economic_layer", "EconomicLayerBuilder"),
    "environmental": ("app.core.layers.environmental_layer", "EnvironmentalLayerBuilder"),
    "optimal": ("app.core.layers.optimal_layer", "OptimalLayerBuilder"),
}


@router.get(
    "/layers",
    response_model=LayersListResponse,
    summary="List available GeoJSON layers for an analysis",
    description="Returns metadata and URLs for all 8 available layers (7 category layers + 1 optimal composite).",
)
async def list_layers(
    analysis_id: str = Query(..., description="Analysis ID returned by POST /analyze"),
) -> LayersListResponse:
    return LayersListResponse(
        analysis_id=analysis_id,
        layers=[
            LayerMetadata(
                layer_id=lid,
                label=LAYER_METADATA[lid][0],
                description=LAYER_METADATA[lid][1],
                geojson_url=f"/api/v1/layers/{lid}?analysis_id={analysis_id}",
            )
            for lid in VALID_LAYER_IDS
        ],
    )


@router.get(
    "/layers/{layer_id}",
    summary="Get GeoJSON FeatureCollection for a specific layer",
    description=(
        f"Returns a GeoJSON FeatureCollection where each feature is a scored grid cell. "
        f"layer_id must be one of: {', '.join(VALID_LAYER_IDS)}. "
        "Checks Redis cache first, rebuilds from DB if not cached."
    ),
)
async def get_layer(
    layer_id: str,
    analysis_id: str = Query(..., description="Analysis ID returned by POST /analyze"),
    format: str = Query("geojson", description="Response format: geojson (default)"),
    db: AsyncSession = Depends(get_db),
    redis_client: Optional[aioredis.Redis] = Depends(get_redis),
) -> JSONResponse:
    if layer_id not in VALID_LAYER_IDS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown layer_id '{layer_id}'. Valid options: {VALID_LAYER_IDS}",
        )

    # ── 1. Check Redis cache ───────────────────────────────────────────────────
    if redis_client:
        try:
            cache_key = f"layer:{layer_id}:{analysis_id}"
            cached = await redis_client.get(cache_key)
            if cached:
                logger.debug(f"Redis cache hit for layer={layer_id} analysis={analysis_id}")
                return JSONResponse(content=json.loads(cached))
        except Exception as e:
            logger.warning(f"Redis layer cache read failed: {e}")

    # ── 2. Rebuild from database ───────────────────────────────────────────────
    try:
        geojson = await _rebuild_layer_from_db(db, analysis_id, layer_id)
    except Exception as e:
        logger.error(f"Layer rebuild failed for layer={layer_id} analysis={analysis_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Layer generation failed: {str(e)}")

    if geojson is None:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis '{analysis_id}' not found. Run POST /analyze first.",
        )

    # ── 3. Cache the rebuilt layer ─────────────────────────────────────────────
    if redis_client:
        try:
            from app.config import settings
            await redis_client.setex(
                f"layer:{layer_id}:{analysis_id}",
                settings.CACHE_TTL_HOURS * 3600,
                json.dumps(geojson),
            )
        except Exception as e:
            logger.warning(f"Redis layer cache write failed: {e}")

    return JSONResponse(content=geojson)


async def _rebuild_layer_from_db(
    db: AsyncSession,
    analysis_id: str,
    layer_id: str,
) -> Optional[dict]:
    """
    Load ScoreBundles from the location_scores table and rebuild the requested layer.
    Returns None if no rows found for analysis_id.
    """
    from sqlalchemy import text

    result = await db.execute(
        text("""
            SELECT
                ST_Y(point::geometry) as lat,
                ST_X(point::geometry) as lng,
                ST_AsGeoJSON(cell_polygon::geometry) as cell_polygon_json,
                composite_score,
                score_power, score_water, score_geological,
                score_climate, score_connectivity, score_economic, score_environmental,
                metrics, composite_detail
            FROM location_scores
            WHERE region_id = :analysis_id
            ORDER BY composite_score DESC
        """),
        {"analysis_id": analysis_id},
    )

    rows = result.mappings().all()
    if not rows:
        return None

    bundles = _rows_to_bundles(rows)
    if not bundles:
        return None

    # Dynamically import and instantiate the appropriate layer builder
    module_path, class_name = _LAYER_BUILDER_MAP[layer_id]
    import importlib
    module = importlib.import_module(module_path)
    builder_class = getattr(module, class_name)
    return builder_class().build(bundles)


def _rows_to_bundles(rows) -> list:
    """Reconstruct ScoreBundle objects from DB rows."""
    from app.models.responses import ScoreBundle, CompositeScore, LocationPoint
    from app.core.scoring.engine import ScoringEngine

    # Create a detached engine instance just for _build_metrics
    dummy_engine = ScoringEngine.__new__(ScoringEngine)

    bundles = []
    for row in rows:
        try:
            metrics_dict = row["metrics"] or {}
            composite_detail = row["composite_detail"] or {}
            cell_polygon_raw = row.get("cell_polygon_json")
            cell_polygon = (
                json.loads(cell_polygon_raw)
                if cell_polygon_raw
                else {"type": "Polygon", "coordinates": [[]]}
            )

            scores = {
                cat: float(row[f"score_{cat}"])
                for cat in ["power", "water", "geological", "climate", "connectivity", "economic", "environmental"]
                if row.get(f"score_{cat}") is not None
            }

            metrics = dummy_engine._build_metrics(metrics_dict)

            bundles.append(
                ScoreBundle(
                    location=LocationPoint(
                        lat=float(row["lat"]),
                        lng=float(row["lng"]),
                        cell_polygon=cell_polygon,
                    ),
                    composite_score=CompositeScore(
                        composite=float(row["composite_score"] or 0.0),
                        weighted_contributions=composite_detail.get("weighted_contributions", {}),
                        weights_used=composite_detail.get("weights_used", {}),
                    ),
                    scores=scores,
                    metrics=metrics,
                )
            )
        except Exception as e:
            logger.debug(f"Skipped DB row during bundle reconstruction: {e}")

    return bundles
