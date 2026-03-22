"""
app/integrations/fema.py
─────────────────────────
FEMA National Flood Hazard Layer (NFHL) integration.
<<<<<<< HEAD

No API key required.
Cache TTL: 30 days (flood maps change rarely).

FIX: Correct ArcGIS subdomain — old URL used hazards.fema.gov/gis/... (404)
     Current URL is hazards.fema.gov/arcgis/rest/services/...
=======
Provides flood zone polygons.

No API key required.
Cache TTL: 30 days (flood maps change rarely).
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
"""

import logging
from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

<<<<<<< HEAD
# CORRECT URL — note "arcgis" subdomain, not "gis"
FEMA_NFHL_URL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"

FLOOD_ZONE_RISK = {
    "X":    0.0,   # Minimal risk (outside 500-year floodplain)
    "X500": 0.3,   # Moderate risk (0.2% annual chance)
    "B":    0.3,   # Moderate risk (older designation)
    "C":    0.1,   # Minimal risk (older designation)
    "A":    0.7,   # High risk, no BFE determined
    "AE":   1.0,   # High risk, BFE determined
    "AH":   0.9,   # High risk, shallow flooding
    "AO":   1.0,   # High risk, sheet flow
    "AR":   0.8,   # High risk, area being restored
    "A99":  0.6,   # High risk, federally protected
    "VE":   1.0,   # Coastal high hazard
    "V":    0.95,  # Coastal high hazard (older designation)
=======
FEMA_NFHL_URL = "https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query"

# Flood zone risk mapping (higher = more flood risk)
FLOOD_ZONE_RISK = {
    "X": 0.0,         # Minimal flood risk (outside 500-year floodplain)
    "X500": 0.3,      # Moderate risk (0.2% annual chance flood)
    "B": 0.3,         # Moderate risk (same as X500 in older maps)
    "C": 0.1,         # Minimal risk (older designation, like X)
    "A": 0.7,         # High risk, 1% annual chance, no BFE determined
    "AE": 1.0,        # High risk, 1% annual chance, BFE determined
    "AH": 0.9,        # High risk, shallow flooding
    "AO": 1.0,        # High risk, sheet flow flooding
    "AR": 0.8,        # High risk, area being restored
    "A99": 0.6,       # High risk, protected by federal flood control system
    "VE": 1.0,        # Coastal high hazard, velocity wave action
    "V": 0.95,        # Coastal high hazard (older designation)
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
}


class FEMAClient(BaseIntegrationClient):
    """FEMA National Flood Hazard Layer client."""

<<<<<<< HEAD
    def __init__(self, db_session=None, settings=None):
        super().__init__(db_session, settings)
=======
    def __init__(self, redis_client=None, settings=None):
        super().__init__(redis_client, settings)
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        self.source_name = "fema"

    async def get_flood_zones(self, bbox: BoundingBox) -> list[dict]:
        """
<<<<<<< HEAD
        Returns flood zone polygons as GeoJSON Features.
        Properties: FLD_ZONE, SFHA_TF, flood_risk_score (0.0=safe, 1.0=high risk).
        """
        cache_key = self._cache_key(
            "flood_zones",
            bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng,
        )
=======
        Returns flood zone polygons as GeoJSON Feature list.
        Each feature has properties: FLD_ZONE (zone code), SFHA_TF (Special Flood Hazard Area T/F),
        and flood_risk_score (0.0=safe, 1.0=high risk).

        Returns list of GeoJSON Feature dicts (Polygon geometry).
        """
        cache_key = self._cache_key("flood_zones", bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng)
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_flood_zones(bbox)
            await self._set_cached(cache_key, result, ttl_hours=30 * 24)
            return result

        try:
            params = {
<<<<<<< HEAD
                "geometry":          f"{bbox.min_lng},{bbox.min_lat},{bbox.max_lng},{bbox.max_lat}",
                "geometryType":      "esriGeometryEnvelope",
                "inSR":              "4326",
                "outSR":             "4326",
                "spatialRel":        "esriSpatialRelIntersects",
                "outFields":         "FLD_ZONE,SFHA_TF,ZONE_SUBTY",
                "returnGeometry":    "true",
                "f":                 "geojson",
=======
                "geometry": f"{bbox.min_lng},{bbox.min_lat},{bbox.max_lng},{bbox.max_lat}",
                "geometryType": "esriGeometryEnvelope",
                "inSR": "4326",
                "outSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "FLD_ZONE,SFHA_TF,ZONE_SUBTY",
                "returnGeometry": "true",
                "f": "geojson",
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
                "resultRecordCount": 500,
            }
            data = await self._fetch_with_retry(FEMA_NFHL_URL, params=params)
            features = []
            for feat in data.get("features", []):
                props = feat.get("properties", {})
                zone = props.get("FLD_ZONE", "X")
<<<<<<< HEAD
                # Check for X500 subtype
                subty = props.get("ZONE_SUBTY", "")
                if zone == "X" and "0.2" in subty:
                    zone = "X500"
                feat["properties"]["flood_risk_score"] = FLOOD_ZONE_RISK.get(zone, 0.5)
=======
                risk = FLOOD_ZONE_RISK.get(zone, 0.5)
                feat["properties"]["flood_risk_score"] = risk
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
                features.append(feat)

            await self._set_cached(cache_key, features, ttl_hours=30 * 24)
            return features

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(source="fema", message=f"flood zone fetch failed: {e}")

    def _mock_flood_zones(self, bbox: BoundingBox) -> list[dict]:
<<<<<<< HEAD
        clng = (bbox.min_lng + bbox.max_lng) / 2
        return [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[
                    [bbox.min_lng, bbox.min_lat], [bbox.max_lng, bbox.min_lat],
                    [bbox.max_lng, bbox.max_lat], [bbox.min_lng, bbox.max_lat],
                    [bbox.min_lng, bbox.min_lat],
                ]]},
                "properties": {"FLD_ZONE": "X", "SFHA_TF": "F", "flood_risk_score": 0.0},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[
                    [clng - 0.03, bbox.min_lat], [clng + 0.03, bbox.min_lat],
                    [clng + 0.02, bbox.max_lat], [clng - 0.02, bbox.max_lat],
                    [clng - 0.03, bbox.min_lat],
                ]]},
                "properties": {"FLD_ZONE": "AE", "SFHA_TF": "T", "flood_risk_score": 1.0},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [[
                    [clng - 0.07, bbox.min_lat], [clng + 0.07, bbox.min_lat],
                    [clng + 0.06, bbox.max_lat], [clng - 0.06, bbox.max_lat],
                    [clng - 0.07, bbox.min_lat],
                ]]},
=======
        """
        Returns a realistic mix of flood zones for a NC bbox:
        - Most area is Zone X (low risk) — typical for upland NC
        - A small floodplain area shows Zone AE
        - A buffer area shows Zone X500
        """
        clat = (bbox.min_lat + bbox.max_lat) / 2
        clng = (bbox.min_lng + bbox.max_lng) / 2

        return [
            # Zone X — covers most of the bbox (upland, low risk)
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [bbox.min_lng, bbox.min_lat],
                        [bbox.max_lng, bbox.min_lat],
                        [bbox.max_lng, bbox.max_lat],
                        [bbox.min_lng, bbox.max_lat],
                        [bbox.min_lng, bbox.min_lat],
                    ]],
                },
                "properties": {"FLD_ZONE": "X", "SFHA_TF": "F", "flood_risk_score": 0.0},
            },
            # Zone AE — narrow river corridor
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [clng - 0.03, bbox.min_lat],
                        [clng + 0.03, bbox.min_lat],
                        [clng + 0.02, bbox.max_lat],
                        [clng - 0.02, bbox.max_lat],
                        [clng - 0.03, bbox.min_lat],
                    ]],
                },
                "properties": {"FLD_ZONE": "AE", "SFHA_TF": "T", "flood_risk_score": 1.0},
            },
            # Zone X500 — buffer around the AE corridor
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [clng - 0.07, bbox.min_lat],
                        [clng + 0.07, bbox.min_lat],
                        [clng + 0.06, bbox.max_lat],
                        [clng - 0.06, bbox.max_lat],
                        [clng - 0.07, bbox.min_lat],
                    ]],
                },
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
                "properties": {
                    "FLD_ZONE": "X",
                    "ZONE_SUBTY": "0.2 PCT ANNUAL CHANCE FLOOD HAZARD",
                    "SFHA_TF": "F",
                    "flood_risk_score": 0.3,
                },
            },
<<<<<<< HEAD
        ]
=======
        ]
>>>>>>> df3f91299d88c237f6a06dfe3d32900ee0c7af6e
