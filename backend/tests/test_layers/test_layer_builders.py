"""
tests/test_layers/test_layer_builders.py
─────────────────────────────────────────
Tests that all 8 layer builders produce valid GeoJSON from mock ScoreBundle data.
"""

import json
import pytest
from app.models.responses import (
    ScoreBundle, CompositeScore, LocationPoint, ScoreMetrics,
    PowerMetrics, WaterMetrics, GeologicalMetrics, ClimateMetrics,
    ConnectivityMetrics, EconomicMetrics, EnvironmentalMetrics,
)
from app.core.layers.power_layer import PowerLayerBuilder
from app.core.layers.water_layer import WaterLayerBuilder
from app.core.layers.geological_layer import GeologicalLayerBuilder
from app.core.layers.climate_layer import ClimateLayerBuilder
from app.core.layers.connectivity_layer import ConnectivityLayerBuilder
from app.core.layers.economic_layer import EconomicLayerBuilder
from app.core.layers.environmental_layer import EnvironmentalLayerBuilder
from app.core.layers.optimal_layer import OptimalLayerBuilder


def make_mock_bundle(
    lat: float = 35.9,
    lng: float = -78.9,
    composite: float = 0.75,
    power_score: float = 0.8,
) -> ScoreBundle:
    """Create a realistic mock ScoreBundle for testing."""
    return ScoreBundle(
        location=LocationPoint(
            lat=lat,
            lng=lng,
            cell_polygon={
                "type": "Polygon",
                "coordinates": [[
                    [lng - 0.023, lat - 0.023],
                    [lng + 0.023, lat - 0.023],
                    [lng + 0.023, lat + 0.023],
                    [lng - 0.023, lat + 0.023],
                    [lng - 0.023, lat - 0.023],
                ]],
            },
        ),
        composite_score=CompositeScore(
            composite=composite,
            weighted_contributions={
                "power": 0.16, "water": 0.135, "geological": 0.12,
                "climate": 0.128, "connectivity": 0.07, "economic": 0.098, "environmental": 0.05,
            },
            weights_used={
                "power": 0.20, "water": 0.15, "geological": 0.15,
                "climate": 0.15, "connectivity": 0.10, "economic": 0.15, "environmental": 0.10,
            },
        ),
        scores={
            "power": power_score, "water": 0.9, "geological": 0.8,
            "climate": 0.85, "connectivity": 0.7, "economic": 0.65, "environmental": 0.5,
        },
        metrics=ScoreMetrics(
            power=PowerMetrics(
                nearest_transmission_line_km=2.5,
                nearest_substation_km=1.8,
                electricity_rate_cents_per_kwh=8.2,
                renewable_energy_pct=22.0,
                grid_reliability_index=72.0,
                utility_territory="Duke Energy Carolinas",
            ),
            water=WaterMetrics(
                fema_flood_zone="X",
                flood_risk_pct=0.0,
                nearest_water_body_km=2.8,
                groundwater_availability="moderate",
                drought_risk_level="None",
            ),
            geological=GeologicalMetrics(
                seismic_hazard_pga=0.08,
                slope_degrees=1.5,
                elevation_m=112.0,
                soil_bearing_capacity="moderate",
                nearest_wetland_km=4.2,
                nearest_superfund_km=8.5,
            ),
            climate=ClimateMetrics(
                avg_annual_temp_c=15.2,
                avg_summer_temp_c=26.1,
                avg_humidity_pct=71.0,
                annual_cooling_degree_days=1850.0,
                tornado_risk_index=16.0,
                hurricane_risk_index=30.0,
                hail_risk_index=12.0,
            ),
            connectivity=ConnectivityMetrics(
                fiber_routes_within_5km=3,
                nearest_ix_point_km=72.0,
                nearest_highway_km=1.2,
                nearest_airport_km=18.5,
            ),
            economic=EconomicMetrics(
                state_corporate_tax_rate_pct=2.5,
                data_center_tax_exemption=True,
                permitting_difficulty="easy",
                median_electrician_wage_usd=58000.0,
                median_land_cost_per_acre_usd=8500.0,
                tech_workers_per_1000_residents=8.2,
            ),
            environmental=EnvironmentalMetrics(
                population_within_5km=4200,
                nearest_school_km=2.1,
                nearest_hospital_km=5.8,
                air_quality_index=42.0,
                protected_land_within_1km=False,
                land_cover_type="Cultivated Crops",
            ),
        ),
    )


