"""
app/api/v1/scoring_schema.py
─────────────────────────────
GET /api/v1/scoring/schema — full scoring system schema with current weights.

IMPORTANT: This endpoint imports weights from weights.py at request time,
not at module load time. This ensures the response always reflects the
currently deployed weights — even if the scoring partner edits and redeploys
without a full service restart.

Never hardcode weight values in this file. Import them directly from weights.py.
"""

import logging

from fastapi import APIRouter

from app.models.responses import (
    ScoringSchemaResponse,
    ScoringCategorySchema,
    ScoringMetricSchema,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get(
    "/scoring/schema",
    response_model=ScoringSchemaResponse,
    summary="Get the scoring system schema and current weights",
    description=(
        "Returns all scoring categories, sub-metrics with formulas, and current weights. "
        "Weights are read directly from weights.py at runtime — this endpoint always "
        "reflects the currently deployed weights, never hardcoded values."
    ),
)
async def get_scoring_schema() -> ScoringSchemaResponse:
    # Import weights at request time so changes to weights.py are reflected immediately
    from app.core.scoring.weights import (
        CATEGORY_WEIGHTS,
        POWER_SUB_WEIGHTS,
        WATER_SUB_WEIGHTS,
        GEOLOGICAL_SUB_WEIGHTS,
        CLIMATE_SUB_WEIGHTS,
        CONNECTIVITY_SUB_WEIGHTS,
        ECONOMIC_SUB_WEIGHTS,
        ENVIRONMENTAL_SUB_WEIGHTS,
    )

    categories = [
        ScoringCategorySchema(
            id="power",
            label="Power & Energy",
            description=(
                "Scores proximity to electrical grid infrastructure, commercial electricity cost, "
                "renewable energy percentage in the state's generation mix, and grid reliability (SAIDI). "
                "Critical for data center operational costs and uptime."
            ),
            weight=CATEGORY_WEIGHTS["power"],
            sub_weights=POWER_SUB_WEIGHTS,
            metrics=[
                ScoringMetricSchema(
                    id="nearest_substation_km",
                    label="Distance to nearest substation",
                    unit="km",
                    lower_is_better=True,
                    formula="1.0 - clamp(distance / 20.0)",
                ),
                ScoringMetricSchema(
                    id="nearest_transmission_line_km",
                    label="Distance to nearest transmission line",
                    unit="km",
                    lower_is_better=True,
                    formula="1.0 - clamp(min(dist_substation_km, dist_line_km) / 20.0)",
                ),
                ScoringMetricSchema(
                    id="electricity_rate_cents_per_kwh",
                    label="Commercial electricity rate",
                    unit="cents/kWh",
                    lower_is_better=True,
                    formula="1.0 - clamp((rate_cents - 5.0) / 15.0)  # 5c=best, 20c=worst",
                ),
                ScoringMetricSchema(
                    id="renewable_energy_pct",
                    label="Renewable energy percentage",
                    unit="%",
                    lower_is_better=False,
                    formula="renewable_pct / 100.0",
                ),
                ScoringMetricSchema(
                    id="grid_reliability_index",
                    label="Grid reliability index (SAIDI-based)",
                    unit="0-100",
                    lower_is_better=False,
                    formula="reliability_index / 100.0",
                ),
            ],
        ),
        ScoringCategorySchema(
            id="water",
            label="Water & Flood Risk",
            description=(
                "Scores FEMA flood zone designation, proximity to water bodies needed for cooling, "
                "and USDM drought risk. Flooding and drought both threaten data center continuity."
            ),
            weight=CATEGORY_WEIGHTS["water"],
            sub_weights=WATER_SUB_WEIGHTS,
            metrics=[
                ScoringMetricSchema(
                    id="fema_flood_zone",
                    label="FEMA flood zone designation",
                    unit="zone code",
                    lower_is_better=False,
                    formula="Zone X->1.0, Zone B/X500->0.7, Zone A->0.3, Zone AE/VE/AO->0.0",
                ),
                ScoringMetricSchema(
                    id="nearest_water_body_km",
                    label="Distance to nearest water body",
                    unit="km",
                    lower_is_better=True,
                    formula="1.0 - clamp(distance / 10.0) + 0.2 bonus if groundwater=high",
                ),
                ScoringMetricSchema(
                    id="drought_risk_level",
                    label="USDM drought level",
                    unit="D0-D4",
                    lower_is_better=True,
                    formula="None->1.0, D0->0.9, D1->0.7, D2->0.5, D3->0.2, D4->0.0",
                ),
            ],
        ),
        ScoringCategorySchema(
            id="geological",
            label="Geological & Terrain",
            description=(
                "Scores USGS seismic hazard (peak ground acceleration), terrain slope, "
                "soil bearing capacity, and distance from wetlands and Superfund sites. "
                "Geological stability reduces construction risk and long-term foundation costs."
            ),
            weight=CATEGORY_WEIGHTS["geological"],
            sub_weights=GEOLOGICAL_SUB_WEIGHTS,
            metrics=[
                ScoringMetricSchema(
                    id="seismic_hazard_pga",
                    label="Seismic hazard (USGS PGA)",
                    unit="g",
                    lower_is_better=True,
                    formula="1.0 - clamp(pga_g / 2.0)",
                ),
                ScoringMetricSchema(
                    id="slope_degrees",
                    label="Terrain slope",
                    unit="degrees",
                    lower_is_better=True,
                    formula="1.0 - clamp(slope_degrees / 15.0)",
                ),
                ScoringMetricSchema(
                    id="soil_bearing_capacity",
                    label="Soil bearing capacity",
                    unit="category",
                    lower_is_better=False,
                    formula="high->1.0, moderate->0.6, low->0.2, unknown->0.5",
                ),
                ScoringMetricSchema(
                    id="nearest_wetland_km",
                    label="Distance to nearest wetland / Superfund site",
                    unit="km",
                    lower_is_better=False,
                    formula="clamp(min(wetland_km, superfund_km) / 5.0)",
                ),
            ],
        ),
        ScoringCategorySchema(
            id="climate",
            label="Climate & Weather Risk",
            description=(
                "Scores natural cooling efficiency (cooling degree days), ambient humidity, "
                "and severe weather risk including tornado, hurricane, and hail events "
                "per 100 sq km over 30 years (NOAA storm events data)."
            ),
            weight=CATEGORY_WEIGHTS["climate"],
            sub_weights=CLIMATE_SUB_WEIGHTS,
            metrics=[
                ScoringMetricSchema(
                    id="annual_cooling_degree_days",
                    label="Annual cooling degree days",
                    unit="CDD",
                    lower_is_better=True,
                    formula="1.0 - clamp((annual_cdd - 500) / 3500)  # 500=best, 4000=worst",
                ),
                ScoringMetricSchema(
                    id="avg_humidity_pct",
                    label="Average relative humidity",
                    unit="%",
                    lower_is_better=True,
                    formula="1.0 - clamp((avg_rh_pct - 30) / 60)  # 30%=best, 90%=worst",
                ),
                ScoringMetricSchema(
                    id="tornado_risk_index",
                    label="Tornado risk index",
                    unit="0-100",
                    lower_is_better=True,
                    formula="1.0 - clamp(tornado_events_per_100sqkm_30yr / 5.0)",
                ),
                ScoringMetricSchema(
                    id="hurricane_risk_index",
                    label="Hurricane risk index",
                    unit="0-100",
                    lower_is_better=True,
                    formula="1.0 - clamp(hurricane_proximity_score / 1.0)",
                ),
                ScoringMetricSchema(
                    id="hail_risk_index",
                    label="Hail risk index",
                    unit="0-100",
                    lower_is_better=True,
                    formula="1.0 - clamp(hail_events_per_100sqkm_30yr / 10.0)",
                ),
            ],
        ),
        ScoringCategorySchema(
            id="connectivity",
            label="Connectivity & Access",
            description=(
                "Scores fiber optic infrastructure density within 5km, distance to internet "
                "exchange points (PeeringDB), highway access for logistics, and airport proximity "
                "for personnel and equipment."
            ),
            weight=CATEGORY_WEIGHTS["connectivity"],
            sub_weights=CONNECTIVITY_SUB_WEIGHTS,
            metrics=[
                ScoringMetricSchema(
                    id="fiber_routes_within_5km",
                    label="Fiber routes within 5km radius",
                    unit="count",
                    lower_is_better=False,
                    formula="clamp(fiber_routes_within_5km / 5.0)",
                ),
                ScoringMetricSchema(
                    id="nearest_ix_point_km",
                    label="Distance to nearest internet exchange point",
                    unit="km",
                    lower_is_better=True,
                    formula="1.0 - clamp(nearest_ix_km / 200.0)",
                ),
                ScoringMetricSchema(
                    id="nearest_highway_km",
                    label="Distance to nearest highway",
                    unit="km",
                    lower_is_better=True,
                    formula="1.0 - clamp(nearest_highway_km / 10.0)",
                ),
                ScoringMetricSchema(
                    id="nearest_airport_km",
                    label="Distance to nearest commercial airport",
                    unit="km",
                    lower_is_better=True,
                    formula="1.0 - clamp(nearest_airport_km / 50.0)",
                ),
            ],
        ),
        ScoringCategorySchema(
            id="economic",
            label="Economic Environment",
            description=(
                "Scores state corporate tax rate, data center-specific tax exemptions, "
                "median land cost per acre, tech labor market density, and permitting "
                "ease for large commercial/industrial projects."
            ),
            weight=CATEGORY_WEIGHTS["economic"],
            sub_weights=ECONOMIC_SUB_WEIGHTS,
            metrics=[
                ScoringMetricSchema(
                    id="state_corporate_tax_rate_pct",
                    label="State corporate income tax rate",
                    unit="%",
                    lower_is_better=True,
                    formula="1.0 - clamp(rate / 12.0) + 0.2 bonus if state has DC tax exemption",
                ),
                ScoringMetricSchema(
                    id="median_land_cost_per_acre_usd",
                    label="Median land cost per acre",
                    unit="USD",
                    lower_is_better=True,
                    formula="1.0 - clamp(price_per_acre_usd / 50000)",
                ),
                ScoringMetricSchema(
                    id="tech_workers_per_1000_residents",
                    label="Tech workers per 1,000 residents",
                    unit="workers",
                    lower_is_better=False,
                    formula="clamp(tech_workers_per_1000 / 20.0)",
                ),
                ScoringMetricSchema(
                    id="permitting_difficulty",
                    label="Permitting difficulty",
                    unit="category",
                    lower_is_better=True,
                    formula="easy->1.0, moderate->0.6, difficult->0.2",
                ),
            ],
        ),
        ScoringCategorySchema(
            id="environmental",
            label="Environmental Impact",
            description=(
                "Scores population proximity (noise/light impact), distance from sensitive "
                "receptors (schools, hospitals), EPA AirNow air quality index, and whether "
                "protected or conservation land is adjacent to the site."
            ),
            weight=CATEGORY_WEIGHTS["environmental"],
            sub_weights=ENVIRONMENTAL_SUB_WEIGHTS,
            metrics=[
                ScoringMetricSchema(
                    id="population_within_5km",
                    label="Population within 5km",
                    unit="persons",
                    lower_is_better=True,
                    formula="1.0 - clamp(population_within_5km / 50000)",
                ),
                ScoringMetricSchema(
                    id="nearest_school_km",
                    label="Distance to nearest school / hospital",
                    unit="km",
                    lower_is_better=False,
                    formula="clamp(min(nearest_school_km, nearest_hospital_km) / 2.0)",
                ),
                ScoringMetricSchema(
                    id="air_quality_index",
                    label="EPA Air Quality Index (AQI)",
                    unit="AQI",
                    lower_is_better=True,
                    formula="1.0 - clamp(aqi / 300.0)",
                ),
                ScoringMetricSchema(
                    id="protected_land_within_1km",
                    label="Protected land within 1km",
                    unit="boolean",
                    lower_is_better=True,
                    formula="0.0 if protected_land_within_1km else 1.0",
                ),
            ],
        ),
    ]

    return ScoringSchemaResponse(
        version="1.0",
        current_weights=dict(CATEGORY_WEIGHTS),
        categories=categories,
        note=(
            "Weights are applied server-side only. "
            "To change weights: edit app/core/scoring/weights.py and redeploy to Cloud Run. "
            "See docs/SCORING_INTERNALS.md for full documentation."
        ),
    )
