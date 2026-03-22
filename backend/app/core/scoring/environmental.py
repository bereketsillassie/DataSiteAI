"""
app/core/scoring/environmental.py
───────────────────────────────────
Environmental scorer.

Formulas (from CLAUDE.md):
  population_proximity:  1.0 - clamp(population_within_5km / 50000)
  sensitive_sites:       clamp(min(nearest_school_km, nearest_hospital_km) / 2.0)
  air_quality:           1.0 - clamp(aqi / 300.0)
  land_sensitivity:      0.0 if protected_land_within_1km else 1.0

<<<<<<< HEAD
Data sources: OSM (schools, hospitals via region batch), EPA AirNow (region-level),
              US Census (population density), GEE (NLCD land cover)

BATCHING — all external calls are region-level, not per-cell:
  osm.get_region_data(bbox)              — 1 Overpass call (amenities from cache)
  epa.get_air_quality_for_region(bbox)   — 1 AirNow call  (was 99 per-cell calls)
  census.get_population_density(bbox)    — 1 Census call
  gee.get_land_cover(bbox)               — 1 GEE call (non-fatal)

Per-cell scoring uses each cell's specific lat/lng to compute distances to
amenity coordinates fetched for the region. Every cell gets a unique score
reflecting its actual distance to the nearest school, hospital, etc.

NOTE: This scorer reads ENVIRONMENTAL_SUB_WEIGHTS from weights.py only.
It NEVER reads CATEGORY_WEIGHTS — that is the engine's job.
=======
Data sources: OSM (schools, hospitals), EPA AirNow (AQI),
              US Census (population density), GEE (NLCD land cover)

NOTE: "environmental" in this scorer's context means proximity to sensitive things
that could complicate data center siting — not environmental impact assessment.
Fewer people nearby, farther from schools/hospitals, better air = higher score.

NOTE: This scorer reads ENVIRONMENTAL_SUB_WEIGHTS from weights.py to roll up its own
sub-metrics. It NEVER reads CATEGORY_WEIGHTS — that is the engine's job only.
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
"""

import logging
import math

from app.core.scoring.base import BaseScorer
from app.core.scoring.weights import ENVIRONMENTAL_SUB_WEIGHTS
from app.core.grid import generate_grid
from app.models.domain import BoundingBox, CellScore

logger = logging.getLogger(__name__)

<<<<<<< HEAD
PROTECTED_LAND_COVER_CLASSES: set[int] = {11, 90, 95}   # water, wetlands
DEVELOPED_LAND_COVER_CLASSES: set[int] = {21, 22, 23, 24}  # developed land
=======
# NLCD classes that indicate protected or environmentally sensitive land
# These indicate a location should NOT be developed as a data center
PROTECTED_LAND_COVER_CLASSES: set[int] = {
    11,   # Open Water
    90,   # Woody Wetlands
    95,   # Emergent Herbaceous Wetlands
}

# NLCD classes that indicate already-developed land (acceptable for data centers)
DEVELOPED_LAND_COVER_CLASSES: set[int] = {
    21,   # Developed, Open Space
    22,   # Developed, Low Intensity
    23,   # Developed, Medium Intensity
    24,   # Developed, High Intensity
}
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e


class EnvironmentalScorer(BaseScorer):
    """Scores locations on population proximity, sensitive sites, air quality, and land use."""

    category_id = "environmental"

<<<<<<< HEAD
    def __init__(self, db_session=None, settings=None):
=======
    def __init__(self, redis_client=None, settings=None):
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        from app.integrations.osm import OSMClient
        from app.integrations.epa import EPAClient
        from app.integrations.census import CensusClient
        from app.integrations.gee import GEEClient
        from app.config import settings as default_settings

        self.settings = settings or default_settings
