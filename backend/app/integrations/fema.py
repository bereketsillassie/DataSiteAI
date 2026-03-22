"""
app/integrations/fema.py
─────────────────────────
FEMA National Flood Hazard Layer (NFHL) integration.

No API key required.
Cache TTL: 30 days (flood maps change rarely).

FIX: Correct ArcGIS subdomain — old URL used hazards.fema.gov/gis/... (404)
     Current URL is hazards.fema.gov/arcgis/rest/services/...
"""

import logging
from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

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
}


class FEMAClient(BaseIntegrationClient):
    """FEMA National Flood Hazard Layer client."""

    def __init__(self, db_session=None, settings=None):
        super().__init__(db_session, settings)
        self.source_name = "fema"

    async def get_flood_zones(self, bbox: BoundingBox) -> list[dict]:
        """
        Returns flood zone polygons as GeoJSON Features.
        Properties: FLD_ZONE, SFHA_TF, flood_risk_score (0.0=safe, 1.0=high risk).
        """
        cache_key = self._cache_key(
            "flood_zones",
            bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng,
        )
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_flood_zones(bbox)
            await self._set_cached(cache_key, result, ttl_hours=30 * 24)
            return result

        try:
            params = {
                "geometry":          f"{bbox.min_lng},{bbox.min_lat},{bbox.max_lng},{bbox.max_lat}",
                "geometryType":      "esriGeometryEnvelope",
                "inSR":              "4326",
                "outSR":             "4326",
                "spatialRel":        "esriSpatialRelIntersects",
                "outFields":         "FLD_ZONE,SFHA_TF,ZONE_SUBTY",
                "returnGeometry":    "true",
                "f":                 "geojson",
                "resultRecordCount": 500,
            }
            data = await self._fetch_with_retry(FEMA_NFHL_URL, params=params)
            features = []
            for feat in data.get("features", []):
                props = feat.get("properties", {})
                zone = props.get("FLD_ZONE", "X")
                # Check for X500 subtype
                subty = props.get("ZONE_SUBTY", "")
                if zone == "X" and "0.2" in subty:
                    zone = "X500"
                feat["properties"]["flood_risk_score"] = FLOOD_ZONE_RISK.get(zone, 0.5)
                features.append(feat)

            await self._set_cached(cache_key, features, ttl_hours=30 * 24)
            return features

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(source="fema", message=f"flood zone fetch failed: {e}")

    def _mock_flood_zones(self, bbox: BoundingBox) -> list[dict]:
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
                "properties": {
                    "FLD_ZONE": "X",
                    "ZONE_SUBTY": "0.2 PCT ANNUAL CHANCE FLOOD HAZARD",
                    "SFHA_TF": "F",
                    "flood_risk_score": 0.3,
                },
            },
        ]