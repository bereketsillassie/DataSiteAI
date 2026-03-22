"""
app/core/scoring/connectivity.py
──────────────────────────────────
Connectivity scorer.

Formulas (from CLAUDE.md):
  fiber_density:     clamp(fiber_routes_within_5km / 5.0)
  ix_proximity:      1.0 - clamp(nearest_ix_km / 200.0)
  road_access:       1.0 - clamp(nearest_highway_km / 10.0)
  airport_proximity: 1.0 - clamp(nearest_airport_km / 50.0)

Data sources:
  OSM (fiber routes, highways) — fetched via get_region_data() batch
  PeeringDB IXP coords — hardcoded from public dataset
  FAA airport coords  — hardcoded

BATCHING:
  osm.get_region_data(bbox) fetches all OSM features in ONE Overpass call.
  Individual get_fiber_routes() and get_highways() calls hit the cache that
  get_region_data() populated — no additional Overpass requests.

NOTE: This scorer reads CONNECTIVITY_SUB_WEIGHTS from weights.py to roll up
sub-metrics. It NEVER reads CATEGORY_WEIGHTS — that is the engine's job only.
"""

import logging
import math

from app.core.scoring.base import BaseScorer
from app.core.scoring.weights import CONNECTIVITY_SUB_WEIGHTS
from app.core.grid import generate_grid
from app.models.domain import BoundingBox, CellScore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internet Exchange Point locations — PeeringDB public dataset, 2024
# ---------------------------------------------------------------------------
IX_POINTS: list[tuple[float, float]] = [
    (39.0438, -77.4874),   # Ashburn VA — Equinix DC
    (38.9072, -77.0369),   # Washington DC — DC-IX
    (40.7128, -74.0060),   # New York NY — DE-CIX / Equinix NY
    (40.6892, -74.0445),   # Newark NJ — Equinix NY2
    (41.8781, -87.6298),   # Chicago IL — Equinix CH / AMS-IX Chicago
    (37.7749, -122.4194),  # San Francisco CA — SFMIX
    (37.3861, -122.0839),  # Silicon Valley CA — Equinix SV2
    (47.6062, -122.3321),  # Seattle WA — SIX
    (34.0522, -118.2437),  # Los Angeles CA — LAIXA / Equinix LA
    (33.4484, -112.0740),  # Phoenix AZ — Equinix PHX
    (32.7767, -96.7970),   # Dallas TX — Equinix DA / AMS-IX DFW
    (29.7604, -95.3698),   # Houston TX — Equinix HO
    (25.7617, -80.1918),   # Miami FL — NAP of the Americas
    (33.7490, -84.3880),   # Atlanta GA — Equinix AT
    (35.7796, -78.6382),   # Raleigh NC — NCIX
    (39.7392, -104.9903),  # Denver CO — IX Denver
    (45.5231, -122.6765),  # Portland OR — NWAX
    (36.1627, -86.7816),   # Nashville TN — regional
    (35.1495, -90.0490),   # Memphis TN — regional
    (30.3322, -81.6557),   # Jacksonville FL — regional
    (42.3601, -71.0589),   # Boston MA — BOSIX
    (39.9526, -75.1652),   # Philadelphia PA — PHL-IX
    (44.9778, -93.2650),   # Minneapolis MN — MICE
    (39.1031, -84.5120),   # Cincinnati OH — regional
    (35.2271, -80.9431),   # Charlotte NC — regional
    (30.2672, -97.7431),   # Austin TX — regional
]


# ---------------------------------------------------------------------------
# Major commercial airports — FAA Airport Data
# ---------------------------------------------------------------------------
AIRPORTS: list[tuple[float, float]] = [
    (35.8801, -78.7880),   # RDU Raleigh-Durham
    (36.0977, -79.9403),   # GSO Piedmont Triad
    (35.2271, -80.9431),   # CLT Charlotte Douglas
    (33.6407, -84.4277),   # ATL Hartsfield-Jackson
    (36.1340, -86.6782),   # BNA Nashville
    (38.9445, -77.4558),   # IAD Dulles
    (38.8521, -77.0379),   # DCA Reagan National
    (39.1774, -76.6684),   # BWI Baltimore
    (40.6413, -73.7781),   # JFK
    (40.6895, -74.1745),   # EWR Newark
    (40.0895, -75.0105),   # PHL Philadelphia
    (41.9742, -87.9073),   # ORD Chicago O'Hare
    (39.8561, -104.6737),  # DEN Denver
    (33.4373, -112.0078),  # PHX Phoenix
    (36.0840, -115.1537),  # LAS Las Vegas
    (32.8998, -97.0403),   # DFW Dallas Fort Worth
    (29.9902, -95.3368),   # IAH Houston
    (30.1945, -97.6699),   # AUS Austin
    (37.6213, -122.3790),  # SFO San Francisco
    (33.9425, -118.4081),  # LAX Los Angeles
    (47.4502, -122.3088),  # SEA Seattle
    (44.8820, -93.2218),   # MSP Minneapolis
    (39.2976, -94.7139),   # MCI Kansas City
    (29.9934, -90.2580),   # MSY New Orleans
]


