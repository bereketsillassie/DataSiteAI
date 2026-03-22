"""
app/api/v1/scores.py
─────────────────────
GET /api/v1/scores — retrieve all scores for a completed analysis.
Reads from DB only — no re-processing.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.responses import ScoresResponse, ScoreBundle, CompositeScore, LocationPoint

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/scores",
    response_model=ScoresResponse,
    summary="Retrieve all scores for a completed analysis",
)
async def get_scores(
    analysis_id: str = Query(..., description="Analysis ID from POST /analyze"),
    db: AsyncSession = Depends(get_db),
) -> ScoresResponse:

    result = await db.execute(
        text("""
            SELECT
                ST_Y(point::geometry)            as lat,
                ST_X(point::geometry)            as lng,
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
        raise HTTPException(
            status_code=404,
            detail=f"Analysis '{analysis_id}' not found. Run POST /analyze first.",
        )

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
            logger.debug(f"Skipped malformed score row: {e}")

    return ScoresResponse(analysis_id=analysis_id, scores=bundles)
