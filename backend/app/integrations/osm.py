"""
app/integrations/osm.py
────────────────────────
OpenStreetMap Overpass API integration.
Provides: power lines, substations, fiber routes, highways, amenities.

Rate limit: 1 request/second enforced with asyncio.sleep(1).
Cache TTL: 48 hours

BATCHING STRATEGY:
  The Overpass API rate-limits aggressively when called once per grid cell.
  Use get_region_data(bbox) to fetch ALL OSM features for the full analysis
  region in a SINGLE Overpass call. The result is cached and all individual
  method calls (get_power_lines, get_substations, etc.) check this region
  cache first before making their own request.

  Scorers should call get_region_data() once at region level during setup,
  then call individual methods normally — they will hit the cache every time.
"""

import asyncio
import logging
from typing import Optional

from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


class OSMClient(BaseIntegrationClient):
    """OpenStreetMap Overpass API client."""

    def __init__(self, redis_client=None, settings=None):
        super().__init__(redis_client, settings)
        self.source_name = "osm"

    # ── Region-level batch fetch (call this ONCE per analysis region) ──────────

    async def get_region_data(self, bbox: BoundingBox) -> dict:
        """
        Fetch ALL OSM features for the region in a single Overpass query.
        Results are stored in Redis under per-feature-type cache keys so that
        all individual methods (get_power_lines, get_substations, etc.) find
        a cache hit when called afterward.

        Call this once before scoring starts to prevent per-cell 429 errors.

        Returns: {
            "power_lines": [...],
            "substations": [...],
            "fiber_routes": [...],
            "highways": [...],
            "amenities": [...]
        }
        """
        region_cache_key = self._cache_key("region_all", bbox.overpass_bbox())
        cached = await self._get_cached(region_cache_key)
        if cached:
            return cached

        if self.mock:
            result = {
                "power_lines":  self._mock_power_lines(bbox),
                "substations":  self._mock_substations(bbox),
                "fiber_routes": self._mock_fiber_routes(bbox),
                "highways":     self._mock_highways(bbox),
                "amenities":    self._mock_amenities(bbox),
            }
            await self._populate_sub_caches(bbox, result)
            await self._set_cached(region_cache_key, result, ttl_hours=48)
            return result

        # Single Overpass query fetching all needed feature types at once
        bb = bbox.overpass_bbox()
        query = f"""
        [out:json][timeout:60];
        (
          way["power"="line"]({bb});
          way["power"="minor_line"]({bb});
          node["power"="substation"]({bb});
          way["power"="substation"]({bb});
          way["telecom"="cable"]({bb});
          way["communication:fibre_optic"="yes"]({bb});
          way["highway"~"^(motorway|trunk|primary|motorway_link|trunk_link)$"]({bb});
          node["amenity"~"^(school|hospital|university|college)$"]({bb});
          way["amenity"~"^(school|hospital|university|college)$"]({bb});
        );
        out center geom;
        """
        data = await self._overpass_query(query)
        elements = data.get("elements", [])

        # Split elements into feature-type buckets
        power_lines, substations, fiber_routes, highways, amenities = [], [], [], [], []

        for el in elements:
            tags = el.get("tags", {})
            feature = self._element_to_feature(el)
            if feature is None:
                continue

            power_val = tags.get("power", "")
            telecom_val = tags.get("telecom", "")
            fiber_val = tags.get("communication:fibre_optic", "")
            highway_val = tags.get("highway", "")
            amenity_val = tags.get("amenity", "")

            if power_val == "line" or power_val == "minor_line":
                power_lines.append(feature)
            elif power_val == "substation":
                substations.append(feature)
            elif telecom_val == "cable" or fiber_val == "yes":
                fiber_routes.append(feature)
            elif highway_val in ("motorway", "trunk", "primary", "motorway_link", "trunk_link"):
                highways.append(feature)
            elif amenity_val in ("school", "hospital", "university", "college"):
                amenities.append(feature)

        result = {
            "power_lines":  power_lines,
            "substations":  substations,
            "fiber_routes": fiber_routes,
            "highways":     highways,
            "amenities":    amenities,
        }

        # Populate individual sub-caches so per-method calls hit cache
        await self._populate_sub_caches(bbox, result)
        await self._set_cached(region_cache_key, result, ttl_hours=48)

        logger.info(
            f"OSM region batch: {len(power_lines)} power lines, "
            f"{len(substations)} substations, {len(fiber_routes)} fiber, "
            f"{len(highways)} highways, {len(amenities)} amenities"
        )
        return result

    async def _populate_sub_caches(self, bbox: BoundingBox, data: dict) -> None:
        """Write batch results into the same cache keys used by individual methods."""
        bb = bbox.overpass_bbox()
        type_filter = "motorway:trunk:primary:motorway_link:trunk_link"
        amenity_filter = "college:hospital:school:university"

        await self._set_cached(self._cache_key("power_lines", bb),    data["power_lines"],  ttl_hours=48)
        await self._set_cached(self._cache_key("substations", bb),     data["substations"],  ttl_hours=48)
        await self._set_cached(self._cache_key("fiber_routes", bb),    data["fiber_routes"], ttl_hours=48)
        await self._set_cached(self._cache_key("highways", bb, type_filter), data["highways"], ttl_hours=48)
        await self._set_cached(self._cache_key("amenities", bb, amenity_filter), data["amenities"], ttl_hours=48)

    # ── Internal helpers ───────────────────────────────────────────────────────

    async def _overpass_query(self, query: str) -> dict:
        """Execute an Overpass QL query. Enforces 1 req/sec rate limit."""
        await asyncio.sleep(1.0)
        client = await self._get_http_client()
        try:
            response = await client.post(OVERPASS_URL, data={"data": query})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise IntegrationError(source="osm", message=f"Overpass query failed: {e}")

    def _element_to_feature(self, el: dict) -> Optional[dict]:
        """Convert a single Overpass element to a GeoJSON Feature. Returns None if unusable."""
        el_type = el.get("type")
        tags = el.get("tags", {})

        if el_type == "node":
            if "lat" not in el or "lon" not in el:
                return None
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}

        elif el_type == "way":
            # Ways with center (from "out center geom") have both center and geometry
            center = el.get("center")
            geometry = el.get("geometry", [])
            if geometry and len(geometry) >= 2:
                coords = [[n["lon"], n["lat"]] for n in geometry]
                geom = {"type": "LineString", "coordinates": coords}
            elif center:
                geom = {"type": "Point", "coordinates": [center["lon"], center["lat"]]}
            else:
                return None
        else:
            return None

        return {"type": "Feature", "geometry": geom, "properties": tags}

    def _to_features(self, elements: list) -> list[dict]:
        """Convert a list of Overpass elements to GeoJSON Features."""
        return [f for f in (self._element_to_feature(el) for el in elements) if f is not None]

    # ── Individual fetch methods (check cache first — batch fills it) ──────────

    async def get_power_lines(self, bbox: BoundingBox) -> list[dict]:
        """Returns power transmission lines as GeoJSON LineString features."""
        cache_key = self._cache_key("power_lines", bbox.overpass_bbox())
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
            result = self._mock_power_lines(bbox)
            await self._set_cached(cache_key, result, ttl_hours=48)
            return result

        query = f"""
        [out:json][timeout:25];
        (
          way["power"="line"]({bbox.overpass_bbox()});
          way["power"="minor_line"]({bbox.overpass_bbox()});
        );
        out geom;
        """
        data = await self._overpass_query(query)
        result = self._to_features(data.get("elements", []))
        await self._set_cached(cache_key, result, ttl_hours=48)
        return result

    async def get_substations(self, bbox: BoundingBox) -> list[dict]:
        """Returns electrical substations as GeoJSON Point features."""
        cache_key = self._cache_key("substations", bbox.overpass_bbox())
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
            result = self._mock_substations(bbox)
            await self._set_cached(cache_key, result, ttl_hours=48)
            return result

        query = f"""
        [out:json][timeout:25];
        (
          node["power"="substation"]({bbox.overpass_bbox()});
          way["power"="substation"]({bbox.overpass_bbox()});
        );
        out center geom;
        """
        data = await self._overpass_query(query)
        result = self._to_features(data.get("elements", []))
        await self._set_cached(cache_key, result, ttl_hours=48)
        return result

    async def get_fiber_routes(self, bbox: BoundingBox) -> list[dict]:
        """Returns fiber optic cable routes as GeoJSON LineString features."""
        cache_key = self._cache_key("fiber_routes", bbox.overpass_bbox())
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
            result = self._mock_fiber_routes(bbox)
            await self._set_cached(cache_key, result, ttl_hours=48)
            return result

        query = f"""
        [out:json][timeout:25];
        (
          way["telecom"="cable"]({bbox.overpass_bbox()});
          way["communication:fibre_optic"="yes"]({bbox.overpass_bbox()});
        );
        out geom;
        """
        data = await self._overpass_query(query)
        result = self._to_features(data.get("elements", []))
        await self._set_cached(cache_key, result, ttl_hours=48)
        return result

    async def get_highways(self, bbox: BoundingBox, types: Optional[list[str]] = None) -> list[dict]:
        """Returns road features as GeoJSON LineString features."""
        if types is None:
            types = ["motorway", "trunk", "primary", "motorway_link", "trunk_link"]

        cache_key = self._cache_key("highways", bbox.overpass_bbox(), ":".join(sorted(types)))
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
            result = self._mock_highways(bbox)
            await self._set_cached(cache_key, result, ttl_hours=48)
            return result

        type_filter = "|".join(types)
        query = f"""
        [out:json][timeout:25];
        (
          way["highway"~"^({type_filter})$"]({bbox.overpass_bbox()});
        );
        out geom;
        """
        data = await self._overpass_query(query)
        result = self._to_features(data.get("elements", []))
        await self._set_cached(cache_key, result, ttl_hours=48)
        return result

    async def get_amenities(self, bbox: BoundingBox, types: Optional[list[str]] = None) -> list[dict]:
        """Returns amenity features as GeoJSON Point features."""
        if types is None:
            types = ["school", "hospital", "university", "college"]

        cache_key = self._cache_key("amenities", bbox.overpass_bbox(), ":".join(sorted(types)))
        cached = await self._get_cached(cache_key)
        if cached is not None:
            return cached

        if self.mock:
            result = self._mock_amenities(bbox)
            await self._set_cached(cache_key, result, ttl_hours=48)
            return result

        type_filter = "|".join(types)
        query = f"""
        [out:json][timeout:25];
        (
          node["amenity"~"^({type_filter})$"]({bbox.overpass_bbox()});
          way["amenity"~"^({type_filter})$"]({bbox.overpass_bbox()});
        );
        out center geom;
        """
        data = await self._overpass_query(query)
        result = self._to_features(data.get("elements", []))
        await self._set_cached(cache_key, result, ttl_hours=48)
        return result

    # ── Mock data generators ───────────────────────────────────────────────────

    def _mock_power_lines(self, bbox: BoundingBox) -> list[dict]:
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
                [bbox.min_lng + 0.05, clat - 0.05], [bbox.max_lng - 0.05, clat + 0.05],
            ]}, "properties": {"power": "line", "voltage": "230000", "name": "Mock Transmission Line 1"}},
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
                [clng - 0.1, bbox.min_lat + 0.05], [clng + 0.1, bbox.max_lat - 0.05],
            ]}, "properties": {"power": "line", "voltage": "115000", "name": "Mock Transmission Line 2"}},
        ]

    def _mock_substations(self, bbox: BoundingBox) -> list[dict]:
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [clng - 0.08, clat + 0.04]},
             "properties": {"power": "substation", "voltage": "230000", "name": "Mock Substation Alpha"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [clng + 0.12, clat - 0.06]},
             "properties": {"power": "substation", "voltage": "115000", "name": "Mock Substation Beta"}},
        ]

    def _mock_fiber_routes(self, bbox: BoundingBox) -> list[dict]:
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
                [bbox.min_lng + 0.02, clat], [bbox.max_lng - 0.02, clat],
            ]}, "properties": {"telecom": "cable", "name": "Mock Fiber Route I-40"}},
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
                [clng, bbox.min_lat + 0.02], [clng, bbox.max_lat - 0.02],
            ]}, "properties": {"telecom": "cable", "name": "Mock Fiber Route US-1"}},
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
                [clng - 0.15, clat - 0.1], [clng + 0.2, clat + 0.1],
            ]}, "properties": {"telecom": "cable", "name": "Mock Fiber Route US-70"}},
        ]

    def _mock_highways(self, bbox: BoundingBox) -> list[dict]:
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
                [bbox.min_lng + 0.01, clat], [bbox.max_lng - 0.01, clat],
            ]}, "properties": {"highway": "motorway", "ref": "I-40", "name": "Interstate 40"}},
            {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [
                [clng, bbox.min_lat + 0.01], [clng, bbox.max_lat - 0.01],
            ]}, "properties": {"highway": "trunk", "ref": "US-1", "name": "US Highway 1"}},
        ]

    def _mock_amenities(self, bbox: BoundingBox) -> list[dict]:
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [clng - 0.05, clat + 0.08]},
             "properties": {"amenity": "school", "name": "Mock Elementary School"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [clng + 0.1, clat - 0.05]},
             "properties": {"amenity": "hospital", "name": "Mock Regional Hospital"}},
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [clng + 0.02, clat + 0.15]},
             "properties": {"amenity": "university", "name": "Mock State University"}},
        ]