class ConnectivityScorer(BaseScorer):
    """Scores locations on fiber density, IXP proximity, road access, and airports."""

    category_id = "connectivity"

<<<<<<< HEAD
    def __init__(self, db_session=None, settings=None):
=======
    def __init__(self, redis_client=None, settings=None):
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        from app.integrations.osm import OSMClient
        from app.config import settings as default_settings

        self.settings = settings or default_settings
<<<<<<< HEAD
        self.osm = OSMClient(db_session=db_session, settings=self.settings)
=======
        self.osm = OSMClient(redis_client=redis_client, settings=self.settings)
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """
        Score all grid cells in the bbox for connectivity.

        OSM data is fetched via get_region_data() — ONE Overpass call for the
        whole region. Individual method calls (get_fiber_routes, get_highways)
        hit the cache that get_region_data() populated.
        """
        grid_res = getattr(self.settings, "GRID_RESOLUTION_DEFAULT_KM", 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

        # ── ONE Overpass call fetches all OSM features for the region ─────────
        try:
            osm_data = await self.osm.get_region_data(bbox)
            fiber_routes = osm_data.get("fiber_routes", [])
            highways     = osm_data.get("highways", [])
        except Exception as e:
            logger.error(f"ConnectivityScorer: OSM fetch failed: {e}")
            fiber_routes = []
            highways = []

        # Precompute midpoints once — reused for every cell
        fiber_midpoints   = self._extract_line_midpoints(fiber_routes)
        highway_midpoints = self._extract_line_midpoints(highways)

        # ── Score each cell (pure math, no API calls) ─────────────────────────
        results = []
        for cell in grid:
            try:
                cs = self._score_cell(cell, fiber_midpoints, highway_midpoints)
                results.append(cs)
            except Exception as e:
                logger.warning(f"ConnectivityScorer: cell ({cell.lat},{cell.lng}) failed: {e}")
                results.append(CellScore(lat=cell.lat, lng=cell.lng, error=str(e)))

        return results

    def _score_cell(self, cell, fiber_midpoints: list, highway_midpoints: list) -> CellScore:
        """Score a single grid cell for connectivity factors."""

        # fiber_density: count fiber midpoints within 5km
        fiber_within_5km = sum(
            1 for (plat, plng) in fiber_midpoints
            if self._haversine_km(cell.lat, cell.lng, plat, plng) <= 5.0
        )
        fiber_score = self._clamp(fiber_within_5km / 5.0)

        # ix_proximity: 0km = best, 200km = worst
        nearest_ix_km = self._nearest_distance_km(cell.lat, cell.lng, IX_POINTS)
        ix_score = 1.0 - self._clamp(nearest_ix_km / 200.0)

        # road_access: 0km = best, 10km = worst; default 5km if no OSM data
        nearest_hwy_km = self._nearest_distance_km(cell.lat, cell.lng, highway_midpoints)
        if nearest_hwy_km == 999.0:
            nearest_hwy_km = 5.0
        road_score = 1.0 - self._clamp(nearest_hwy_km / 10.0)

        # airport_proximity: 0km = best, 50km = worst
        nearest_airport_km = self._nearest_distance_km(cell.lat, cell.lng, AIRPORTS)
        airport_score = 1.0 - self._clamp(nearest_airport_km / 50.0)

        sub_scores = {
            "fiber_density":     round(fiber_score,   4),
            "ix_proximity":      round(ix_score,      4),
            "road_access":       round(road_score,    4),
            "airport_proximity": round(airport_score, 4),
        }

        category_score = self._weighted_sum(sub_scores, CONNECTIVITY_SUB_WEIGHTS)

        metrics = {
            "fiber_routes_within_5km": fiber_within_5km,
            "nearest_ix_point_km":     round(nearest_ix_km, 1),
            "nearest_highway_km":      round(nearest_hwy_km, 2),
            "nearest_airport_km":      round(nearest_airport_km, 1),
        }

        return CellScore(
            lat=cell.lat,
            lng=cell.lng,
            raw_scores={self.category_id: round(category_score, 4)},
            sub_scores=sub_scores,
            metrics=metrics,
        )

    def _extract_line_midpoints(self, features: list) -> list[tuple[float, float]]:
        coords = []
        for f in features:
            geom = f.get("geometry", {})
            if geom.get("type") == "LineString":
                pts = geom["coordinates"]
                if pts:
                    mid = pts[len(pts) // 2]
                    coords.append((mid[1], mid[0]))  # GeoJSON [lng,lat] -> (lat,lng)
        return coords

    def _nearest_distance_km(self, lat: float, lng: float, points: list) -> float:
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