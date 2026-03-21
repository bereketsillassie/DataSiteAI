"""
app/integrations/gee.py
────────────────────────
Google Earth Engine integration.
Provides: land cover, elevation, NDVI, surface temperature.

Real mode: Uses the GEE Python SDK with a service account key.
Mock mode: Returns a 10x10 grid of realistic values for a North Carolina bbox.

Cache TTL: 7 days (GEE data is static — NLCD updates every ~2 years)
"""

import logging
from typing import Optional

from app.integrations.base import BaseIntegrationClient
from app.models.domain import BoundingBox, IntegrationError

logger = logging.getLogger(__name__)

# NLCD 2021 land cover class names, keyed by integer class value
NLCD_CLASS_NAMES = {
    11: "Open Water",
    12: "Perennial Ice/Snow",
    21: "Developed, Open Space",
    22: "Developed, Low Intensity",
    23: "Developed, Medium Intensity",
    24: "Developed, High Intensity",
    31: "Barren Land",
    41: "Deciduous Forest",
    42: "Evergreen Forest",
    43: "Mixed Forest",
    52: "Shrub/Scrub",
    71: "Grassland/Herbaceous",
    81: "Pasture/Hay",
    82: "Cultivated Crops",
    90: "Woody Wetlands",
    95: "Emergent Herbaceous Wetlands",
}


