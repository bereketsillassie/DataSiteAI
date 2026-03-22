"""
app/core/scoring/power.py
──────────────────────────
Power & Energy scorer.

Formulas (from CLAUDE.md):
  grid_proximity:   1.0 - clamp(min(dist_substation_km, dist_line_km) / 20.0)
  electricity_cost: 1.0 - clamp((rate_cents - 5.0) / 15.0)   # 5c=best, 20c=worst
  renewable_pct:    renewable_pct / 100.0
  grid_reliability: reliability_index / 100.0

Data sources: OSM (power infrastructure), EIA (rates, reliability)

BATCHING:
  - osm.get_region_data(bbox) fetches ALL OSM features in one Overpass call
  - EIA calls are state-level and cached — one call per state, not per cell

NOTE: This scorer reads POWER_SUB_WEIGHTS from weights.py to roll up its own
sub-metrics. It NEVER reads CATEGORY_WEIGHTS — that is the engine's job only.
"""

import logging
import math

from app.core.scoring.base import BaseScorer
from app.core.scoring.weights import POWER_SUB_WEIGHTS
from app.core.grid import generate_grid
from app.models.domain import BoundingBox, CellScore

logger = logging.getLogger(__name__)


class PowerScorer(BaseScorer):
    """Scores locations on power grid quality, electricity cost, and reliability."""

    category_id = "power"

<<<<<<< HEAD
    def __init__(self, db_session=None, settings=None):
=======
    def __init__(self, redis_client=None, settings=None):
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        from app.integrations.osm import OSMClient
        from app.integrations.eia import EIAClient
        from app.config import settings as default_settings

        self.settings = settings or default_settings
<<<<<<< HEAD
        self.osm = OSMClient(db_session=db_session, settings=self.settings)
        self.eia = EIAClient(db_session=db_session, settings=self.settings)