@pytest.fixture
def mock_bundles() -> list[ScoreBundle]:
    return [
        make_mock_bundle(lat=35.9, lng=-78.9, composite=0.80, power_score=0.85),
        make_mock_bundle(lat=35.95, lng=-78.85, composite=0.65, power_score=0.60),
        make_mock_bundle(lat=35.85, lng=-78.95, composite=0.72, power_score=0.70),
    ]


ALL_BUILDERS = [
    PowerLayerBuilder(),
    WaterLayerBuilder(),
    GeologicalLayerBuilder(),
    ClimateLayerBuilder(),
    ConnectivityLayerBuilder(),
    EconomicLayerBuilder(),
    EnvironmentalLayerBuilder(),
    OptimalLayerBuilder(),
]


@pytest.mark.parametrize("builder", ALL_BUILDERS, ids=[b.layer_id for b in ALL_BUILDERS])
def test_build_returns_feature_collection(builder, mock_bundles):
    result = builder.build(mock_bundles)
    assert result["type"] == "FeatureCollection"


@pytest.mark.parametrize("builder", ALL_BUILDERS, ids=[b.layer_id for b in ALL_BUILDERS])
def test_build_is_valid_json(builder, mock_bundles):
    result = builder.build(mock_bundles)
    json_str = json.dumps(result)
    assert json.loads(json_str) == result


@pytest.mark.parametrize("builder", ALL_BUILDERS, ids=[b.layer_id for b in ALL_BUILDERS])
def test_feature_count_matches_input(builder, mock_bundles):
    result = builder.build(mock_bundles)
    assert len(result["features"]) == len(mock_bundles)


@pytest.mark.parametrize("builder", ALL_BUILDERS, ids=[b.layer_id for b in ALL_BUILDERS])
def test_features_have_required_properties(builder, mock_bundles):
    result = builder.build(mock_bundles)
    for feature in result["features"]:
        props = feature["properties"]
        assert "layer_id" in props
        assert "score" in props
        assert "label" in props
        assert "color_hex" in props
        assert "metrics" in props
        assert 0.0 <= props["score"] <= 1.0
        assert props["color_hex"].startswith("#")
        assert len(props["color_hex"]) == 7


@pytest.mark.parametrize("builder", ALL_BUILDERS, ids=[b.layer_id for b in ALL_BUILDERS])
def test_metadata_present(builder, mock_bundles):
    result = builder.build(mock_bundles)
    meta = result["metadata"]
    assert "layer_id" in meta
    assert "label" in meta
    assert "score_range" in meta
    assert "generated_at" in meta
    assert len(meta["score_range"]) == 2


@pytest.mark.parametrize("builder", ALL_BUILDERS, ids=[b.layer_id for b in ALL_BUILDERS])
def test_layer_id_matches(builder, mock_bundles):
    result = builder.build(mock_bundles)
    assert result["metadata"]["layer_id"] == builder.layer_id
    for feature in result["features"]:
        assert feature["properties"]["layer_id"] == builder.layer_id


def test_score_to_color_red():
    b = PowerLayerBuilder()
    assert b._score_to_color(0.0) == "#E74C3C"


def test_score_to_color_green():
    b = PowerLayerBuilder()
    assert b._score_to_color(1.0) == "#2ECC71"


def test_score_to_color_midpoint():
    b = PowerLayerBuilder()
    color = b._score_to_color(0.5)
    assert color == "#F39C12"


def test_score_to_color_clamping():
    b = PowerLayerBuilder()
    assert b._score_to_color(-0.5) == b._score_to_color(0.0)
    assert b._score_to_color(1.5) == b._score_to_color(1.0)


def test_optimal_layer_includes_contributions(mock_bundles):
    builder = OptimalLayerBuilder()
    result = builder.build(mock_bundles)
    for feature in result["features"]:
        assert "weighted_contributions" in feature["properties"]["metrics"]
        assert "raw_category_scores" in feature["properties"]["metrics"]


def test_empty_bundles_returns_valid_geojson():
    for builder in ALL_BUILDERS:
        result = builder.build([])
        assert result["type"] == "FeatureCollection"
        assert result["features"] == []
        assert result["metadata"]["score_range"] == [0.0, 1.0]
