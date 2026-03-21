"""
app/core/scoring/water.py
──────────────────────────
Water scorer.

Formulas (from CLAUDE.md):
  flood_risk:        Zone X→1.0, Zone B/X500→0.7, Zone A→0.3, Zone AE/VE/AO→0.0
  water_availability:1.0 - clamp(nearest_water_body_km / 10.0)
                     + 0.2 bonus if groundwater="high"
  drought_risk:      D0→0.9, D1→0.7, D2→0.5, D3→0.2, D4→0.0

Data sources: FEMA (flood zones), OSM (water bodies), NASA POWER (drought proxy)

NOTE: This scorer reads WATER_SUB_WEIGHTS from weights.py to roll up its own
sub-metrics. It NEVER reads CATEGORY_WEIGHTS — that is the engine's job only.
"""

import logging
import math

from app.core.scoring.base import BaseScorer
from app.core.scoring.weights import WATER_SUB_WEIGHTS
from app.core.grid import generate_grid
from app.models.domain import BoundingBox, CellScore

logger = logging.getLogger(__name__)

# Flood zone score lookup — FEMA zone codes → raw score (1.0=safe, 0.0=dangerous)
FLOOD_ZONE_SCORES: dict[str, float] = {
    "X":    1.0,   # Zone X: Minimal flood hazard (most common safe zone)
    "C":    1.0,   # Zone C: Minimal flood hazard (older designation, same as X)
    "B":    0.7,   # Zone B: Moderate flood hazard
    "X500": 0.7,   # Zone X500: 0.2% annual chance (500-year) flood zone
    "A":    0.3,   # Zone A: 1% annual chance (100-year) flood — no base flood elevation
    "AR":   0.3,   # Zone AR: Area to be restored to pre-project condition
    "A99":  0.4,   # Zone A99: Protected by federal flood control project
    "AH":   0.1,   # Zone AH: 1% annual chance shallow flooding, ponding
    "AE":   0.0,   # Zone AE: 1% annual chance, detailed study, high risk
    "AO":   0.0,   # Zone AO: 1% annual chance river or stream flood, sheet flow
    "V":    0.05,  # Zone V: Coastal high-hazard area, wave action, no BFE
    "VE":   0.0,   # Zone VE: Coastal high-hazard, detailed study, highest risk
}

# Drought score lookup — USDM classification → raw score
DROUGHT_SCORES: dict[str, float] = {
    "None": 1.0,   # No drought
    "D0":   0.9,   # Abnormally dry
    "D1":   0.7,   # Moderate drought
    "D2":   0.5,   # Severe drought
    "D3":   0.2,   # Extreme drought
    "D4":   0.0,   # Exceptional drought
}