<<<<<<< HEAD
        self.osm     = OSMClient(db_session=db_session, settings=self.settings)
        self.epa     = EPAClient(db_session=db_session, settings=self.settings)
        self.census  = CensusClient(db_session=db_session, settings=self.settings)
        self.gee     = GEEClient(db_session=db_session, settings=self.settings)

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """
        Score all grid cells for environmental proximity factors.

        All 4 external calls happen ONCE at region level.
        Per-cell scoring computes unique distances from each cell's lat/lng
        to the shared set of amenity coordinates — every cell gets a real,
        differentiated score based on its actual location.
        """
        grid_res = getattr(self.settings, "GRID_RESOLUTION_DEFAULT_KM", 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

        # ── 1 Overpass call — amenities from region batch cache ───────────────
        # engine.py calls get_region_data() before scorers run, so this hits cache
        try:
            osm_data = await self.osm.get_region_data(bbox)
            school_amenities   = [
                f for f in osm_data.get("amenities", [])
                if f.get("properties", {}).get("amenity") in ("school", "university", "college")
            ]
            hospital_amenities = [
                f for f in osm_data.get("amenities", [])
                if f.get("properties", {}).get("amenity") in ("hospital", "clinic")
            ]
        except Exception as e:
            logger.error(f"EnvironmentalScorer: OSM amenities failed: {e}")
            school_amenities   = []
            hospital_amenities = []

        # ── 1 AirNow call for the whole region (was 99 per-cell calls) ────────
        # AQI represents regional air quality — it doesn't vary at 5km resolution.
        # Each cell receives this same AQI value, which is accurate for the region.
        try:
            region_aqi = await self.epa.get_air_quality_for_region(bbox)
        except Exception as e:
            logger.warning(f"EnvironmentalScorer: AirNow fetch failed (non-fatal): {e}")
            region_aqi = 45.0  # moderate default

        # ── 1 Census call for population density ──────────────────────────────
        try:
            pop_data = await self.census.get_population_density(bbox)
            pop_5km  = pop_data.get("population_within_5km_estimate", 5000)
        except Exception as e:
            logger.error(f"EnvironmentalScorer: Census population failed: {e}")
            pop_5km = 5000

        # ── 1 GEE call for land cover (non-fatal) ─────────────────────────────
        try:
            land_cover_data = await self.gee.get_land_cover(bbox)
        except Exception as e:
            logger.warning(f"EnvironmentalScorer: GEE land cover unavailable (non-fatal): {e}")
            land_cover_data = {"grid": []}

        # Precompute coordinate lookups once — reused in every cell's math
        school_coords   = self._extract_point_coords(school_amenities)
        hospital_coords = self._extract_point_coords(hospital_amenities)
        land_cover_map  = self._build_land_cover_map(land_cover_data)

        # ── Per-cell scoring — pure distance math, zero API calls ─────────────
        # Each cell computes its own distances to the shared coordinate lists,
        # producing unique scores that reflect each cell's actual location.
        results = []
        for cell in grid:
            try:
                lc_key     = (round(cell.lat, 3), round(cell.lng, 3))
                land_class = land_cover_map.get(lc_key, 82)  # default: cultivated crops
                cs = self._score_cell(
                    cell, school_coords, hospital_coords,
                    region_aqi, land_class, pop_5km,
=======
        self.osm = OSMClient(redis_client=redis_client, settings=self.settings)
        self.epa = EPAClient(redis_client=redis_client, settings=self.settings)
        self.census = CensusClient(redis_client=redis_client, settings=self.settings)
        self.gee = GEEClient(redis_client=redis_client, settings=self.settings)

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """Score all grid cells in the bbox for environmental proximity factors."""
        grid_res = getattr(self.settings, 'GRID_RESOLUTION_DEFAULT_KM', 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

        # Fetch sensitive site locations (schools, hospitals, universities)
        try:
            school_amenities = await self.osm.get_amenities(
                bbox, types=["school", "university", "college"]
            )
        except Exception as e:
            logger.error(f"EnvironmentalScorer: OSM school amenities failed: {e}")
            school_amenities = []

        try:
            hospital_amenities = await self.osm.get_amenities(
                bbox, types=["hospital", "clinic", "healthcare"]
            )
        except Exception as e:
            logger.error(f"EnvironmentalScorer: OSM hospital amenities failed: {e}")
            hospital_amenities = []

        # Fetch NLCD land cover for the bbox
        try:
            land_cover_data = await self.gee.get_land_cover(bbox)
        except Exception as e:
            logger.warning(f"EnvironmentalScorer: GEE land cover failed (non-fatal): {e}")
            land_cover_data = {"grid": []}

        # Fetch population density
        try:
            pop_data = await self.census.get_population_density(bbox)
        except Exception as e:
            logger.error(f"EnvironmentalScorer: Census population failed: {e}")
            pop_data = {"population_within_5km_estimate": 5000}

        # Precompute coordinate lists for distance calculations
        school_coords = self._extract_point_coords(school_amenities)
        hospital_coords = self._extract_point_coords(hospital_amenities)
        land_cover_map = self._build_land_cover_map(land_cover_data)
        pop_5km = pop_data.get("population_within_5km_estimate", 5000)

        results = []
        for cell in grid:
            try:
                # AQI is fetched per-cell as it can vary significantly across a bbox
                aqi = await self.epa.get_air_quality(cell.lat, cell.lng)

                # Get land cover class for this cell
                lc_key = (round(cell.lat, 3), round(cell.lng, 3))
                land_class = land_cover_map.get(lc_key, 82)  # Default: Cultivated Crops

                cs = self._score_cell(
                    cell, school_coords, hospital_coords,
                    aqi, land_class, pop_5km
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
                )
                results.append(cs)
            except Exception as e:
                logger.warning(f"EnvironmentalScorer: cell ({cell.lat},{cell.lng}) failed: {e}")
                results.append(CellScore(lat=cell.lat, lng=cell.lng, error=str(e)))

        return results

    def _score_cell(
<<<<<<< HEAD
        self,
        cell,
        school_coords: list,
        hospital_coords: list,
        aqi: float,
        land_class: int,
        pop_5km: int,
    ) -> CellScore:
        """
        Score a single grid cell using pre-fetched region data.

        UNIQUE PER CELL: nearest_school_km and nearest_hospital_km are computed
        from this cell's specific lat/lng vs the full coordinate list, so cells
        closer to schools score lower on sensitive_sites than cells farther away.
        Land cover class also varies per cell via the GEE grid lookup.
        """

        # population_proximity: 0 people = best, 50k+ = worst
        pop_score = 1.0 - self._clamp(pop_5km / 50000.0)

        # sensitive_sites: each cell computes its own nearest distance
        nearest_school_km   = self._nearest_distance_km(cell.lat, cell.lng, school_coords)
        nearest_hospital_km = self._nearest_distance_km(cell.lat, cell.lng, hospital_coords)
        if nearest_school_km   == 999.0: nearest_school_km   = 5.0
        if nearest_hospital_km == 999.0: nearest_hospital_km = 5.0
        sensitive_score = self._clamp(min(nearest_school_km, nearest_hospital_km) / 2.0)

        # air_quality: AQI 0 = best, 300+ = hazardous
        aqi_score = 1.0 - self._clamp(aqi / 300.0)

        # land_sensitivity: protected land (wetlands/water) = disqualifying
        is_protected = land_class in PROTECTED_LAND_COVER_CLASSES
        land_score   = 0.0 if is_protected else 1.0

        sub_scores = {
            "population_proximity": round(pop_score,       4),
            "sensitive_sites":      round(sensitive_score, 4),
            "air_quality":          round(aqi_score,       4),
            "land_sensitivity":     round(land_score,      4),
        }

        category_score = self._weighted_sum(sub_scores, ENVIRONMENTAL_SUB_WEIGHTS)

        try:
            from app.integrations.gee import NLCD_CLASS_NAMES
            land_cover_name = NLCD_CLASS_NAMES.get(land_class, "Unknown")
        except ImportError:
            land_cover_name = "Unknown"

        metrics = {
            "population_within_5km":     pop_5km,
            "nearest_school_km":         round(nearest_school_km, 2),
            "nearest_hospital_km":       round(nearest_hospital_km, 2),
            "air_quality_index":         round(aqi, 1),
            "protected_land_within_1km": is_protected,
            "land_cover_type":           land_cover_name,
=======
        self, cell, school_coords: list, hospital_coords: list,
        aqi: float, land_class: int, pop_5km: int
    ) -> CellScore:
        """Score a single grid cell for environmental proximity factors."""

        # population_proximity: 1.0 - clamp(population_within_5km / 50000)
        # 0 people within 5km = best (remote location), 50000+ = worst (dense urban)
        pop_score = 1.0 - self._clamp(pop_5km / 50000.0)

        # sensitive_sites: clamp(min(nearest_school_km, nearest_hospital_km) / 2.0)
        # Farther from schools/hospitals = higher score (less community opposition)
        nearest_school_km = self._nearest_distance_km(cell.lat, cell.lng, school_coords)
        nearest_hospital_km = self._nearest_distance_km(cell.lat, cell.lng, hospital_coords)
        # Apply defaults when no amenities are found in the bbox
        if nearest_school_km == 999.0:
            nearest_school_km = 5.0
        if nearest_hospital_km == 999.0:
            nearest_hospital_km = 5.0
        min_sensitive_km = min(nearest_school_km, nearest_hospital_km)
        sensitive_score = self._clamp(min_sensitive_km / 2.0)

        # air_quality: 1.0 - clamp(aqi / 300.0)
        # AQI 0 = best (clean air), 300+ = worst (hazardous — data center staff risk)
        aqi_score = 1.0 - self._clamp(aqi / 300.0)

        # land_sensitivity: 0.0 if protected land within 1km, 1.0 otherwise
        # Protected land (wetlands, water) = disqualifying — score 0
        # Any other land use = acceptable — score 1.0
        is_protected = land_class in PROTECTED_LAND_COVER_CLASSES
        land_score = 0.0 if is_protected else 1.0

        sub_scores = {
            "population_proximity": round(pop_score, 4),
            "sensitive_sites":      round(sensitive_score, 4),
            "air_quality":          round(aqi_score, 4),
            "land_sensitivity":     round(land_score, 4),
        }

        # Roll up sub-metrics using ENVIRONMENTAL_SUB_WEIGHTS
        category_score = self._weighted_sum(sub_scores, ENVIRONMENTAL_SUB_WEIGHTS)

        # Get human-readable land cover name
        from app.integrations.gee import NLCD_CLASS_NAMES
        land_cover_name = NLCD_CLASS_NAMES.get(land_class, "Unknown")

        metrics = {
            "population_within_5km":      pop_5km,
            "nearest_school_km":          round(nearest_school_km, 2),
            "nearest_hospital_km":        round(nearest_hospital_km, 2),
            "air_quality_index":          round(aqi, 1),
            "protected_land_within_1km":  is_protected,
            "land_cover_type":            land_cover_name,
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        }

        return CellScore(
            lat=cell.lat,
            lng=cell.lng,
            raw_scores={self.category_id: round(category_score, 4)},
            sub_scores=sub_scores,
            metrics=metrics,
        )

    def _extract_point_coords(self, features: list) -> list[tuple[float, float]]:
<<<<<<< HEAD
        coords = []
        for f in features:
            geom = f.get("geometry") or {}
            if geom.get("type") == "Point":
                c = geom.get("coordinates") or []
                if len(c) >= 2:
                    coords.append((c[1], c[0]))  # GeoJSON [lng,lat] → (lat,lng)
        return coords

    def _nearest_distance_km(self, lat: float, lng: float, points: list) -> float:
        if not points:
            return 999.0
        return min(self._haversine_km(lat, lng, p[0], p[1]) for p in points)

    def _haversine_km(self, lat1, lng1, lat2, lng2) -> float:
=======
        """Extract (lat, lng) from GeoJSON Point features."""
        coords = []
        for f in features:
            geom = f.get("geometry", {})
            if geom.get("type") == "Point":
                c = geom["coordinates"]
                coords.append((c[1], c[0]))  # GeoJSON: [lng, lat] → (lat, lng)
        return coords

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
        return R * 2 * math.asin(math.sqrt(a))

    def _build_land_cover_map(self, land_cover: dict) -> dict:
<<<<<<< HEAD
        return {
            (round(p["lat"], 3), round(p["lng"], 3)): p.get("class", 82)
            for p in land_cover.get("grid", [])
        }
=======
        """Build a (rounded_lat, rounded_lng) → class_int lookup for fast cell scoring."""
        mapping = {}
        for point in land_cover.get("grid", []):
            key = (round(point["lat"], 3), round(point["lng"], 3))
            mapping[key] = point.get("class", 82)
        return mapping
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
