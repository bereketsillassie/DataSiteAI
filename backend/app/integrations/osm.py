"""
app/integrations/osm.py
────────────────────────
OpenStreetMap Overpass API integration.
Provides: power lines, substations, fiber routes, highways, amenities.

Rate limit: 1 request/second — enforced with asyncio.sleep(1) before each call.
Cache TTL: 48 hours
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

    async def _overpass_query(self, query: str) -> dict:
        """Execute an Overpass QL query. Enforces 1 req/sec rate limit."""
        await asyncio.sleep(1.0)  # Hard rate limit — Overpass requires this
        client = await self._get_http_client()
        try:
            response = await client.post(OVERPASS_URL, data={"data": query})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise IntegrationError(source="osm", message=f"Overpass query failed: {e}")

    def _to_features(self, elements: list, geometry_type: str = "auto") -> list[dict]:
        """Convert Overpass elements to GeoJSON Feature dicts."""
        features = []
        for el in elements:
            el_type = el.get("type")
            tags = el.get("tags", {})

            if el_type == "node":
                geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
            elif el_type == "way":
                coords = [[n["lon"], n["lat"]] for n in el.get("geometry", [])]
                if len(coords) >= 2:
                    geom = {"type": "LineString", "coordinates": coords}
                else:
                    continue
            else:
                continue

            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": tags,
            })
        return features

    async def get_power_lines(self, bbox: BoundingBox) -> list[dict]:
        """
        Returns power transmission lines as GeoJSON LineString features.
        Each feature has properties: voltage, cables, name, operator.
        """
        cache_key = self._cache_key("power_lines", bbox.overpass_bbox())
        cached = await self._get_cached(cache_key)
        if cached:
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
        """
        Returns electrical substations as GeoJSON Point features.
        Each feature has properties: voltage, name, operator.
        """
        cache_key = self._cache_key("substations", bbox.overpass_bbox())
        cached = await self._get_cached(cache_key)
        if cached:
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
        """
        Returns fiber optic cable routes as GeoJSON LineString features.
        """
        cache_key = self._cache_key("fiber_routes", bbox.overpass_bbox())
        cached = await self._get_cached(cache_key)
        if cached:
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
          way["communication:telephone"="yes"]["cables"]({bbox.overpass_bbox()});
        );
        out geom;
        """
        data = await self._overpass_query(query)
        result = self._to_features(data.get("elements", []))
        await self._set_cached(cache_key, result, ttl_hours=48)
        return result

    async def get_highways(self, bbox: BoundingBox, types: Optional[list[str]] = None) -> list[dict]:
        """
        Returns road features as GeoJSON LineString features.
        types: OSM highway values to filter for. Default: motorway, trunk, primary.
        """
        if types is None:
            types = ["motorway", "trunk", "primary", "motorway_link", "trunk_link"]

        cache_key = self._cache_key("highways", bbox.overpass_bbox(), ":".join(sorted(types)))
        cached = await self._get_cached(cache_key)
        if cached:
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
        """
        Returns amenity features (schools, hospitals, etc.) as GeoJSON Point features.
        types: OSM amenity values. Default: school, hospital, university.
        """
        if types is None:
            types = ["school", "hospital", "university", "college"]

        cache_key = self._cache_key("amenities", bbox.overpass_bbox(), ":".join(sorted(types)))
        cached = await self._get_cached(cache_key)
        if cached:
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
        """2 realistic transmission lines crossing the bbox."""
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [bbox.min_lng + 0.05, clat - 0.05],
                        [bbox.max_lng - 0.05, clat + 0.05],
                    ],
                },
                "properties": {"power": "line", "voltage": "230000", "name": "Mock Transmission Line 1"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [clng - 0.1, bbox.min_lat + 0.05],
                        [clng + 0.1, bbox.max_lat - 0.05],
                    ],
                },
                "properties": {"power": "line", "voltage": "115000", "name": "Mock Transmission Line 2"},
            },
        ]

    def _mock_substations(self, bbox: BoundingBox) -> list[dict]:
        """2 substations near the center of the bbox."""
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [clng - 0.08, clat + 0.04]},
                "properties": {"power": "substation", "voltage": "230000", "name": "Mock Substation Alpha"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [clng + 0.12, clat - 0.06]},
                "properties": {"power": "substation", "voltage": "115000", "name": "Mock Substation Beta"},
            },
        ]

    def _mock_fiber_routes(self, bbox: BoundingBox) -> list[dict]:
        """3 fiber routes along mock highway corridors."""
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [bbox.min_lng + 0.02, clat],
                        [bbox.max_lng - 0.02, clat],
                    ],
                },
                "properties": {"telecom": "cable", "name": "Mock Fiber Route I-40"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [clng, bbox.min_lat + 0.02],
                        [clng, bbox.max_lat - 0.02],
                    ],
                },
                "properties": {"telecom": "cable", "name": "Mock Fiber Route US-1"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [clng - 0.15, clat - 0.1],
                        [clng + 0.2, clat + 0.1],
                    ],
                },
                "properties": {"telecom": "cable", "name": "Mock Fiber Route US-70"},
            },
        ]

    def _mock_highways(self, bbox: BoundingBox) -> list[dict]:
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [bbox.min_lng + 0.01, clat],
                        [bbox.max_lng - 0.01, clat],
                    ],
                },
                "properties": {"highway": "motorway", "ref": "I-40", "name": "Interstate 40"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [clng, bbox.min_lat + 0.01],
                        [clng, bbox.max_lat - 0.01],
                    ],
                },
                "properties": {"highway": "trunk", "ref": "US-1", "name": "US Highway 1"},
            },
        ]

    def _mock_amenities(self, bbox: BoundingBox) -> list[dict]:
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [clng - 0.05, clat + 0.08]},
                "properties": {"amenity": "school", "name": "Mock Elementary School"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [clng + 0.1, clat - 0.05]},
                "properties": {"amenity": "hospital", "name": "Mock Regional Hospital"},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [clng + 0.02, clat + 0.15]},
                "properties": {"amenity": "university", "name": "Mock State University"},
            },
        ]
