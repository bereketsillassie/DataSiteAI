"""
app/core/scoring/geological.py
───────────────────────────────
Geological scorer.

Formulas (from CLAUDE.md):
  seismic_hazard:   1.0 - clamp(pga_g / 2.0)
  terrain_slope:    1.0 - clamp(slope_degrees / 15.0)
  soil_stability:   high→1.0, moderate→0.6, low→0.2, unknown→0.5
  hazard_proximity: clamp(min(wetland_km, superfund_km) / 5.0)

Data sources: USGS (seismic + elevation), GEE (land cover), EPA (Superfund + NWI wetlands)

BATCHING — all external calls are region-level, not per-cell:
  usgs.get_seismic_hazard_for_region(bbox) — 1 USGS call  (was 99 calls)
  usgs.get_elevation_slope(bbox)           — 1 USGS call  (5 sample points)
  epa.get_superfund_sites(bbox)            — 1 EPA call
  epa.get_wetlands(bbox)                   — 1 NWI call
  gee.get_land_cover(bbox)                 — 1 GEE call (non-fatal if key missing)

Per-cell work is pure geometry math — zero additional API calls.

NOTE: This scorer reads GEOLOGICAL_SUB_WEIGHTS from weights.py only.
It NEVER reads CATEGORY_WEIGHTS — that is the engine's job.
"""

import logging
import math

from app.core.scoring.base import BaseScorer
from app.core.scoring.weights import GEOLOGICAL_SUB_WEIGHTS
from app.core.grid import generate_grid
from app.models.domain import BoundingBox, CellScore

logger = logging.getLogger(__name__)

SOIL_STABILITY_SCORES: dict[str, float] = {
    "high":     1.0,
    "moderate": 0.6,
    "low":      0.2,
    "unknown":  0.5,
}

# NLCD classes → stable buildable land
STABLE_LAND_COVERS    = {21, 22, 23, 24, 31, 52, 71, 81, 82}
# NLCD classes → wetland / water / unstable
UNSTABLE_LAND_COVERS  = {11, 90, 95}


