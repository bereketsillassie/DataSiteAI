"""
app/core/scoring/climate.py
────────────────────────────
Climate scorer.

Formulas (from CLAUDE.md):
  cooling_efficiency: 1.0 - clamp((annual_cdd - 500) / 3500)  # 500=best, 4000=worst
  humidity:           1.0 - clamp((avg_rh_pct - 30) / 60)     # 30%=best, 90%=worst
  tornado_risk:       1.0 - clamp(tornado_events_per_100sqkm_30yr / 5.0)
  hurricane_risk:     1.0 - clamp(hurricane_proximity_score / 1.0)
  hail_risk:          1.0 - clamp(hail_events_per_100sqkm_30yr / 10.0)

Data sources: NOAA CDO (climate normals, storm events), NASA POWER (humidity, temperature)

NOTE: This scorer reads CLIMATE_SUB_WEIGHTS from weights.py to roll up its own
sub-metrics. It NEVER reads CATEGORY_WEIGHTS — that is the engine's job only.
"""

import logging

from app.core.scoring.base import BaseScorer
from app.core.scoring.weights import CLIMATE_SUB_WEIGHTS
from app.core.grid import generate_grid
from app.models.domain import BoundingBox, CellScore

logger = logging.getLogger(__name__)


class ClimateScorer(BaseScorer):
    """Scores locations on cooling requirements, humidity, and severe weather risk."""

    category_id = "climate"

    def __init__(self, redis_client=None, settings=None):
        from app.integrations.noaa import NOAAClient
        from app.integrations.nasa_power import NASAPowerClient
        from app.config import settings as default_settings

        self.settings = settings or default_settings
        self.noaa = NOAAClient(redis_client=redis_client, settings=self.settings)
        self.nasa = NASAPowerClient(redis_client=redis_client, settings=self.settings)

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """Score all grid cells in the bbox for climate factors."""
        grid_res = getattr(self.settings, 'GRID_RESOLUTION_DEFAULT_KM', 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

        # Determine state for storm events (NOAA provides state-level data)
        center_lat, center_lng = bbox.center()
        state = self._lat_lng_to_state(center_lat, center_lng)

        # Fetch state-level storm event statistics (bbox-level, not per-cell)
        try:
            storm_events = await self.noaa.get_storm_events(state)
        except Exception as e:
            logger.error(f"ClimateScorer: NOAA storm events fetch failed: {e}")
            # Conservative defaults — moderate risk
            storm_events = {
                "tornado_per_100sqkm": 0.8,
                "hurricane_proximity_score": 0.3,
                "hail_per_100sqkm": 1.2,
            }

        results = []
        for cell in grid:
            try:
                # Per-cell climate normals from NOAA CDO
                climate_normals = await self.noaa.get_climate_normals(cell.lat, cell.lng)
                # Per-cell humidity from NASA POWER
                nasa_data = await self.nasa.get_climate_data(cell.lat, cell.lng)
                cs = self._score_cell(cell, climate_normals, nasa_data, storm_events)
                results.append(cs)
            except Exception as e:
                logger.warning(f"ClimateScorer: cell ({cell.lat},{cell.lng}) failed: {e}")
                results.append(CellScore(lat=cell.lat, lng=cell.lng, error=str(e)))

        return results

    def _score_cell(
        self, cell, climate_normals: dict, nasa_data: dict, storm_events: dict
    ) -> CellScore:
        """Score a single grid cell for climate factors."""

        # Extract climate values with defaults for missing data
        cdd = climate_normals.get("annual_cdd", 1500.0)
        avg_temp_c = climate_normals.get("avg_annual_temp_c", 15.0)
        avg_summer_temp_c = climate_normals.get("avg_summer_temp_c", 26.0)
        humidity = nasa_data.get("avg_humidity_pct", 70.0)

        # cooling_efficiency: 1.0 - clamp((annual_cdd - 500) / 3500)
        # 500 CDD = best (cool climate, minimal A/C), 4000 CDD = worst (very hot climate)
        cooling_score = 1.0 - self._clamp((cdd - 500.0) / 3500.0)

        # humidity: 1.0 - clamp((avg_rh_pct - 30) / 60)
        # 30% RH = best (dry), 90% RH = worst (very humid — bad for servers)
        humidity_score = 1.0 - self._clamp((humidity - 30.0) / 60.0)

        # tornado_risk: 1.0 - clamp(tornado_events_per_100sqkm_30yr / 5.0)
        # 0 tornadoes = best, 5+ per 100 sq km over 30 years = worst
        tornado_score = 1.0 - self._clamp(
            storm_events.get("tornado_per_100sqkm", 0.5) / 5.0
        )

        # hurricane_risk: 1.0 - clamp(hurricane_proximity_score / 1.0)
        # 0.0 = inland/no risk, 1.0 = direct coastal exposure
        hurricane_score = 1.0 - self._clamp(
            storm_events.get("hurricane_proximity_score", 0.1) / 1.0
        )

        # hail_risk: 1.0 - clamp(hail_events_per_100sqkm_30yr / 10.0)
        # 0 events = best, 10+ per 100 sq km over 30 years = worst
        hail_score = 1.0 - self._clamp(
            storm_events.get("hail_per_100sqkm", 1.0) / 10.0
        )

        # Convert raw risk scores (0-1) to 0-100 index for human-readable metrics
        tornado_index = round((1.0 - tornado_score) * 100.0, 1)
        hurricane_index = round((1.0 - hurricane_score) * 100.0, 1)
        hail_index = round((1.0 - hail_score) * 100.0, 1)

        sub_scores = {
            "cooling_efficiency": round(cooling_score, 4),
            "humidity":           round(humidity_score, 4),
            "tornado_risk":       round(tornado_score, 4),
            "hurricane_risk":     round(hurricane_score, 4),
            "hail_risk":          round(hail_score, 4),
        }

        # Roll up sub-metrics using CLIMATE_SUB_WEIGHTS
        category_score = self._weighted_sum(sub_scores, CLIMATE_SUB_WEIGHTS)

        metrics = {
            "avg_annual_temp_c":          round(avg_temp_c, 1),
            "avg_summer_temp_c":          round(avg_summer_temp_c, 1),
            "avg_humidity_pct":           round(humidity, 1),
            "annual_cooling_degree_days": round(cdd, 0),
            "tornado_risk_index":         tornado_index,
            "hurricane_risk_index":       hurricane_index,
            "hail_risk_index":            hail_index,
        }

        return CellScore(
            lat=cell.lat,
            lng=cell.lng,
            raw_scores={self.category_id: round(category_score, 4)},
            sub_scores=sub_scores,
            metrics=metrics,
        )

    def _lat_lng_to_state(self, lat: float, lng: float) -> str:
        """
        Very rough state determination from lat/lng for NOAA state-level queries.
        In production, this would use a proper point-in-polygon check.
        """
        if 33.8 <= lat <= 36.6 and -84.3 <= lng <= -75.5:
            return "NC"
        if 37.0 <= lat <= 39.5 and -83.7 <= lng <= -75.2:
            return "VA"
        if 25.8 <= lat <= 36.5 and -106.7 <= lng <= -93.5:
            return "TX"
        if 30.4 <= lat <= 35.0 and -85.6 <= lng <= -80.8:
            return "GA"
        if 34.9 <= lat <= 36.7 and -90.3 <= lng <= -81.6:
            return "TN"
        if 36.9 <= lat <= 41.0 and -109.1 <= lng <= -102.0:
            return "CO"
        if 31.3 <= lat <= 37.0 and -114.8 <= lng <= -109.0:
            return "AZ"
        return "NC"  # Default fallback
