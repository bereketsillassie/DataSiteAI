"""
app/core/grid.py
─────────────────
Generates a grid of candidate locations within a bounding box.
Each grid cell is a square region at the requested resolution.

The grid is the foundation of the entire analysis — every other system
(scorers, layers, listings) operates on this set of grid cells.
"""

import math
import logging
from app.models.domain import BoundingBox, GridCell

logger = logging.getLogger(__name__)


def generate_grid(bbox: BoundingBox, cell_size_km: float = 5.0) -> list[GridCell]:
    """
    Generate a regular grid of cells covering the bounding box.

    Each cell is a square of approximately cell_size_km x cell_size_km.
    The cell center points are evenly spaced across the bbox.

    Args:
        bbox: The geographic bounding box to cover
        cell_size_km: Size of each grid cell in kilometers (default: 5km)

    Returns:
        List of GridCell objects, one per cell center point.

    Example:
        A 50x50 km bbox with 5km cells produces approximately 100 cells (10x10).
    """
    # Convert km to degrees
    # 1 degree latitude ~= 111.0 km everywhere
    lat_step = cell_size_km / 111.0

    # 1 degree longitude ~= 111.0 km * cos(latitude) at the bbox center
    center_lat = (bbox.min_lat + bbox.max_lat) / 2
    lng_step = cell_size_km / (111.0 * math.cos(math.radians(center_lat)))

    # Half-step for cell boundary calculations
    half_lat = lat_step / 2
    half_lng = lng_step / 2

    cells = []
    lat = bbox.min_lat + half_lat
    while lat <= bbox.max_lat - half_lat + 1e-9:
        lng = bbox.min_lng + half_lng
        while lng <= bbox.max_lng - half_lng + 1e-9:
            cell_polygon = {
                "type": "Polygon",
                "coordinates": [[
                    [round(lng - half_lng, 6), round(lat - half_lat, 6)],
                    [round(lng + half_lng, 6), round(lat - half_lat, 6)],
                    [round(lng + half_lng, 6), round(lat + half_lat, 6)],
                    [round(lng - half_lng, 6), round(lat + half_lat, 6)],
                    [round(lng - half_lng, 6), round(lat - half_lat, 6)],  # close ring
                ]],
            }
            cells.append(GridCell(
                lat=round(lat, 6),
                lng=round(lng, 6),
                cell_size_km=cell_size_km,
                cell_polygon=cell_polygon,
            ))
            lng += lng_step
        lat += lat_step

    logger.debug(
        f"Generated {len(cells)} grid cells at {cell_size_km}km resolution for bbox {bbox}"
    )
    return cells


def estimate_cell_count(bbox: BoundingBox, cell_size_km: float) -> int:
    """
    Estimate how many grid cells will be generated without actually generating them.
    Used for validation before running an expensive analysis.
    """
    area = bbox.area_sq_km()
    cell_area = cell_size_km ** 2
    return max(1, int(area / cell_area))