=======
        self.osm = OSMClient(redis_client=redis_client, settings=self.settings)
        self.eia = EIAClient(redis_client=redis_client, settings=self.settings)
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """Score all grid cells in the bbox for power infrastructure."""
        grid_res = getattr(self.settings, "GRID_RESOLUTION_DEFAULT_KM", 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

        center_lat, center_lng = bbox.center()
        state = self._lat_lng_to_state(center_lat, center_lng)

        # ── ONE Overpass call fetches all OSM features for the region ─────────
        try:
            osm_data = await self.osm.get_region_data(bbox)
            substations = osm_data.get("substations", [])
            power_lines = osm_data.get("power_lines", [])
        except Exception as e:
            logger.error(f"PowerScorer: OSM fetch failed: {e}")
            substations = []
            power_lines = []

        # ── State-level EIA calls — cached, one per state not per cell ────────
        try:
            electricity_rate = await self.eia.get_retail_electricity_rate(state)
            renewable_pct    = await self.eia.get_renewable_pct(state)
            reliability      = await self.eia.get_reliability_index(state)
            utility_territories = await self.eia.get_utility_territories(bbox)
        except Exception as e:
            logger.error(f"PowerScorer: EIA fetch failed: {e}")
            electricity_rate = 9.5
            renewable_pct    = 15.0
            reliability      = 70.0
            utility_territories = []

        # Precompute geometry lookups once — reused for every cell
        substation_coords = self._extract_points(substations)
        line_coords       = self._extract_line_midpoints(power_lines)
        utility_name      = (
            utility_territories[0].get("properties", {}).get("utility_name", "Unknown")
            if utility_territories else "Unknown"
        )

        # ── Score each cell (pure math, no API calls) ─────────────────────────
        results = []
        for cell in grid:
            try:
                cs = self._score_cell(
                    cell, substation_coords, line_coords,
                    electricity_rate, renewable_pct, reliability, utility_name,
                )
                results.append(cs)
            except Exception as e:
                logger.warning(f"PowerScorer: cell ({cell.lat},{cell.lng}) failed: {e}")
                results.append(CellScore(lat=cell.lat, lng=cell.lng, error=str(e)))

        return results

    def _score_cell(
        self,
        cell,
        substation_coords,
        line_coords,
        electricity_rate,
        renewable_pct,
        reliability,
        utility_name,
    ) -> CellScore:
        """Score a single grid cell for power infrastructure."""

        dist_substation = self._nearest_point_km(cell.lat, cell.lng, substation_coords)
        dist_line       = self._nearest_point_km(cell.lat, cell.lng, line_coords)
        best_dist       = min(dist_substation, dist_line)

        # grid_proximity: 1.0 - clamp(min(dist_substation, dist_line) / 20.0)
        grid_proximity_score  = 1.0 - self._clamp(best_dist / 20.0)
        # electricity_cost: 1.0 - clamp((rate - 5.0) / 15.0)  5c=best, 20c=worst
        electricity_cost_score = 1.0 - self._clamp((electricity_rate - 5.0) / 15.0)
        # renewable_pct: pct / 100.0
        renewable_score       = self._clamp(renewable_pct / 100.0)
        # grid_reliability: index / 100.0
        reliability_score     = self._clamp(reliability / 100.0)

        sub_scores = {
            "grid_proximity":   round(grid_proximity_score,   4),
            "electricity_cost": round(electricity_cost_score, 4),
            "renewable_pct":    round(renewable_score,        4),
            "grid_reliability": round(reliability_score,      4),
        }

        category_score = self._weighted_sum(sub_scores, POWER_SUB_WEIGHTS)

        metrics = {
            "nearest_transmission_line_km":  round(dist_line, 2),
            "nearest_substation_km":         round(dist_substation, 2),
            "electricity_rate_cents_per_kwh": electricity_rate,
            "renewable_energy_pct":          renewable_pct,
            "grid_reliability_index":        reliability,
            "utility_territory":             utility_name,
        }

        return CellScore(
            lat=cell.lat,
            lng=cell.lng,
            raw_scores={self.category_id: round(category_score, 4)},
            sub_scores=sub_scores,
            metrics=metrics,
        )

    def _lat_lng_to_state(self, lat: float, lng: float) -> str:
        if 33.8 <= lat <= 36.6 and -84.3 <= lng <= -75.5:  return "NC"
        if 37.0 <= lat <= 39.5 and -83.7 <= lng <= -75.2:  return "VA"
        if 25.8 <= lat <= 36.5 and -106.7 <= lng <= -93.5: return "TX"
        if 30.4 <= lat <= 35.0 and -85.6 <= lng <= -80.8:  return "GA"
        if 34.9 <= lat <= 36.7 and -90.3 <= lng <= -81.6:  return "TN"
        if 36.9 <= lat <= 41.0 and -109.1 <= lng <= -102.0:return "CO"
        if 31.3 <= lat <= 37.0 and -114.8 <= lng <= -109.0:return "AZ"
        if 24.5 <= lat <= 31.0 and -87.6 <= lng <= -80.0:  return "FL"
        return "NC"

    def _extract_points(self, features: list) -> list[tuple[float, float]]:
        coords = []
        for feat in features:
            geom = feat.get("geometry", {})
            if geom.get("type") == "Point":
                c = geom["coordinates"]
                coords.append((c[1], c[0]))  # GeoJSON [lng, lat] -> (lat, lng)
        return coords

    def _extract_line_midpoints(self, features: list) -> list[tuple[float, float]]:
        coords = []
        for feat in features:
            geom = feat.get("geometry", {})
            if geom.get("type") == "LineString":
                pts = geom["coordinates"]
                if pts:
                    mid = pts[len(pts) // 2]
                    coords.append((mid[1], mid[0]))
        return coords

    def _nearest_point_km(self, lat: float, lng: float, points: list) -> float:
        if not points:
            return 999.0
        return min(self._haversine_km(lat, lng, plat, plng) for plat, plng in points)

    def _haversine_km(self, lat1, lng1, lat2, lng2) -> float:
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlng / 2) ** 2
        )
        return R * 2 * math.asin(math.sqrt(a))