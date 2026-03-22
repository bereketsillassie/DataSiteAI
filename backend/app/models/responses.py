"""
app/models/responses.py
────────────────────────
THE API CONTRACT — this file defines every response shape the backend sends
to the frontend. Do not change field names or types without coordinating with
the frontend partner.

The canonical reference for these types is also documented with full TypeScript
equivalents in docs/FRONTEND_INTEGRATION.md.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Any, Optional


# ── Composite Score ────────────────────────────────────────────────────────────

class CompositeScore(BaseModel):
    """
    The final weighted score for a location, plus a full breakdown of how
    it was calculated. Weights come from app/core/scoring/weights.py.
    """
    composite: float = Field(
        ...,
        ge=0.0, le=1.0,
        description="Final weighted score from 0.0 (worst) to 1.0 (best)"
    )
    weighted_contributions: dict[str, float] = Field(
        ...,
        description="How much each category contributed to the composite score. "
                    "Keys are category IDs (power, water, etc.). Values sum to composite."
    )
    weights_used: dict[str, float] = Field(
        ...,
        description="The normalized weights actually applied to each category. "
                    "These are the values from weights.py, normalized to sum to 1.0."
    )


# ── Per-Category Metric Models ─────────────────────────────────────────────────
# Each model holds the raw underlying data values for one scoring category.
# These values are BEFORE scoring — they're the actual measured quantities.

class PowerMetrics(BaseModel):
    nearest_transmission_line_km: float = Field(..., description="Distance to nearest transmission line (km)")
    nearest_substation_km: float = Field(..., description="Distance to nearest electrical substation (km)")
    electricity_rate_cents_per_kwh: float = Field(..., description="Commercial electricity rate (cents/kWh)")
    renewable_energy_pct: float = Field(..., description="% of state generation mix from renewable sources")
    grid_reliability_index: float = Field(..., description="Grid reliability score 0–100 (100=most reliable)")
    utility_territory: str = Field(..., description="Name of the electric utility serving this area")


class WaterMetrics(BaseModel):
    fema_flood_zone: str = Field(..., description="FEMA flood zone designation (X, A, AE, VE, etc.)")
    flood_risk_pct: float = Field(..., description="Flood risk as a percentage (0–100, 100=highest risk)")
    nearest_water_body_km: float = Field(..., description="Distance to nearest river, lake, or reservoir (km)")
    groundwater_availability: str = Field(..., description="Groundwater depth classification: high | moderate | low")
    drought_risk_level: str = Field(..., description="USDM drought classification: None | D0 | D1 | D2 | D3 | D4")


class GeologicalMetrics(BaseModel):
    seismic_hazard_pga: float = Field(..., description="USGS peak ground acceleration (g) — higher = more seismic risk")
    slope_degrees: float = Field(..., description="Terrain slope in degrees — steeper = harder to build on")
    elevation_m: float = Field(..., description="Elevation above sea level (meters)")
    soil_bearing_capacity: str = Field(..., description="Soil load capacity: high | moderate | low | unknown")
    nearest_wetland_km: float = Field(..., description="Distance to nearest wetland (km)")
    nearest_superfund_km: float = Field(..., description="Distance to nearest EPA Superfund site (km)")


class ClimateMetrics(BaseModel):
    avg_annual_temp_c: float = Field(..., description="Average annual temperature (°C)")
    avg_summer_temp_c: float = Field(..., description="Average summer (JJA) temperature (°C)")
    avg_humidity_pct: float = Field(..., description="Average annual relative humidity (%)")
    annual_cooling_degree_days: float = Field(..., description="Annual cooling degree days — higher = more A/C needed")
    tornado_risk_index: float = Field(..., ge=0, le=100, description="Tornado risk score 0–100")
    hurricane_risk_index: float = Field(..., ge=0, le=100, description="Hurricane risk score 0–100")
    hail_risk_index: float = Field(..., ge=0, le=100, description="Hail risk score 0–100")


class ConnectivityMetrics(BaseModel):
    fiber_routes_within_5km: int = Field(..., description="Number of fiber optic routes within 5km radius")
    nearest_ix_point_km: float = Field(..., description="Distance to nearest internet exchange point (km)")
    nearest_highway_km: float = Field(..., description="Distance to nearest highway or motorway (km)")
    nearest_airport_km: float = Field(..., description="Distance to nearest commercial airport (km)")


class EconomicMetrics(BaseModel):
    state_corporate_tax_rate_pct: float = Field(..., description="State corporate income tax rate (%)")
    data_center_tax_exemption: bool = Field(..., description="True if state has data center tax exemption or incentive program")
    permitting_difficulty: str = Field(..., description="Data center permitting environment: easy | moderate | difficult")
    median_electrician_wage_usd: float = Field(..., description="Median annual wage for electricians in this area (USD)")
    median_land_cost_per_acre_usd: float = Field(..., description="Median land cost per acre in this county (USD)")
    tech_workers_per_1000_residents: float = Field(..., description="Tech workforce density per 1,000 residents")


class EnvironmentalMetrics(BaseModel):
    population_within_5km: int = Field(..., description="Estimated population living within 5km")
    nearest_school_km: float = Field(..., description="Distance to nearest school (km)")
    nearest_hospital_km: float = Field(..., description="Distance to nearest hospital (km)")
    air_quality_index: float = Field(..., description="EPA Air Quality Index (0=good, 300+=hazardous)")
    protected_land_within_1km: bool = Field(..., description="True if any protected/conservation land is within 1km")
    land_cover_type: str = Field(..., description="NLCD 2021 land cover class name at this location")


class ScoreMetrics(BaseModel):
    """All raw metric values for a location — one sub-object per scoring category."""
    power:         PowerMetrics
    water:         WaterMetrics
    geological:    GeologicalMetrics
    climate:       ClimateMetrics
    connectivity:  ConnectivityMetrics
    economic:      EconomicMetrics
    environmental: EnvironmentalMetrics


# ── Location + Score Bundle ────────────────────────────────────────────────────

class LocationPoint(BaseModel):
    lat: float = Field(..., description="Latitude of grid cell center (WGS84)")
    lng: float = Field(..., description="Longitude of grid cell center (WGS84)")
    cell_polygon: dict = Field(..., description="GeoJSON Polygon defining this grid cell's boundary")


class ScoreBundle(BaseModel):
    """
    The complete scoring result for one grid cell location.
    This is the primary data object in the system — everything else
    is derived from or wraps a list of ScoreBundles.
    """
    location: LocationPoint
    composite_score: CompositeScore = Field(
        ...,
        description="Final weighted composite score plus full breakdown"
    )
    scores: dict[str, float] = Field(
        ...,
        description="Raw category scores (0.0–1.0) BEFORE weight application. "
                    "Keys: power, water, geological, climate, connectivity, economic, environmental"
    )
    metrics: ScoreMetrics = Field(
        ...,
        description="All underlying raw data values used to produce the scores"
    )


# ── Land Listings ──────────────────────────────────────────────────────────────

class Listing(BaseModel):
    id: str
    source: str = Field(..., description="Data source: landwatch | county_parcel")
    address: Optional[str] = None
    state: str = Field(..., description="2-letter US state code")
    county: Optional[str] = None
    acres: float
    price_usd: Optional[int] = None
    price_per_acre: Optional[float] = None
    zoning: Optional[str] = None
    coordinates: dict = Field(..., description="{ lat: float, lng: float }")
    polygon: Optional[dict] = Field(None, description="GeoJSON MultiPolygon if parcel boundary is available")
    listing_url: Optional[str] = None
    nearest_cell_scores: dict[str, float] = Field(
        ...,
        description="Scores from the nearest analyzed grid cell. "
                    "Keys: composite, power, water, geological, climate, connectivity, economic, environmental"
    )
    scraped_at: str = Field(..., description="ISO 8601 timestamp when this listing was scraped")


# ── Analysis Region ────────────────────────────────────────────────────────────

class RegionInfo(BaseModel):
    bbox: dict = Field(..., description="The bounding box that was analyzed, as a GeoJSON Polygon")
    state: str = Field(..., description="2-letter US state code")
    grid_resolution_km: float


class AnalysisMetadata(BaseModel):
    grid_cells_analyzed: int
    processing_time_ms: int
    weights_used: dict[str, float] = Field(
        ...,
        description="The category weights used for this analysis (from weights.py)"
    )
    data_freshness: dict[str, str] = Field(
        ...,
        description="ISO 8601 date strings indicating how fresh each data source is. "
                    "Keys: gee, osm, listings, eia, noaa, census"
    )
    listings_stale: bool = Field(
        False,
        description="True if listing data is older than 14 days — display a warning to the user"
    )


# ── API Response Envelopes ─────────────────────────────────────────────────────

class AnalyzeResponse(BaseModel):
    """Response from POST /api/v1/analyze"""
    analysis_id: str
    region: RegionInfo
    grid_cells: list[ScoreBundle] = Field(
        ...,
        description="All scored grid cells, sorted by composite score descending"
    )
    listings: list[Listing] = Field(
        default_factory=list,
        description="Land listings within the analysis bbox (empty if include_listings=False)"
    )
    layers_available: list[str] = Field(
        default_factory=list,
        description="Layer IDs that can be fetched via GET /layers/{layer_id}"
    )
    layer_urls: dict[str, str] = Field(
        default_factory=dict,
        description="Pre-built URLs for each available layer"
    )
    metadata: AnalysisMetadata


class ScoresResponse(BaseModel):
    """Response from GET /api/v1/scores"""
    analysis_id: str
    scores: list[ScoreBundle]


class LayerMetadata(BaseModel):
    layer_id: str
    label: str
    description: str
    geojson_url: str


class LayersListResponse(BaseModel):
    """Response from GET /api/v1/layers"""
    analysis_id: str
    layers: list[LayerMetadata]


class ListingsResponse(BaseModel):
    """Response from GET /api/v1/listings"""
    listings: list[Listing]
    total: int


class ScoringMetricSchema(BaseModel):
    id: str
    label: str
    unit: str
    lower_is_better: bool
    formula: str


class ScoringCategorySchema(BaseModel):
    id: str
    label: str
    description: str
    weight: float
    sub_weights: dict[str, float]
    metrics: list[ScoringMetricSchema]


class ScoringSchemaResponse(BaseModel):
    """Response from GET /api/v1/scoring/schema"""
    version: str
    current_weights: dict[str, float]
    categories: list[ScoringCategorySchema]
    note: str


class HealthResponse(BaseModel):
    """Response from GET /api/v1/health"""
    status: str
    db: str
    redis: str
    gee: str


# ── GeoJSON Layer Response ────────────────────────────────────────────────────
# Note: Layer endpoints return raw GeoJSON dicts, not Pydantic models,
# because GeoJSON is inherently a dict structure. The shape is documented
# here for reference and in FRONTEND_INTEGRATION.md with TypeScript types.
#
# GeoJSON FeatureCollection shape:
# {
#   "type": "FeatureCollection",
#   "metadata": {
#     "layer_id": str,
#     "label": str,
#     "score_range": [float, float],
#     "generated_at": str  # ISO 8601
#   },
#   "features": [
#     {
#       "type": "Feature",
#       "geometry": { "type": "Polygon", "coordinates": [...] },
#       "properties": {
#         "layer_id": str,
#         "score": float,       # 0.0–1.0
#         "label": str,         # Human-readable e.g. "Power: High — Substation 1.8km"
#         "color_hex": str,     # e.g. "#2ECC71"
#         "metrics": { ... }    # relevant subset of ScoreMetrics
#       }
#     }
#   ]
# }
