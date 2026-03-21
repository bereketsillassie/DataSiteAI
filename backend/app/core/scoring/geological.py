"""
app/core/scoring/geological.py
───────────────────────────────
Geological scorer.

Formulas (from CLAUDE.md):
  seismic_hazard:   1.0 - clamp(pga_g / 2.0)
  terrain_slope:    1.0 - clamp(slope_degrees / 15.0)
  soil_stability:   high→1.0, moderate→0.6, low→0.2, unknown→0.5
  hazard_proximity: clamp(min(wetland_km, superfund_km) / 5.0)

Data sources: USGS (seismic hazard + elevation/slope), GEE (land cover for soil proxy),
              EPA (Superfund sites), EPA/USFWS NWI (wetlands)

NOTE: This scorer reads GEOLOGICAL_SUB_WEIGHTS from weights.py to roll up its own
sub-metrics. It NEVER reads CATEGORY_WEIGHTS — that is the engine's job only.
"""

import logging
import math

from app.core.scoring.base import BaseScorer
from app.core.scoring.weights import GEOLOGICAL_SUB_WEIGHTS
from app.core.grid import generate_grid
from app.models.domain import BoundingBox, CellScore

logger = logging.getLogger(__name__)

# Soil stability score lookup — derived from NLCD land cover class and soil type
# In production, this would use USDA SSURGO soil survey data
SOIL_STABILITY_SCORES: dict[str, float] = {
    "high":    1.0,   # Dense clay, consolidated rock — excellent bearing capacity
    "moderate": 0.6,  # Mixed soils — adequate for most construction
    "low":     0.2,   # Sandy, expansive, or organic soils — poor bearing capacity
    "unknown": 0.5,   # No data available — use neutral score
}

# NLCD classes that typically correspond to stable, buildable soils
# Classes 21-24 (developed), 31 (barren), 52 (shrub), 71 (grassland), 81-82 (agriculture)
STABLE_LAND_COVERS = {21, 22, 23, 24, 31, 52, 71, 81, 82}

# NLCD classes that indicate unstable or restricted soils
# Classes 11 (water), 90 (woody wetlands), 95 (emergent wetlands)
UNSTABLE_LAND_COVERS = {11, 90, 95}


