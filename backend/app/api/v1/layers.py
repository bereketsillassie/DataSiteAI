"""
app/api/v1/layers.py
─────────────────────
GET /api/v1/layers                — list available layers for an analysis
GET /api/v1/layers/{layer_id}     — return GeoJSON for a specific layer

Cache flow:
  1. Check integration_cache table (key: layer:{layer_id}:{analysis_id})
  2. On miss, reload ScoreBundles from location_scores and rebuild
  3. Write rebuilt layer back to integration_cache
  4. Return GeoJSON FeatureCollection
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.responses import LayersListResponse, LayerMetadata

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_LAYER_IDS = [
    "power", "water", "geological", "climate",
    "connectivity", "economic", "environmental", "optimal",
]

LAYER_METADATA = {
    "power":         ("Power & Energy",           "Grid proximity, electricity cost, renewable energy."),
    "water":         ("Water & Flood Risk",        "FEMA flood zones, water proximity, drought risk."),
    "geological":    ("Geological & Terrain",      "Seismic hazard, slope, soil stability."),
    "climate":       ("Climate & Weather Risk",    "Cooling degree days, humidity, storm risk."),
    "connectivity":  ("Connectivity & Access",     "Fiber density, IXP proximity, highway access."),
    "economic":      ("Economic Environment",      "Tax environment, land cost, labor market."),
    "environmental": ("Environmental Impact",      "Population proximity, air quality, protected land."),
    "optimal":       ("Optimal Composite Score",   "Weighted composite of all 7 categories."),
}

_LAYER_BUILDER_MAP = {
    "power":         ("app.core.layers.power_layer",         "PowerLayerBuilder"),
    "water":         ("app.core.layers.water_layer",         "WaterLayerBuilder"),
    "geological":    ("app.core.layers.geological_layer",    "GeologicalLayerBuilder"),
    "climate":       ("app.core.layers.climate_layer",       "ClimateLayerBuilder"),
    "connectivity":  ("app.core.layers.connectivity_layer",  "ConnectivityLayerBuilder"),
    "economic":      ("app.core.layers.economic_layer",      "EconomicLayerBuilder"),
    "environmental": ("app.core.layers.environmental_layer", "EnvironmentalLayerBuilder"),
    "optimal":       ("app.core.layers.optimal_layer",       "OptimalLayerBuilder"),
}


@router.get("/layers", response_model=LayersListResponse)
async def list_layers(
    analysis_id: str = Query(..., description="Analysis ID from POST /analyze"),
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


@router.get("/layers/{layer_id}")
async def get_layer(
    layer_id: str,
    analysis_id: str = Query(..., description="Analysis ID from POST /analyze"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    if layer_id not in VALID_LAYER_IDS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown layer_id '{layer_id}'. Valid: {VALID_LAYER_IDS}",
        )

    # ── 1. Check DB cache ──────────────────────────────────────────────────────
    cache_key = f"layer:{layer_id}:{analysis_id}"
    try:
        cached_result = await db.execute(
            text(
                "SELECT data FROM integration_cache "
                "WHERE cache_key = :key AND expires_at > NOW()"
            ),
            {"key": cache_key},
        )
        row = cached_result.fetchone()
        if row:
            logger.debug(f"DB cache hit for layer={layer_id} analysis={analysis_id}")
            return JSONResponse(content=row[0])
    except Exception as e:
        logger.warning(f"Layer cache read failed: {e}")

    # ── 2. Rebuild from location_scores ───────────────────────────────────────
    try:
        geojson = await _rebuild_layer_from_db(db, analysis_id, layer_id)
    except Exception as e:
        logger.error(f"Layer rebuild failed layer={layer_id} analysis={analysis_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Layer generation failed: {str(e)}")

    if geojson is None:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis '{analysis_id}' not found. Run POST /analyze first.",
        )

    # ── 3. Write back to cache ─────────────────────────────────────────────────
    try:
        expires = datetime.now(timezone.utc) + timedelta(hours=settings.CACHE_TTL_HOURS)
        await db.execute(
            text("""
                INSERT INTO integration_cache (cache_key, data, expires_at)
                VALUES (:key, :data, :expires)
                ON CONFLICT (cache_key) DO UPDATE
                    SET data = EXCLUDED.data,
                        expires_at = EXCLUDED.expires_at
            """),
            {"key": cache_key, "data": json.dumps(geojson), "expires": expires},
        )
        await db.commit()
    except Exception as e:
        logger.warning(f"Layer cache write failed: {e}")

    return JSONResponse(content=geojson)


async def _rebuild_layer_from_db(
    db: AsyncSession,
    analysis_id: str,
    layer_id: str,
) -> Optional[dict]:
    """Load ScoreBundles from DB and rebuild the requested GeoJSON layer."""
    result = await db.execute(
        text("""
            SELECT
                ST_Y(point::geometry)                as lat,
                ST_X(point::geometry)                as lng,
                ST_AsGeoJSON(cell_polygon::geometry) as cell_polygon_json,
                composite_score,
                score_power, score_water, score_geological,
                score_climate, score_connectivity, score_economic,
                score_environmental, metrics, composite_detail
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

    import importlib
    module_path, class_name = _LAYER_BUILDER_MAP[layer_id]
    module = importlib.import_module(module_path)
    return getattr(module, class_name)().build(bundles)


def _rows_to_bundles(rows) -> list:
    """Reconstruct ScoreBundle objects from DB rows."""
    from app.models.responses import ScoreBundle, CompositeScore, LocationPoint
    from app.core.scoring.engine import ScoringEngine

    dummy_engine = ScoringEngine.__new__(ScoringEngine)
    bundles = []

    for row in rows:
        try:
            cell_polygon_raw = row.get("cell_polygon_json")
            cell_polygon = (
                json.loads(cell_polygon_raw)
                if cell_polygon_raw
                else {"type": "Polygon", "coordinates": [[]]}
            )
            scores = {
                cat: float(row[f"score_{cat}"])
                for cat in [
                    "power", "water", "geological", "climate",
                    "connectivity", "economic", "environmental",
                ]
                if row.get(f"score_{cat}") is not None
            }
            composite_detail = row["composite_detail"] or {}
            bundles.append(ScoreBundle(
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
                metrics=dummy_engine._build_metrics(row["metrics"] or {}),
            ))
        except Exception as e:
            logger.debug(f"Skipped malformed DB row: {e}")

    return bundles