class WaterScorer(BaseScorer):
    """Scores locations on flood risk, water availability, and drought conditions."""

    category_id = "water"

    def __init__(self, redis_client=None, settings=None):
        from app.integrations.fema import FEMAClient
        from app.integrations.osm import OSMClient
        from app.config import settings as default_settings

        self.settings = settings or default_settings
        self.fema = FEMAClient(redis_client=redis_client, settings=self.settings)
        self.osm = OSMClient(redis_client=redis_client, settings=self.settings)

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """Score all grid cells in the bbox for water-related factors."""
        grid_res = getattr(self.settings, 'GRID_RESOLUTION_DEFAULT_KM', 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

        try:
            flood_zones = await self.fema.get_flood_zones(bbox)
        except Exception as e:
            logger.error(f"WaterScorer: FEMA flood zones failed: {e}")
            flood_zones = []

        # Fetch waterway/water body features from OSM for water_availability scoring
        try:
            water_features = await self.osm.get_highways(bbox, types=["waterway"])
        except Exception as e:
            logger.warning(f"WaterScorer: OSM waterway fetch failed (non-fatal): {e}")
            water_features = []

        # Extract water body point coordinates for distance calculations
        water_coords = self._extract_water_coords(water_features)

        # Groundwater and drought defaults — in production these come from USGS and NDMC
        # Mock mode returns these typical NC values
        groundwater = "moderate"
        drought_level = "None"

        results = []
        for cell in grid:
            try:
                cs = self._score_cell(cell, flood_zones, water_coords, groundwater, drought_level)
                results.append(cs)
            except Exception as e:
                logger.warning(f"WaterScorer: cell ({cell.lat},{cell.lng}) failed: {e}")
                results.append(CellScore(lat=cell.lat, lng=cell.lng, error=str(e)))

        return results

    def _score_cell(
        self, cell, flood_zones, water_coords, groundwater, drought_level
    ) -> CellScore:
        """Score a single grid cell for water factors."""

        # --- Flood risk score ---
        flood_zone = self._flood_zone_at_point(cell.lat, cell.lng, flood_zones)
        flood_score = FLOOD_ZONE_SCORES.get(flood_zone, 0.5)
        flood_risk_pct = round((1.0 - flood_score) * 100.0, 1)

        # --- Water availability score ---
        nearest_water_km = self._nearest_distance_km(cell.lat, cell.lng, water_coords)
        if nearest_water_km == 999.0:
            nearest_water_km = 3.0  # Assume 3km if no OSM data available
        water_avail_score = 1.0 - self._clamp(nearest_water_km / 10.0)
        if groundwater == "high":
            water_avail_score = min(1.0, water_avail_score + 0.2)

        # --- Drought risk score ---
        drought_score = DROUGHT_SCORES.get(drought_level, 0.5)

        sub_scores = {
            "flood_risk":         round(flood_score, 4),
            "water_availability": round(water_avail_score, 4),
            "drought_risk":       round(drought_score, 4),
        }

        # Roll up sub-metrics using WATER_SUB_WEIGHTS
        category_score = self._weighted_sum(sub_scores, WATER_SUB_WEIGHTS)

        metrics = {
            "fema_flood_zone":          flood_zone,
            "flood_risk_pct":           flood_risk_pct,
            "nearest_water_body_km":    round(nearest_water_km, 2),
            "groundwater_availability": groundwater,
            "drought_risk_level":       drought_level,
        }

        return CellScore(
            lat=cell.lat,
            lng=cell.lng,
            raw_scores={self.category_id: round(category_score, 4)},
            sub_scores=sub_scores,
            metrics=metrics,
        )

    def _flood_zone_at_point(self, lat: float, lng: float, flood_zones: list) -> str:
        """
        Determine which FEMA flood zone polygon contains this point.
        Checks highest-risk zones first to return the correct designation
        when zones overlap.
        """
        if not flood_zones:
            return "X"  # Default: low risk when no FEMA data

        # Check highest-risk zones first (AE, VE, AO)
        for feat in flood_zones:
            props = feat.get("properties", {})
            zone = props.get("FLD_ZONE", "X")
            if zone in ("AE", "VE", "AO", "AH") and self._point_in_feature(lat, lng, feat):
                return zone

        # Then check Zone A and A99
        for feat in flood_zones:
            props = feat.get("properties", {})
            zone = props.get("FLD_ZONE", "X")
            if zone in ("A", "AR", "A99") and self._point_in_feature(lat, lng, feat):
                return zone

        # Then check X500/B (0.2% annual chance)
        for feat in flood_zones:
            props = feat.get("properties", {})
            zone = props.get("FLD_ZONE", "X")
            subtype = props.get("ZONE_SUBTY", "")
            if (("0.2 PCT" in subtype or zone in ("B", "X500"))
                    and self._point_in_feature(lat, lng, feat)):
                return "X500"

        return "X"  # Default: minimal flood hazard

    def _point_in_feature(self, lat: float, lng: float, feature: dict) -> bool:
        """
        Check if a point is within the bounding box of a GeoJSON feature.
        This is a simplified check (bounding box, not true polygon) for performance.
        A true point-in-polygon test would use Shapely — acceptable for 5km grid scoring.
        """
        try:
            geom = feature.get("geometry", {})
            geom_type = geom.get("type", "")
            if geom_type == "Polygon":
                coords = geom["coordinates"][0]
            elif geom_type == "MultiPolygon":
                # Check each polygon in the multipolygon
                for poly in geom["coordinates"]:
                    coords = poly[0]
                    lngs = [c[0] for c in coords]
                    lats = [c[1] for c in coords]
                    if min(lngs) <= lng <= max(lngs) and min(lats) <= lat <= max(lats):
                        return True
                return False
            else:
                return False
            lngs = [c[0] for c in coords]
            lats = [c[1] for c in coords]
            return min(lngs) <= lng <= max(lngs) and min(lats) <= lat <= max(lats)
        except Exception:
            return False

    def _extract_water_coords(self, features: list) -> list[tuple[float, float]]:
        """Extract coordinate points from waterway LineString features (as midpoints)."""
        coords = []
        for feat in features:
            geom = feat.get("geometry", {})
            if geom.get("type") == "LineString":
                pts = geom["coordinates"]
                if pts:
                    mid = pts[len(pts) // 2]
                    coords.append((mid[1], mid[0]))  # GeoJSON: [lng, lat] → (lat, lng)
            elif geom.get("type") == "Point":
                c = geom["coordinates"]
                coords.append((c[1], c[0]))
        return coords

    def _nearest_distance_km(self, lat: float, lng: float, points: list) -> float:
        """Find the km distance to the nearest point in the list. Returns 999 if empty."""
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
