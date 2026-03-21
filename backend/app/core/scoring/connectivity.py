"""
app/core/scoring/connectivity.py
──────────────────────────────────
Connectivity scorer.

Formulas (from CLAUDE.md):
  fiber_density:     clamp(fiber_routes_within_5km / 5.0)
  ix_proximity:      1.0 - clamp(nearest_ix_km / 200.0)
  road_access:       1.0 - clamp(nearest_highway_km / 10.0)
  airport_proximity: 1.0 - clamp(nearest_airport_km / 50.0)

Data sources: OSM (fiber routes, highways), PeeringDB (internet exchanges — hardcoded
              coordinates from public dataset), FAA (airport locations — hardcoded)

NOTE: This scorer reads CONNECTIVITY_SUB_WEIGHTS from weights.py to roll up its own
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
# Internet Exchange Point locations — sourced from PeeringDB public dataset
# (lat, lng) for major US IXPs, current as of 2024
# ---------------------------------------------------------------------------
IX_POINTS: list[tuple[float, float]] = [
    (39.0438, -77.4874),   # Ashburn VA — Equinix DC (largest in Western Hemisphere)
    (38.9072, -77.0369),   # Washington DC — DC-IX
    (40.7128, -74.0060),   # New York NY — DE-CIX New York, Equinix NY
    (40.6892, -74.0445),   # Newark NJ — Equinix NY2
    (41.8781, -87.6298),   # Chicago IL — Equinix CH, AMS-IX Chicago
    (37.7749, -122.4194),  # San Francisco CA — Equinix SV, SFMIX
    (37.3861, -122.0839),  # Silicon Valley CA — Equinix SV2
    (47.6062, -122.3321),  # Seattle WA — SIX (Seattle Internet Exchange)
    (34.0522, -118.2437),  # Los Angeles CA — LAIXA, Equinix LA
    (33.4484, -112.0740),  # Phoenix AZ — Equinix PHX
    (32.7767, -96.7970),   # Dallas TX — Equinix DA, AMS-IX DFW
    (29.7604, -95.3698),   # Houston TX — Equinix HO
    (25.7617, -80.1918),   # Miami FL — NAP of the Americas
    (33.7490, -84.3880),   # Atlanta GA — Equinix AT
    (35.7796, -78.6382),   # Raleigh NC — NCIX
    (39.7392, -104.9903),  # Denver CO — IX Denver
    (45.5231, -122.6765),  # Portland OR — NWAX
    (36.1627, -86.7816),   # Nashville TN — regional exchange
    (35.1495, -90.0490),   # Memphis TN — regional exchange
    (30.3322, -81.6557),   # Jacksonville FL — regional exchange
    (43.0481, -76.1474),   # Syracuse NY — regional exchange
    (42.3601, -71.0589),   # Boston MA — BOSIX
    (39.9526, -75.1652),   # Philadelphia PA — PHL-IX
    (36.1540, -95.9928),   # Tulsa OK — regional
    (35.4676, -97.5164),   # Oklahoma City OK — regional
    (44.9778, -93.2650),   # Minneapolis MN — MICE
    (39.1031, -84.5120),   # Cincinnati OH — regional
    (41.4993, -81.6944),   # Cleveland OH — regional
    (43.0489, -76.1466),   # Rochester NY — regional
    (30.2672, -97.7431),   # Austin TX — regional
    (32.7357, -97.1081),   # Fort Worth TX — regional
    (35.2271, -80.9431),   # Charlotte NC — regional
]


# ---------------------------------------------------------------------------
# Major commercial airport locations — sourced from FAA Airport Data
# (lat, lng) for airports with scheduled commercial service
# ---------------------------------------------------------------------------
AIRPORTS: list[tuple[float, float]] = [
    # Southeast
    (35.8801, -78.7880),   # RDU — Raleigh-Durham International
    (36.0977, -79.9403),   # GSO — Piedmont Triad International (Greensboro)
    (35.2271, -80.9431),   # CLT — Charlotte Douglas International
    (33.6407, -84.4277),   # ATL — Hartsfield-Jackson Atlanta International
    (36.1340, -86.6782),   # BNA — Nashville International
    (35.0421, -85.2036),   # CHA — Chattanooga Metropolitan
    (35.0424, -78.0139),   # FAY — Fayetteville Regional
    (35.8654, -76.0135),   # ORF — Norfolk International
    # Mid-Atlantic / Northeast
    (38.9445, -77.4558),   # IAD — Dulles International
    (38.8521, -77.0379),   # DCA — Ronald Reagan National
    (39.1774, -76.6684),   # BWI — Baltimore/Washington International
    (40.6413, -73.7781),   # JFK — John F. Kennedy International
    (40.6895, -74.1745),   # EWR — Newark Liberty International
    (40.0895, -75.0105),   # PHL — Philadelphia International
    (41.9742, -87.9073),   # ORD — Chicago O'Hare International
    (41.7868, -87.7522),   # MDW — Chicago Midway International
    # Mountain / Southwest
    (39.8561, -104.6737),  # DEN — Denver International
    (33.4373, -112.0078),  # PHX — Phoenix Sky Harbor International
    (36.0840, -115.1537),  # LAS — Harry Reid International (Las Vegas)
    (35.0402, -106.6092),  # ABQ — Albuquerque International Sunport
    # Texas
    (32.8998, -97.0403),   # DFW — Dallas Fort Worth International
    (32.8481, -96.8512),   # DAL — Dallas Love Field
    (29.9902, -95.3368),   # IAH — George Bush Intercontinental (Houston)
    (29.6454, -95.2789),   # HOU — William P. Hobby (Houston)
    (30.1945, -97.6699),   # AUS — Austin-Bergstrom International
    (29.5337, -98.4698),   # SAT — San Antonio International
    # West Coast
    (37.6213, -122.3790),  # SFO — San Francisco International
    (37.3626, -121.9290),  # SJC — Norman Y. Mineta San Jose International
    (33.9425, -118.4081),  # LAX — Los Angeles International
    (47.4502, -122.3088),  # SEA — Seattle-Tacoma International
    (45.5898, -122.5951),  # PDX — Portland International
    (44.1246, -121.1507),  # RDM — Roberts Field (Redmond OR)
    # Other major hubs
    (44.8820, -93.2218),   # MSP — Minneapolis-Saint Paul International
    (39.2976, -94.7139),   # MCI — Kansas City International
    (29.9934, -90.2580),   # MSY — Louis Armstrong New Orleans International
]


class ConnectivityScorer(BaseScorer):
    """Scores locations on fiber density, internet exchange proximity, road access, and airports."""

    category_id = "connectivity"

    def __init__(self, redis_client=None, settings=None):
        from app.integrations.osm import OSMClient
        from app.config import settings as default_settings

        self.settings = settings or default_settings
        self.osm = OSMClient(redis_client=redis_client, settings=self.settings)

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """Score all grid cells in the bbox for connectivity infrastructure."""
        grid_res = getattr(self.settings, 'GRID_RESOLUTION_DEFAULT_KM', 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

        try:
            fiber_routes = await self.osm.get_fiber_routes(bbox)
        except Exception as e:
            logger.error(f"ConnectivityScorer: OSM fiber fetch failed: {e}")
            fiber_routes = []

        try:
            highways = await self.osm.get_highways(bbox)
        except Exception as e:
            logger.error(f"ConnectivityScorer: OSM highway fetch failed: {e}")
            highways = []

        # Extract midpoints from LineString features
        highway_midpoints = self._extract_line_midpoints(highways)
        fiber_midpoints = self._extract_line_midpoints(fiber_routes)

        results = []
        for cell in grid:
            try:
                cs = self._score_cell(cell, fiber_midpoints, highway_midpoints)
                results.append(cs)
            except Exception as e:
                logger.warning(f"ConnectivityScorer: cell ({cell.lat},{cell.lng}) failed: {e}")
                results.append(CellScore(lat=cell.lat, lng=cell.lng, error=str(e)))

        return results

    def _score_cell(
        self, cell, fiber_midpoints: list, highway_midpoints: list
    ) -> CellScore:
        """Score a single grid cell for connectivity factors."""

        # fiber_density: clamp(fiber_routes_within_5km / 5.0)
        # Count fiber route midpoints within 5km radius
        fiber_within_5km = sum(
            1 for (plat, plng) in fiber_midpoints
            if self._haversine_km(cell.lat, cell.lng, plat, plng) <= 5.0
        )
        fiber_score = self._clamp(fiber_within_5km / 5.0)

        # ix_proximity: 1.0 - clamp(nearest_ix_km / 200.0)
        # 0km = best (at an IX), 200km = worst practical limit
        nearest_ix_km = self._nearest_distance_km(cell.lat, cell.lng, IX_POINTS)
        ix_score = 1.0 - self._clamp(nearest_ix_km / 200.0)

        # road_access: 1.0 - clamp(nearest_highway_km / 10.0)
        # 0km = best (adjacent to highway), 10km = worst
        nearest_hwy_km = self._nearest_distance_km(cell.lat, cell.lng, highway_midpoints)
        if nearest_hwy_km == 999.0:
            nearest_hwy_km = 5.0  # Assume 5km default if no OSM highway data
        road_score = 1.0 - self._clamp(nearest_hwy_km / 10.0)

        # airport_proximity: 1.0 - clamp(nearest_airport_km / 50.0)
        # 0km = best (adjacent), 50km = worst
        nearest_airport_km = self._nearest_distance_km(cell.lat, cell.lng, AIRPORTS)
        airport_score = 1.0 - self._clamp(nearest_airport_km / 50.0)

        sub_scores = {
            "fiber_density":     round(fiber_score, 4),
            "ix_proximity":      round(ix_score, 4),
            "road_access":       round(road_score, 4),
            "airport_proximity": round(airport_score, 4),
        }

        # Roll up sub-metrics using CONNECTIVITY_SUB_WEIGHTS
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
        """Extract midpoints from GeoJSON LineString features."""
        coords = []
        for f in features:
            geom = f.get("geometry", {})
            if geom.get("type") == "LineString":
                pts = geom["coordinates"]
                if pts:
                    mid = pts[len(pts) // 2]
                    coords.append((mid[1], mid[0]))  # GeoJSON: [lng, lat] → (lat, lng)
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
