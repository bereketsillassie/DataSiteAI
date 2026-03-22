"""
app/core/scoring/water.py
──────────────────────────
Water scorer.

Formulas (from CLAUDE.md):
  flood_risk:        Zone X→1.0, Zone B/X500→0.7, Zone A→0.3, Zone AE/VE/AO→0.0
  water_availability:1.0 - clamp(nearest_water_body_km / 10.0)
                     + 0.2 bonus if groundwater="high"
  drought_risk:      D0→0.9, D1→0.7, D2→0.5, D3→0.2, D4→0.0

<<<<<<< HEAD
Data sources: FEMA (flood zones), OSM region batch (waterways)

BATCHING:
  - fema.get_flood_zones(bbox)    — one call per region, shared across all cells
  - osm.get_region_data(bbox)     — one Overpass call, waterways extracted from result
  - All per-cell work is pure geometry math, zero API calls

NoneType fix: FEMA returns ZONE_SUBTY as JSON null → Python None.
  Use `props.get("ZONE_SUBTY") or ""` to safely coerce None → "".
=======
Data sources: FEMA (flood zones), OSM (water bodies), NASA POWER (drought proxy)
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e

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

<<<<<<< HEAD
FLOOD_ZONE_SCORES: dict[str, float] = {
    "X":    1.0,
    "C":    1.0,
    "B":    0.7,
    "X500": 0.7,
    "A":    0.3,
    "AR":   0.3,
    "A99":  0.4,
    "AH":   0.1,
    "AE":   0.0,
    "AO":   0.0,
    "V":    0.05,
    "VE":   0.0,
}

DROUGHT_SCORES: dict[str, float] = {
    "None": 1.0,
    "D0":   0.9,
    "D1":   0.7,
    "D2":   0.5,
    "D3":   0.2,
    "D4":   0.0,
=======
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
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
}


class WaterScorer(BaseScorer):
    """Scores locations on flood risk, water availability, and drought conditions."""

    category_id = "water"

<<<<<<< HEAD
    def __init__(self, db_session=None, settings=None):
=======
    def __init__(self, redis_client=None, settings=None):
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        from app.integrations.fema import FEMAClient
        from app.integrations.osm import OSMClient
        from app.config import settings as default_settings

        self.settings = settings or default_settings
<<<<<<< HEAD
        self.fema = FEMAClient(db_session=db_session, settings=self.settings)
        self.osm = OSMClient(db_session=db_session, settings=self.settings)

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """
        Score all grid cells for water factors.

        All external data is fetched ONCE at region level:
          - FEMA flood zones: 1 call
          - OSM region data:  1 Overpass call (waterways extracted from batch result)
        Per-cell work is pure geometry math — zero additional API calls.
        """
        grid_res = getattr(self.settings, "GRID_RESOLUTION_DEFAULT_KM", 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

        # ── 1 FEMA call for the whole region ──────────────────────────────────
=======
        self.fema = FEMAClient(redis_client=redis_client, settings=self.settings)
        self.osm = OSMClient(redis_client=redis_client, settings=self.settings)

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """Score all grid cells in the bbox for water-related factors."""
        grid_res = getattr(self.settings, 'GRID_RESOLUTION_DEFAULT_KM', 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        try:
            flood_zones = await self.fema.get_flood_zones(bbox)
        except Exception as e:
            logger.error(f"WaterScorer: FEMA flood zones failed: {e}")
            flood_zones = []

<<<<<<< HEAD
        # ── 1 Overpass call — extract waterways from region batch ─────────────
        # NOTE: OSM waterways are NOT a highway type.
        # They come from the region batch as ways tagged natural=water / waterway=*
        # We pull them from get_region_data() if present, otherwise fall back to
        # a dedicated waterway query via get_fiber_routes slot (fiber key unused here).
        try:
            osm_data = await self.osm.get_region_data(bbox)
            # Waterways aren't their own bucket in get_region_data yet —
            # use highways as a distance proxy (roads follow water corridors)
            # and add a dedicated waterway fetch as a supplemental non-fatal call
            waterway_features = osm_data.get("waterways", [])
            if not waterway_features:
                waterway_features = await self._fetch_waterways(bbox)
        except Exception as e:
            logger.warning(f"WaterScorer: OSM waterway fetch failed (non-fatal): {e}")
            waterway_features = []

        water_coords = self._extract_water_coords(waterway_features)

        # Groundwater and drought — state-level defaults
        # Production: pull from USGS groundwater API and NDMC drought monitor
        groundwater   = "moderate"
        drought_level = "None"

        # ── Per-cell scoring — pure math, no API calls ────────────────────────
=======
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

>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        results = []
        for cell in grid:
            try:
                cs = self._score_cell(cell, flood_zones, water_coords, groundwater, drought_level)
                results.append(cs)
            except Exception as e:
                logger.warning(f"WaterScorer: cell ({cell.lat},{cell.lng}) failed: {e}")
                results.append(CellScore(lat=cell.lat, lng=cell.lng, error=str(e)))

        return results

<<<<<<< HEAD
    async def _fetch_waterways(self, bbox: BoundingBox) -> list[dict]:
        """
        Dedicated waterway fetch as a fallback if get_region_data() didn't include them.
        Non-fatal — returns empty list on failure.
        """
        try:
            import asyncio
            await asyncio.sleep(1.0)
            client = await self.osm._get_http_client()
            bb = bbox.overpass_bbox()
            query = f"""
            [out:json][timeout:30];
            (
              way["natural"="water"]({bb});
              way["waterway"~"^(river|stream|canal|drain)$"]({bb});
              relation["natural"="water"]({bb});
            );
            out center geom;
            """
            from app.integrations.osm import OVERPASS_URL
            response = await client.post(
                OVERPASS_URL, data={"data": query}, timeout=45.0
            )
            if response.status_code == 200:
                elements = response.json().get("elements", [])
                return self.osm._to_features(elements)
        except Exception as e:
            logger.warning(f"WaterScorer: dedicated waterway fetch failed: {e}")
        return []

    def _score_cell(
        self, cell, flood_zones, water_coords, groundwater, drought_level
    ) -> CellScore:
        """Score a single grid cell — all inputs are pre-fetched region data."""

        flood_zone  = self._flood_zone_at_point(cell.lat, cell.lng, flood_zones)
        flood_score = FLOOD_ZONE_SCORES.get(flood_zone, 0.5)
        flood_risk_pct = round((1.0 - flood_score) * 100.0, 1)

        nearest_water_km = self._nearest_distance_km(cell.lat, cell.lng, water_coords)
        if nearest_water_km == 999.0:
            nearest_water_km = 3.0  # default if no OSM waterway data
=======
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
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        water_avail_score = 1.0 - self._clamp(nearest_water_km / 10.0)
        if groundwater == "high":
            water_avail_score = min(1.0, water_avail_score + 0.2)

<<<<<<< HEAD
        drought_score = DROUGHT_SCORES.get(drought_level, 0.5)

        sub_scores = {
            "flood_risk":         round(flood_score,       4),
            "water_availability": round(water_avail_score, 4),
            "drought_risk":       round(drought_score,     4),
        }

=======
        # --- Drought risk score ---
        drought_score = DROUGHT_SCORES.get(drought_level, 0.5)

        sub_scores = {
            "flood_risk":         round(flood_score, 4),
            "water_availability": round(water_avail_score, 4),
            "drought_risk":       round(drought_score, 4),
        }

        # Roll up sub-metrics using WATER_SUB_WEIGHTS
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
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
<<<<<<< HEAD
        Return the highest-risk FEMA flood zone for this point.
        Checks zones from highest to lowest risk so overlapping zones
        return the most conservative (most hazardous) designation.
        """
        if not flood_zones:
            return "X"

        priority_groups = [
            ("AE", "VE", "AO", "AH"),
            ("A", "AR", "A99", "V"),
            ("B",),
        ]
        for group in priority_groups:
            for feat in flood_zones:
                props = feat.get("properties", {})
                zone  = props.get("FLD_ZONE", "X")
                if zone in group and self._point_in_feature(lat, lng, feat):
                    return zone

        # Check X500 (Zone X with 0.2% subtype)
        for feat in flood_zones:
            props   = feat.get("properties", {})
            zone    = props.get("FLD_ZONE", "X")
            # FIX: FEMA returns ZONE_SUBTY as null → None; coerce to "" before `in` check
            subtype = props.get("ZONE_SUBTY") or ""
            if ("0.2 PCT" in subtype or zone in ("B", "X500")) and \
               self._point_in_feature(lat, lng, feat):
                return "X500"

        return "X"

    def _point_in_feature(self, lat: float, lng: float, feature: dict) -> bool:
        """
        Bounding-box containment check for a GeoJSON polygon feature.
        Fast O(1) proxy for point-in-polygon — acceptable for 5km grid resolution.
        """
        try:
            geom      = feature.get("geometry") or {}
            geom_type = geom.get("type", "")
            coords_list = geom.get("coordinates")
            if not coords_list:
                return False

            if geom_type == "Polygon":
                rings = [coords_list[0]]
            elif geom_type == "MultiPolygon":
                rings = [poly[0] for poly in coords_list if poly]
            else:
                return False

            for ring in rings:
                if not ring:
                    continue
                lngs = [c[0] for c in ring]
                lats = [c[1] for c in ring]
                if min(lngs) <= lng <= max(lngs) and min(lats) <= lat <= max(lats):
                    return True
            return False
=======
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
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        except Exception:
            return False

    def _extract_water_coords(self, features: list) -> list[tuple[float, float]]:
<<<<<<< HEAD
        """Extract midpoints from waterway LineString and Point features."""
        coords = []
        for feat in features:
            geom = feat.get("geometry") or {}
            if geom.get("type") == "LineString":
                pts = geom.get("coordinates") or []
                if pts:
                    mid = pts[len(pts) // 2]
                    coords.append((mid[1], mid[0]))
            elif geom.get("type") == "Point":
                c = geom.get("coordinates") or []
                if len(c) >= 2:
                    coords.append((c[1], c[0]))
        return coords

    def _nearest_distance_km(self, lat: float, lng: float, points: list) -> float:
        if not points:
            return 999.0
        return min(self._haversine_km(lat, lng, p[0], p[1]) for p in points)

    def _haversine_km(self, lat1, lng1, lat2, lng2) -> float:
=======
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
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlng / 2) ** 2
        )
<<<<<<< HEAD
        return R * 2 * math.asin(math.sqrt(a))
=======
        return R * 2 * math.asin(math.sqrt(a))
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