class GeologicalScorer(BaseScorer):
    """Scores locations on seismic risk, terrain, soil stability, and hazard proximity."""

    category_id = "geological"

    def __init__(self, db_session=None, settings=None):
        from app.integrations.usgs import USGSClient
        from app.integrations.gee import GEEClient
        from app.integrations.epa import EPAClient
        from app.config import settings as default_settings

        self.settings = settings or default_settings
        self.usgs = USGSClient(db_session=db_session, settings=self.settings)
        self.gee  = GEEClient(db_session=db_session, settings=self.settings)
        self.epa  = EPAClient(db_session=db_session, settings=self.settings)

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """
        Score all grid cells for geological suitability.

        All 5 data fetches happen ONCE at region level before the cell loop.
        Per-cell scoring is pure geometry math — no additional API calls.
        """
        grid_res = getattr(self.settings, "GRID_RESOLUTION_DEFAULT_KM", 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

        # ── Region-level fetches (5 calls total regardless of grid size) ──────

        # 1. Seismic hazard — region center represents the whole bbox
        try:
            region_pga = await self.usgs.get_seismic_hazard_for_region(bbox)
        except Exception as e:
            logger.error(f"GeologicalScorer: USGS seismic fetch failed: {e}")
            region_pga = 0.1  # safe default for NC

        # 2. Elevation/slope — 5 sample points, center used as fallback
        try:
            elevation_data = await self.usgs.get_elevation_slope(bbox)
        except Exception as e:
            logger.error(f"GeologicalScorer: USGS elevation fetch failed: {e}")
            elevation_data = {"center": {"elevation_m": 100.0}, "points": []}

        center_elevation = elevation_data.get("center", {}).get("elevation_m", 100.0)
        # Build point lookup for cells that match a sample point exactly
        elevation_points = {
            (round(p["lat"], 3), round(p["lng"], 3)): p
            for p in elevation_data.get("points", [])
        }

        # 3. EPA Superfund sites
        try:
            superfund_sites = await self.epa.get_superfund_sites(bbox)
        except Exception as e:
            logger.error(f"GeologicalScorer: EPA Superfund fetch failed: {e}")
            superfund_sites = []

        # 4. NWI Wetlands
        try:
            wetlands = await self.epa.get_wetlands(bbox)
        except Exception as e:
            logger.error(f"GeologicalScorer: NWI wetlands fetch failed: {e}")
            wetlands = []

        # 5. GEE land cover — non-fatal, degrades to "unknown" soil quality
        try:
            land_cover_data = await self.gee.get_land_cover(bbox)
        except Exception as e:
            logger.warning(f"GeologicalScorer: GEE land cover unavailable (non-fatal): {e}")
            land_cover_data = {"grid": []}

        # Precompute geometry lookups used in cell loop
        superfund_coords = self._extract_point_coords(superfund_sites)
        wetland_coords   = self._extract_polygon_centroids(wetlands)
        land_cover_map   = self._build_land_cover_map(land_cover_data)

        # Estimate a single slope value for the region from elevation corner points
        region_slope = self._estimate_region_slope(elevation_data)

        # ── Per-cell scoring — pure math, zero API calls ───────────────────────
        results = []
        for cell in grid:
            try:
                elev_key   = (round(cell.lat, 3), round(cell.lng, 3))
                cell_elev  = elevation_points.get(elev_key, {})
                elevation  = cell_elev.get("elevation_m", center_elevation)
                land_class = land_cover_map.get(elev_key, 82)
                soil_quality = self._land_cover_to_soil_quality(land_class)

                cs = self._score_cell(
                    cell, region_pga, region_slope, elevation, soil_quality,
                    superfund_coords, wetland_coords,
                )
                results.append(cs)
            except Exception as e:
                logger.warning(f"GeologicalScorer: cell ({cell.lat},{cell.lng}) failed: {e}")
                results.append(CellScore(lat=cell.lat, lng=cell.lng, error=str(e)))

        return results

    def _estimate_region_slope(self, elevation_data: dict) -> float:
        """
        Estimate average slope from the 5 sample elevation points.
        Uses max elevation difference / approximate distance as a proxy.
        Falls back to 2.0° (flat) if insufficient data.
        """
        points = elevation_data.get("points", [])
        if len(points) < 2:
            return 2.0
        elevations = [p.get("elevation_m", 100.0) for p in points]
        elev_range = max(elevations) - min(elevations)
        # Approximate horizontal distance across the sample area (~20km diagonal)
        slope_degrees = math.degrees(math.atan(elev_range / 20000.0))
        return round(max(0.5, min(slope_degrees, 30.0)), 2)

    def _score_cell(
        self, cell, pga, slope, elevation, soil_quality,
        superfund_coords, wetland_coords,
    ) -> CellScore:
        """Score a single grid cell using pre-fetched region data."""

        # seismic_hazard: 1.0 - clamp(pga_g / 2.0)
        seismic_score = 1.0 - self._clamp(pga / 2.0)

        # terrain_slope: 1.0 - clamp(slope_degrees / 15.0)
        slope_score = 1.0 - self._clamp(slope / 15.0)

        # soil_stability lookup
        soil_score = SOIL_STABILITY_SCORES.get(soil_quality, SOIL_STABILITY_SCORES["unknown"])

        # hazard_proximity: clamp(min(wetland_km, superfund_km) / 5.0)
        wetland_km    = self._nearest_distance_km(cell.lat, cell.lng, wetland_coords)
        superfund_km  = self._nearest_distance_km(cell.lat, cell.lng, superfund_coords)
        hazard_km     = min(wetland_km, superfund_km)
        hazard_score  = self._clamp(hazard_km / 5.0)

        sub_scores = {
            "seismic_hazard":   round(seismic_score, 4),
            "terrain_slope":    round(slope_score,   4),
            "soil_stability":   round(soil_score,    4),
            "hazard_proximity": round(hazard_score,  4),
        }

        category_score = self._weighted_sum(sub_scores, GEOLOGICAL_SUB_WEIGHTS)

        metrics = {
            "seismic_hazard_pga":    round(pga, 4),
            "slope_degrees":         round(slope, 2),
            "elevation_m":           round(elevation, 1),
            "soil_bearing_capacity": soil_quality,
            "nearest_wetland_km":    round(wetland_km    if wetland_km    < 999 else 10.0, 2),
            "nearest_superfund_km":  round(superfund_km  if superfund_km  < 999 else 15.0, 2),
        }

        return CellScore(
            lat=cell.lat,
            lng=cell.lng,
            raw_scores={self.category_id: round(category_score, 4)},
            sub_scores=sub_scores,
            metrics=metrics,
        )

    def _land_cover_to_soil_quality(self, land_class: int) -> str:
        if land_class in UNSTABLE_LAND_COVERS:
            return "low"
        if land_class in STABLE_LAND_COVERS or land_class in (41, 42, 43):
            return "moderate"
        return "unknown"

    def _extract_point_coords(self, features: list) -> list[tuple[float, float]]:
        coords = []
        for f in features:
            geom = f.get("geometry") or {}
            if geom.get("type") == "Point":
                c = geom.get("coordinates") or []
                if len(c) >= 2:
                    coords.append((c[1], c[0]))
        return coords

    def _extract_polygon_centroids(self, features: list) -> list[tuple[float, float]]:
        coords = []
        for f in features:
            geom = f.get("geometry") or {}
            ring = None
            if geom.get("type") == "Polygon":
                rings = geom.get("coordinates") or []
                ring  = rings[0] if rings else None
            elif geom.get("type") == "MultiPolygon":
                polys = geom.get("coordinates") or []
                ring  = polys[0][0] if polys and polys[0] else None
            if ring:
                avg_lat = sum(c[1] for c in ring) / len(ring)
                avg_lng = sum(c[0] for c in ring) / len(ring)
                coords.append((avg_lat, avg_lng))
        return coords

    def _build_land_cover_map(self, land_cover: dict) -> dict:
        return {
            (round(p["lat"], 3), round(p["lng"], 3)): p.get("class", 82)
            for p in land_cover.get("grid", [])
        }

    def _nearest_distance_km(self, lat: float, lng: float, points: list) -> float:
        if not points:
            return 999.0
        return min(self._haversine_km(lat, lng, p[0], p[1]) for p in points)

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