class GeologicalScorer(BaseScorer):
    """Scores locations on seismic risk, terrain slope, soil stability, and hazard proximity."""

    category_id = "geological"

    def __init__(self, redis_client=None, settings=None):
        from app.integrations.usgs import USGSClient
        from app.integrations.gee import GEEClient
        from app.integrations.epa import EPAClient
        from app.config import settings as default_settings

        self.settings = settings or default_settings
        self.usgs = USGSClient(redis_client=redis_client, settings=self.settings)
        self.gee = GEEClient(redis_client=redis_client, settings=self.settings)
        self.epa = EPAClient(redis_client=redis_client, settings=self.settings)

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """Score all grid cells in the bbox for geological suitability."""
        grid_res = getattr(self.settings, 'GRID_RESOLUTION_DEFAULT_KM', 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

        # Fetch bbox-level data (not per-cell, for efficiency)
        try:
            elevation_data = await self.usgs.get_elevation_slope(bbox)
        except Exception as e:
            logger.error(f"GeologicalScorer: USGS elevation/slope fetch failed: {e}")
            elevation_data = {
                "center": {"elevation_m": 100.0, "slope_degrees": 2.0},
                "points": [],
            }

        try:
            superfund_sites = await self.epa.get_superfund_sites(bbox)
        except Exception as e:
            logger.error(f"GeologicalScorer: EPA Superfund fetch failed: {e}")
            superfund_sites = []

        try:
            wetlands = await self.epa.get_wetlands(bbox)
        except Exception as e:
            logger.error(f"GeologicalScorer: NWI wetlands fetch failed: {e}")
            wetlands = []

        try:
            land_cover_data = await self.gee.get_land_cover(bbox)
        except Exception as e:
            logger.warning(f"GeologicalScorer: GEE land cover fetch failed (non-fatal): {e}")
            land_cover_data = {"grid": []}

        # Extract elevation/slope for the bbox center (used for cells without individual data)
        center_data = elevation_data.get("center", {})
        center_slope = center_data.get("slope_degrees", 2.0)
        center_elevation = center_data.get("elevation_m", 100.0)

        # Build per-point lookup from elevation data if available
        elevation_points = {
            (round(p["lat"], 3), round(p["lng"], 3)): p
            for p in elevation_data.get("points", [])
        }

        # Precompute hazard coordinates for distance calculations
        superfund_coords = self._extract_point_coords(superfund_sites)
        wetland_coords = self._extract_polygon_centroids(wetlands)

        # Build land cover map for soil stability estimation
        land_cover_map = self._build_land_cover_map(land_cover_data)

        results = []
        for cell in grid:
            try:
                # Get seismic hazard per cell (USGS provides point-specific values)
                pga = await self.usgs.get_seismic_hazard(cell.lat, cell.lng)

                # Get slope for this cell (from elevation data or center fallback)
                elev_key = (round(cell.lat, 3), round(cell.lng, 3))
                cell_elev_data = elevation_points.get(elev_key, {})
                slope = cell_elev_data.get("slope_degrees", center_slope)
                elevation = cell_elev_data.get("elevation_m", center_elevation)

                # Estimate soil stability from land cover class
                land_class = land_cover_map.get(elev_key, 82)  # Default: Cultivated Crops
                soil_quality = self._land_cover_to_soil_quality(land_class)

                cs = self._score_cell(
                    cell, pga, slope, elevation, soil_quality,
                    superfund_coords, wetland_coords
                )
                results.append(cs)
            except Exception as e:
                logger.warning(f"GeologicalScorer: cell ({cell.lat},{cell.lng}) failed: {e}")
                results.append(CellScore(lat=cell.lat, lng=cell.lng, error=str(e)))

        return results

    def _score_cell(
        self, cell, pga, slope, elevation, soil_quality,
        superfund_coords, wetland_coords
    ) -> CellScore:
        """Score a single grid cell for geological factors."""

        # seismic_hazard: 1.0 - clamp(pga_g / 2.0)
        seismic_score = 1.0 - self._clamp(pga / 2.0)

        # terrain_slope: 1.0 - clamp(slope_degrees / 15.0)
        slope_score = 1.0 - self._clamp(slope / 15.0)

        # soil_stability: lookup from soil quality classification
        soil_score = SOIL_STABILITY_SCORES.get(soil_quality, SOIL_STABILITY_SCORES["unknown"])

        # hazard_proximity: clamp(min(wetland_km, superfund_km) / 5.0)
        wetland_km = self._nearest_distance_km(cell.lat, cell.lng, wetland_coords)
        superfund_km = self._nearest_distance_km(cell.lat, cell.lng, superfund_coords)
        hazard_km = min(wetland_km, superfund_km)
        hazard_score = self._clamp(hazard_km / 5.0)

        sub_scores = {
            "seismic_hazard":   round(seismic_score, 4),
            "terrain_slope":    round(slope_score, 4),
            "soil_stability":   round(soil_score, 4),
            "hazard_proximity": round(hazard_score, 4),
        }

        # Roll up sub-metrics using GEOLOGICAL_SUB_WEIGHTS
        category_score = self._weighted_sum(sub_scores, GEOLOGICAL_SUB_WEIGHTS)

        metrics = {
            "seismic_hazard_pga":    round(pga, 4),
            "slope_degrees":         round(slope, 2),
            "elevation_m":           round(elevation, 1),
            "soil_bearing_capacity": soil_quality,
            "nearest_wetland_km":    round(wetland_km if wetland_km != 999.0 else 10.0, 2),
            "nearest_superfund_km":  round(superfund_km if superfund_km != 999.0 else 15.0, 2),
        }

        return CellScore(
            lat=cell.lat,
            lng=cell.lng,
            raw_scores={self.category_id: round(category_score, 4)},
            sub_scores=sub_scores,
            metrics=metrics,
        )

    def _land_cover_to_soil_quality(self, land_class: int) -> str:
        """
        Estimate soil bearing capacity from NLCD land cover class.
        This is a rough proxy — production would use SSURGO soil survey data.
        """
        if land_class in UNSTABLE_LAND_COVERS:
            return "low"
        if land_class in STABLE_LAND_COVERS:
            return "moderate"
        if land_class in (41, 42, 43):  # Forest — generally stable
            return "moderate"
        return "unknown"

    def _extract_point_coords(self, features: list) -> list[tuple[float, float]]:
        """Extract (lat, lng) from GeoJSON Point features."""
        coords = []
        for f in features:
            geom = f.get("geometry", {})
            if geom.get("type") == "Point":
                c = geom["coordinates"]
                coords.append((c[1], c[0]))  # GeoJSON: [lng, lat] → (lat, lng)
        return coords

    def _extract_polygon_centroids(self, features: list) -> list[tuple[float, float]]:
        """Compute centroids from GeoJSON Polygon features."""
        coords = []
        for f in features:
            geom = f.get("geometry", {})
            ring = None
            if geom.get("type") == "Polygon":
                ring = geom["coordinates"][0]
            elif geom.get("type") == "MultiPolygon":
                if geom["coordinates"]:
                    ring = geom["coordinates"][0][0]
            if ring:
                avg_lat = sum(c[1] for c in ring) / len(ring)
                avg_lng = sum(c[0] for c in ring) / len(ring)
                coords.append((avg_lat, avg_lng))
        return coords

    def _build_land_cover_map(self, land_cover: dict) -> dict:
        """Build a (rounded_lat, rounded_lng) → class_int lookup for fast cell scoring."""
        mapping = {}
        for point in land_cover.get("grid", []):
            key = (round(point["lat"], 3), round(point["lng"], 3))
            mapping[key] = point.get("class", 82)
        return mapping

    def _nearest_distance_km(self, lat: float, lng: float, points: list) -> float:
        """Find the km distance to the nearest point. Returns 999 if list is empty."""
        if not points:
            return 999.0
        min_d = float("inf")
        for plat, plng in points:
            d = self._haversine_km(lat, lng, plat, plng)
            if d < min_d:
                min_d = d
        return min_d

    def _haversine_km(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate great-circle distance in km between two WGS84 points."""
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
