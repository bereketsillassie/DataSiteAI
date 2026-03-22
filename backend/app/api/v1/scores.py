"""
app/api/v1/scores.py
─────────────────────
<<<<<<< HEAD
GET /api/v1/scores — retrieve all scores for a completed analysis.
Reads from DB only — no re-processing.
=======
GET /api/v1/scores — retrieve all scores for a completed analysis from DB.
Lighter than POST /analyze — reads from cache or DB only, no re-processing.

Flow:
  1. Check Redis cache for the full scores payload
  2. If miss, load from location_scores table
  3. Reconstruct ScoreBundle objects
  4. Return ScoresResponse
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
"""

import json
import logging
<<<<<<< HEAD

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
=======
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.dependencies import get_db, get_redis
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
from app.models.responses import ScoresResponse, ScoreBundle, CompositeScore, LocationPoint

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/scores",
    response_model=ScoresResponse,
    summary="Retrieve all scores for a completed analysis",
<<<<<<< HEAD
)
async def get_scores(
    analysis_id: str = Query(..., description="Analysis ID from POST /analyze"),
    db: AsyncSession = Depends(get_db),
) -> ScoresResponse:
=======
    description=(
        "Reads scores from the database — no re-processing. "
        "Call POST /analyze first to create the analysis. "
        "Results are sorted by composite score descending."
    ),
)
async def get_scores(
    analysis_id: str = Query(..., description="Analysis ID returned by POST /analyze"),
    db: AsyncSession = Depends(get_db),
    redis_client: Optional[aioredis.Redis] = Depends(get_redis),
) -> ScoresResponse:
    # ── 1. Check Redis cache ───────────────────────────────────────────────────
    if redis_client:
        try:
            cache_key = f"scores:{analysis_id}"
            cached = await redis_client.get(cache_key)
            if cached:
                logger.debug(f"Redis cache hit for scores analysis={analysis_id}")
                data = json.loads(cached)
                return ScoresResponse(**data)
        except Exception as e:
            logger.warning(f"Redis scores cache read failed: {e}")

    # ── 2. Load from database ──────────────────────────────────────────────────
    from sqlalchemy import text
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e

    result = await db.execute(
        text("""
            SELECT
<<<<<<< HEAD
                ST_Y(point::geometry)            as lat,
                ST_X(point::geometry)            as lng,
                ST_AsGeoJSON(cell_polygon::geometry) as cell_polygon_json,
                composite_score,
                score_power, score_water, score_geological,
                score_climate, score_connectivity, score_economic,
                score_environmental, metrics, composite_detail
=======
                ST_Y(point::geometry) as lat,
                ST_X(point::geometry) as lng,
                ST_AsGeoJSON(cell_polygon::geometry) as cell_polygon_json,
                composite_score,
                score_power, score_water, score_geological,
                score_climate, score_connectivity, score_economic, score_environmental,
                metrics, composite_detail
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
            FROM location_scores
            WHERE region_id = :analysis_id
            ORDER BY composite_score DESC
        """),
        {"analysis_id": analysis_id},
    )
<<<<<<< HEAD
    rows = result.mappings().all()

=======

    rows = result.mappings().all()
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis '{analysis_id}' not found. Run POST /analyze first.",
        )

<<<<<<< HEAD
    from app.core.scoring.engine import ScoringEngine
=======
    # ── 3. Reconstruct ScoreBundle objects ─────────────────────────────────────
    from app.core.scoring.engine import ScoringEngine

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
    dummy_engine = ScoringEngine.__new__(ScoringEngine)
    bundles = []

    for row in rows:
        try:
<<<<<<< HEAD
=======
            metrics_dict = row["metrics"] or {}
            composite_detail = row["composite_detail"] or {}
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
            cell_polygon_raw = row.get("cell_polygon_json")
            cell_polygon = (
                json.loads(cell_polygon_raw)
                if cell_polygon_raw
                else {"type": "Polygon", "coordinates": [[]]}
            )
<<<<<<< HEAD
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
            logger.debug(f"Skipped malformed score row: {e}")

    return ScoresResponse(analysis_id=analysis_id, scores=bundles)
=======

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
            logger.debug(f"Skipped malformed score row during reconstruction: {e}")

    response = ScoresResponse(analysis_id=analysis_id, scores=bundles)

    # ── 4. Write back to Redis cache ───────────────────────────────────────────
    if redis_client:
        try:
            from app.config import settings
            await redis_client.setex(
                f"scores:{analysis_id}",
                settings.CACHE_TTL_HOURS * 3600,
                json.dumps(response.model_dump()),
            )
        except Exception as e:
            logger.warning(f"Redis scores cache write failed: {e}")

    return response
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
