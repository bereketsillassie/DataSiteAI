"""
app/core/scoring/environmental.py
───────────────────────────────────
Environmental scorer.

Formulas (from CLAUDE.md):
  population_proximity:  1.0 - clamp(population_within_5km / 50000)
  sensitive_sites:       clamp(min(nearest_school_km, nearest_hospital_km) / 2.0)
  air_quality:           1.0 - clamp(aqi / 300.0)
  land_sensitivity:      0.0 if protected_land_within_1km else 1.0

Data sources: OSM (schools, hospitals), EPA AirNow (AQI),
              US Census (population density), GEE (NLCD land cover)

NOTE: "environmental" in this scorer's context means proximity to sensitive things
that could complicate data center siting — not environmental impact assessment.
Fewer people nearby, farther from schools/hospitals, better air = higher score.

NOTE: This scorer reads ENVIRONMENTAL_SUB_WEIGHTS from weights.py to roll up its own
sub-metrics. It NEVER reads CATEGORY_WEIGHTS — that is the engine's job only.
"""

import logging
import math

from app.core.scoring.base import BaseScorer
from app.core.scoring.weights import ENVIRONMENTAL_SUB_WEIGHTS
from app.core.grid import generate_grid
from app.models.domain import BoundingBox, CellScore

logger = logging.getLogger(__name__)

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


class EnvironmentalScorer(BaseScorer):
    """Scores locations on population proximity, sensitive sites, air quality, and land use."""

    category_id = "environmental"

    def __init__(self, redis_client=None, settings=None):
        from app.integrations.osm import OSMClient
        from app.integrations.epa import EPAClient
        from app.integrations.census import CensusClient
        from app.integrations.gee import GEEClient
        from app.config import settings as default_settings

        self.settings = settings or default_settings
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
                )
                results.append(cs)
            except Exception as e:
                logger.warning(f"EnvironmentalScorer: cell ({cell.lat},{cell.lng}) failed: {e}")
                results.append(CellScore(lat=cell.lat, lng=cell.lng, error=str(e)))

        return results

    def _score_cell(
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
        }

        return CellScore(
            lat=cell.lat,
            lng=cell.lng,
            raw_scores={self.category_id: round(category_score, 4)},
            sub_scores=sub_scores,
            metrics=metrics,
        )

    def _extract_point_coords(self, features: list) -> list[tuple[float, float]]:
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
        """Build a (rounded_lat, rounded_lng) → class_int lookup for fast cell scoring."""
        mapping = {}
        for point in land_cover.get("grid", []):
            key = (round(point["lat"], 3), round(point["lng"], 3))
            mapping[key] = point.get("class", 82)
        return mapping