class GEEClient(BaseIntegrationClient):
    """Google Earth Engine client for raster data retrieval."""

    def __init__(self, redis_client=None, settings=None):
        super().__init__(redis_client, settings)
        self.source_name = "gee"
        self._initialized = False

    def _ensure_initialized(self):
        """Initialize GEE SDK with service account credentials."""
        if self._initialized or self.mock:
            return
        try:
            import ee
            credentials = ee.ServiceAccountCredentials(
                email=self.settings.GEE_SERVICE_ACCOUNT,
                key_file=self.settings.GEE_KEY_FILE,
            )
            ee.Initialize(credentials)
            self._initialized = True
            logger.info("GEE initialized with service account")
        except Exception as e:
            raise IntegrationError(source="gee", message=f"GEE initialization failed: {e}")

    async def get_land_cover(self, bbox: BoundingBox) -> dict:
        """
        Returns NLCD 2021 land cover class for each point in a grid.

        Returns: {
            "grid": [{"lat": float, "lng": float, "class": int, "class_name": str}]
        }
        """
        cache_key = self._cache_key("land_cover", bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng)
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_land_cover(bbox)
            await self._set_cached(cache_key, result, ttl_hours=self.settings.GEE_CACHE_TTL_HOURS)
            return result

        self._ensure_initialized()
        try:
            import ee
            region = ee.Geometry.Rectangle([bbox.min_lng, bbox.min_lat, bbox.max_lng, bbox.max_lat])
            nlcd = ee.ImageCollection("USGS/NLCD_RELEASES/2021_REL/NLCD").first().select("landcover")

            sample = nlcd.sample(
                region=region,
                scale=30,
                numPixels=100,
                geometries=True,
            ).getInfo()

            grid = []
            for feat in sample.get("features", []):
                coords = feat["geometry"]["coordinates"]
                lc_class = feat["properties"].get("landcover", 82)
                grid.append({
                    "lat": coords[1],
                    "lng": coords[0],
                    "class": lc_class,
                    "class_name": NLCD_CLASS_NAMES.get(lc_class, "Unknown"),
                })

            result = {"grid": grid}
            await self._set_cached(cache_key, result, ttl_hours=self.settings.GEE_CACHE_TTL_HOURS)
            return result

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(source="gee", message=f"land cover fetch failed: {e}")

    async def get_elevation(self, bbox: BoundingBox) -> dict:
        """
        Returns SRTM 30m elevation grid.

        Returns: {
            "grid": [{"lat": float, "lng": float, "elevation_m": float, "slope_degrees": float}]
        }
        """
        cache_key = self._cache_key("elevation", bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng)
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_elevation(bbox)
            await self._set_cached(cache_key, result, ttl_hours=self.settings.GEE_CACHE_TTL_HOURS)
            return result

        self._ensure_initialized()
        try:
            import ee
            region = ee.Geometry.Rectangle([bbox.min_lng, bbox.min_lat, bbox.max_lng, bbox.max_lat])
            srtm = ee.Image("USGS/SRTMGL1_003")
            slope = ee.Terrain.slope(srtm)
            combined = srtm.addBands(slope)

            sample = combined.sample(region=region, scale=90, numPixels=100, geometries=True).getInfo()

            grid = []
            for feat in sample.get("features", []):
                coords = feat["geometry"]["coordinates"]
                grid.append({
                    "lat": coords[1],
                    "lng": coords[0],
                    "elevation_m": feat["properties"].get("elevation", 100),
                    "slope_degrees": feat["properties"].get("slope", 2.0),
                })

            result = {"grid": grid}
            await self._set_cached(cache_key, result, ttl_hours=self.settings.GEE_CACHE_TTL_HOURS)
            return result

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(source="gee", message=f"elevation fetch failed: {e}")

    async def get_ndvi(self, bbox: BoundingBox) -> dict:
        """
        Returns Sentinel-2 NDVI (vegetation index). Range: -1.0 to 1.0.
        High NDVI = dense vegetation. Low = bare ground, developed, water.

        Returns: {"grid": [{"lat": float, "lng": float, "ndvi": float}]}
        """
        cache_key = self._cache_key("ndvi", bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng)
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_ndvi(bbox)
            await self._set_cached(cache_key, result, ttl_hours=self.settings.GEE_CACHE_TTL_HOURS)
            return result

        self._ensure_initialized()
        try:
            import ee
            region = ee.Geometry.Rectangle([bbox.min_lng, bbox.min_lat, bbox.max_lng, bbox.max_lat])
            s2 = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                  .filterBounds(region)
                  .filterDate("2023-01-01", "2023-12-31")
                  .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
                  .median())
            ndvi = s2.normalizedDifference(["B8", "B4"]).rename("ndvi")
            sample = ndvi.sample(region=region, scale=100, numPixels=100, geometries=True).getInfo()

            grid = [
                {
                    "lat": f["geometry"]["coordinates"][1],
                    "lng": f["geometry"]["coordinates"][0],
                    "ndvi": round(f["properties"].get("ndvi", 0.3), 4),
                }
                for f in sample.get("features", [])
            ]

            result = {"grid": grid}
            await self._set_cached(cache_key, result, ttl_hours=self.settings.GEE_CACHE_TTL_HOURS)
            return result

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(source="gee", message=f"NDVI fetch failed: {e}")

    async def get_surface_temp(self, bbox: BoundingBox) -> dict:
        """
        Returns MODIS land surface temperature (LST) in Celsius.

        Returns: {"grid": [{"lat": float, "lng": float, "lst_celsius": float}]}
        """
        cache_key = self._cache_key("surface_temp", bbox.min_lat, bbox.min_lng, bbox.max_lat, bbox.max_lng)
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        if self.mock:
            result = self._mock_surface_temp(bbox)
            await self._set_cached(cache_key, result, ttl_hours=self.settings.GEE_CACHE_TTL_HOURS)
            return result

        self._ensure_initialized()
        try:
            import ee
            region = ee.Geometry.Rectangle([bbox.min_lng, bbox.min_lat, bbox.max_lng, bbox.max_lat])
            modis_lst = (ee.ImageCollection("MODIS/061/MOD11A2")
                         .filterBounds(region)
                         .filterDate("2023-06-01", "2023-08-31")
                         .select("LST_Day_1km")
                         .median())
            # MODIS LST is stored in Kelvin * 0.02; convert to Celsius
            lst_c = modis_lst.multiply(0.02).subtract(273.15).rename("lst_celsius")
            sample = lst_c.sample(region=region, scale=1000, numPixels=100, geometries=True).getInfo()

            grid = [
                {
                    "lat": f["geometry"]["coordinates"][1],
                    "lng": f["geometry"]["coordinates"][0],
                    "lst_celsius": round(f["properties"].get("lst_celsius", 28.0), 2),
                }
                for f in sample.get("features", [])
            ]

            result = {"grid": grid}
            await self._set_cached(cache_key, result, ttl_hours=self.settings.GEE_CACHE_TTL_HOURS)
            return result

        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(source="gee", message=f"surface temp fetch failed: {e}")

    # ── Mock data generators ───────────────────────────────────────────────────

    def _mock_grid_points(self, bbox: BoundingBox, n: int = 10) -> list[tuple[float, float]]:
        """Generate an n×n grid of (lat, lng) points within the bbox."""
        lats = [bbox.min_lat + (bbox.max_lat - bbox.min_lat) * i / (n - 1) for i in range(n)]
        lngs = [bbox.min_lng + (bbox.max_lng - bbox.min_lng) * j / (n - 1) for j in range(n)]
        return [(lat, lng) for lat in lats for lng in lngs]

    def _mock_land_cover(self, bbox: BoundingBox) -> dict:
        points = self._mock_grid_points(bbox)
        # Mix of classes typical for NC: mostly crops/pasture/forest, some developed
        classes = [82, 82, 81, 41, 42, 21, 22, 52, 71, 82]
        return {
            "grid": [
                {
                    "lat": lat,
                    "lng": lng,
                    "class": classes[i % len(classes)],
                    "class_name": NLCD_CLASS_NAMES[classes[i % len(classes)]],
                }
                for i, (lat, lng) in enumerate(points)
            ]
        }

    def _mock_elevation(self, bbox: BoundingBox) -> dict:
        points = self._mock_grid_points(bbox)
        return {
            "grid": [
                {
                    "lat": lat,
                    "lng": lng,
                    "elevation_m": round(80 + (i % 7) * 15, 1),
                    "slope_degrees": round(1.5 + (i % 5) * 0.8, 2),
                }
                for i, (lat, lng) in enumerate(points)
            ]
        }

    def _mock_ndvi(self, bbox: BoundingBox) -> dict:
        points = self._mock_grid_points(bbox)
        return {
            "grid": [
                {"lat": lat, "lng": lng, "ndvi": round(0.35 + (i % 6) * 0.08, 4)}
                for i, (lat, lng) in enumerate(points)
            ]
        }

    def _mock_surface_temp(self, bbox: BoundingBox) -> dict:
        points = self._mock_grid_points(bbox)
        return {
            "grid": [
                {"lat": lat, "lng": lng, "lst_celsius": round(28.5 + (i % 5) * 1.2, 2)}
                for i, (lat, lng) in enumerate(points)
            ]
        }
