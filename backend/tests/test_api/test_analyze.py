"""
tests/test_api/test_analyze.py
───────────────────────────────
Integration tests for POST /api/v1/analyze and related endpoints.
Uses MOCK_INTEGRATIONS=true so no real API calls, DB, or Redis is required.

Tests are structured to work in three modes:
  1. Pure model/logic tests — no HTTP, no I/O (always pass)
  2. TestClient tests — require FastAPI app to load cleanly (pass if deps available)
  3. DB-dependent tests — skipped when DB is unavailable
"""

import pytest
from pydantic import ValidationError


# ── Model / Logic Tests (no I/O, always pass) ─────────────────────────────────

class TestAnalyzeRequestValidation:
    """Validate AnalyzeRequest Pydantic model without making any HTTP calls."""

    def test_valid_request_accepted(self):
        from app.models.requests import AnalyzeRequest, BBoxRequest

        req = AnalyzeRequest(
            bbox=BBoxRequest(min_lat=35.7, min_lng=-79.2, max_lat=36.2, max_lng=-78.6),
            state="NC",
            grid_resolution_km=5.0,
        )
        assert req.state == "NC"
        assert req.grid_resolution_km == 5.0
        assert req.include_listings is True  # default

    def test_state_is_uppercased(self):
        from app.models.requests import AnalyzeRequest, BBoxRequest

        req = AnalyzeRequest(
            bbox=BBoxRequest(min_lat=35.7, min_lng=-79.2, max_lat=36.2, max_lng=-78.6),
            state="nc",  # lowercase input
        )
        assert req.state == "NC"

    def test_invalid_state_rejected(self):
        from app.models.requests import AnalyzeRequest, BBoxRequest

        with pytest.raises(ValidationError) as exc_info:
            AnalyzeRequest(
                bbox=BBoxRequest(min_lat=35.7, min_lng=-79.2, max_lat=36.2, max_lng=-78.6),
                state="ZZ",
            )
        assert "ZZ" in str(exc_info.value)

    def test_bbox_area_too_large_rejected(self):
        """A bbox covering the entire CONUS (~13M sq km) must be rejected."""
        from app.models.requests import AnalyzeRequest, BBoxRequest

        with pytest.raises(ValidationError) as exc_info:
            AnalyzeRequest(
                bbox=BBoxRequest(min_lat=24.0, min_lng=-125.0, max_lat=50.0, max_lng=-66.0),
                state="NC",
            )
        assert "50,000" in str(exc_info.value) or "50000" in str(exc_info.value)

    def test_inverted_bbox_rejected(self):
        """max_lat must be greater than min_lat."""
        from app.models.requests import AnalyzeRequest, BBoxRequest

        with pytest.raises(ValidationError):
            AnalyzeRequest(
                bbox=BBoxRequest(min_lat=36.2, min_lng=-79.2, max_lat=35.7, max_lng=-78.6),
                state="NC",
            )

    def test_grid_resolution_bounds(self):
        """grid_resolution_km must be between 1 and 25."""
        from app.models.requests import AnalyzeRequest, BBoxRequest

        with pytest.raises(ValidationError):
            AnalyzeRequest(
                bbox=BBoxRequest(min_lat=35.7, min_lng=-79.2, max_lat=36.2, max_lng=-78.6),
                state="NC",
                grid_resolution_km=0.5,  # below minimum of 1.0
            )

        with pytest.raises(ValidationError):
            AnalyzeRequest(
                bbox=BBoxRequest(min_lat=35.7, min_lng=-79.2, max_lat=36.2, max_lng=-78.6),
                state="NC",
                grid_resolution_km=30.0,  # above maximum of 25.0
            )

    def test_dc_state_code_accepted(self):
        """DC is a valid state code in this system."""
        from app.models.requests import AnalyzeRequest, BBoxRequest

        req = AnalyzeRequest(
            bbox=BBoxRequest(min_lat=38.7, min_lng=-77.2, max_lat=39.2, max_lng=-76.8),
            state="DC",
        )
        assert req.state == "DC"


class TestBoundingBox:
    """Test BoundingBox domain object."""

    def test_center(self):
        from app.models.domain import BoundingBox

        bbox = BoundingBox(min_lat=35.7, min_lng=-79.2, max_lat=36.2, max_lng=-78.6)
        center = bbox.center()
        assert abs(center[0] - 35.95) < 0.01
        assert abs(center[1] - (-78.9)) < 0.01

    def test_to_geojson_polygon_structure(self):
        from app.models.domain import BoundingBox

        bbox = BoundingBox(min_lat=35.7, min_lng=-79.2, max_lat=36.2, max_lng=-78.6)
        geojson = bbox.to_geojson_polygon()
        assert geojson["type"] == "Polygon"
        coords = geojson["coordinates"][0]
        assert len(coords) == 5  # closed ring
        assert coords[0] == coords[-1]  # first == last

    def test_area_sq_km_reasonable(self):
        from app.models.domain import BoundingBox

        bbox = BoundingBox(min_lat=35.7, min_lng=-79.2, max_lat=36.2, max_lng=-78.6)
        area = bbox.area_sq_km()
        # Research Triangle area is roughly 3,000–4,000 sq km
        assert 2000 < area < 6000


# ── Scoring Schema Tests (no I/O) ─────────────────────────────────────────────

class TestScoringSchemaEndpoint:
    """Test the scoring schema response structure."""

    def test_scoring_schema_response_model_structure(self):
        from app.models.responses import ScoringSchemaResponse, ScoringCategorySchema, ScoringMetricSchema

        schema = ScoringSchemaResponse.model_json_schema()
        props = schema["properties"]
        assert "version" in props
        assert "current_weights" in props
        assert "categories" in props
        assert "note" in props

    def test_weights_come_from_weights_py(self):
        """Verify that weights.py exports the expected keys."""
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
        expected_categories = {
            "power", "water", "geological", "climate",
            "connectivity", "economic", "environmental",
        }
        assert set(CATEGORY_WEIGHTS.keys()) == expected_categories
        assert all(isinstance(v, float) for v in CATEGORY_WEIGHTS.values())
        assert all(v > 0 for v in CATEGORY_WEIGHTS.values())

    def test_sub_weights_sum_to_one(self):
        """Each sub-weight dict must sum to 1.0 (within floating point tolerance)."""
        from app.core.scoring.weights import (
            POWER_SUB_WEIGHTS, WATER_SUB_WEIGHTS, GEOLOGICAL_SUB_WEIGHTS,
            CLIMATE_SUB_WEIGHTS, CONNECTIVITY_SUB_WEIGHTS, ECONOMIC_SUB_WEIGHTS,
            ENVIRONMENTAL_SUB_WEIGHTS,
        )
        for name, weights in [
            ("POWER", POWER_SUB_WEIGHTS),
            ("WATER", WATER_SUB_WEIGHTS),
            ("GEOLOGICAL", GEOLOGICAL_SUB_WEIGHTS),
            ("CLIMATE", CLIMATE_SUB_WEIGHTS),
            ("CONNECTIVITY", CONNECTIVITY_SUB_WEIGHTS),
            ("ECONOMIC", ECONOMIC_SUB_WEIGHTS),
            ("ENVIRONMENTAL", ENVIRONMENTAL_SUB_WEIGHTS),
        ]:
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.001, f"{name}_SUB_WEIGHTS sum={total}, expected 1.0"


# ── Response Model Tests (no I/O) ─────────────────────────────────────────────

class TestResponseModels:
    """Verify response model schemas match the API contract."""

    def test_health_response_has_required_fields(self):
        from app.models.responses import HealthResponse

        schema = HealthResponse.model_json_schema()
        props = schema["properties"]
        assert "status" in props
        assert "db" in props
        assert "redis" in props
        assert "gee" in props

    def test_score_bundle_structure(self):
        from app.models.responses import ScoreBundle

        schema = ScoreBundle.model_json_schema()
        props = schema["properties"]
        assert "location" in props
        assert "composite_score" in props
        assert "scores" in props
        assert "metrics" in props

    def test_composite_score_bounds(self):
        from app.models.responses import CompositeScore

        score = CompositeScore(
            composite=0.75,
            weighted_contributions={"power": 0.15, "water": 0.1},
            weights_used={"power": 0.2, "water": 0.15},
        )
        assert score.composite == 0.75

        # composite must be 0.0–1.0
        with pytest.raises(ValidationError):
            CompositeScore(
                composite=1.5,  # out of range
                weighted_contributions={},
                weights_used={},
            )

    def test_listing_model_accepts_none_fields(self):
        """Optional fields in Listing must accept None."""
        from app.models.responses import Listing

        listing = Listing(
            id="test_001",
            source="landwatch",
            address=None,
            state="NC",
            county=None,
            acres=50.0,
            price_usd=None,
            price_per_acre=None,
            zoning=None,
            coordinates={"lat": 35.9, "lng": -78.9},
            polygon=None,
            listing_url=None,
            nearest_cell_scores={"composite": 0.75},
            scraped_at="2026-03-01T12:00:00+00:00",
        )
        assert listing.price_usd is None
        assert listing.county is None


# ── Listing Service Mock Tests (no I/O) ────────────────────────────────────────

class TestListingServiceMock:
    """Test ListingService with mock mode enabled."""

    @pytest.mark.asyncio
    async def test_mock_listings_near_returns_results(self):
        from unittest.mock import MagicMock
        from app.core.listings.listing_service import ListingService

        mock_settings = MagicMock()
        mock_settings.MOCK_INTEGRATIONS = True

        service = ListingService(db_session=None, settings=mock_settings)
        listings, is_stale = await service.get_listings_near(
            lat=35.95,
            lng=-78.9,
            radius_km=200.0,  # large radius to capture all mock listings
        )
        assert len(listings) > 0
        assert is_stale is False  # mock data is always fresh

    @pytest.mark.asyncio
    async def test_mock_listings_near_attaches_scores(self):
        from unittest.mock import MagicMock
        from app.core.listings.listing_service import ListingService
        from app.models.responses import ScoreBundle, CompositeScore, LocationPoint, ScoreMetrics
        from app.models.responses import (
            PowerMetrics, WaterMetrics, GeologicalMetrics, ClimateMetrics,
            ConnectivityMetrics, EconomicMetrics, EnvironmentalMetrics,
        )

        mock_settings = MagicMock()
        mock_settings.MOCK_INTEGRATIONS = True

        # Build a minimal ScoreBundle for score attachment
        mock_bundle = ScoreBundle(
            location=LocationPoint(
                lat=35.9,
                lng=-78.9,
                cell_polygon={"type": "Polygon", "coordinates": [[]]},
            ),
            composite_score=CompositeScore(
                composite=0.82,
                weighted_contributions={"power": 0.16},
                weights_used={"power": 0.20},
            ),
            scores={"power": 0.8, "water": 0.9},
            metrics=ScoreMetrics(
                power=PowerMetrics(
                    nearest_transmission_line_km=2.0,
                    nearest_substation_km=1.5,
                    electricity_rate_cents_per_kwh=8.5,
                    renewable_energy_pct=20.0,
                    grid_reliability_index=85.0,
                    utility_territory="Duke Energy",
                ),
                water=WaterMetrics(
                    fema_flood_zone="X",
                    flood_risk_pct=0.0,
                    nearest_water_body_km=2.0,
                    groundwater_availability="moderate",
                    drought_risk_level="None",
                ),
                geological=GeologicalMetrics(
                    seismic_hazard_pga=0.05,
                    slope_degrees=1.5,
                    elevation_m=90.0,
                    soil_bearing_capacity="moderate",
                    nearest_wetland_km=4.0,
                    nearest_superfund_km=12.0,
                ),
                climate=ClimateMetrics(
                    avg_annual_temp_c=14.5,
                    avg_summer_temp_c=25.0,
                    avg_humidity_pct=68.0,
                    annual_cooling_degree_days=1400.0,
                    tornado_risk_index=15.0,
                    hurricane_risk_index=25.0,
                    hail_risk_index=10.0,
                ),
                connectivity=ConnectivityMetrics(
                    fiber_routes_within_5km=3,
                    nearest_ix_point_km=75.0,
                    nearest_highway_km=2.5,
                    nearest_airport_km=20.0,
                ),
                economic=EconomicMetrics(
                    state_corporate_tax_rate_pct=2.5,
                    data_center_tax_exemption=True,
                    permitting_difficulty="easy",
                    median_electrician_wage_usd=55000.0,
                    median_land_cost_per_acre_usd=8000.0,
                    tech_workers_per_1000_residents=9.0,
                ),
                environmental=EnvironmentalMetrics(
                    population_within_5km=4500,
                    nearest_school_km=3.5,
                    nearest_hospital_km=6.0,
                    air_quality_index=40.0,
                    protected_land_within_1km=False,
                    land_cover_type="Cultivated Crops",
                ),
            ),
        )

        service = ListingService(db_session=None, settings=mock_settings)
        listings, _ = await service.get_listings_near(
            lat=35.95,
            lng=-78.9,
            radius_km=200.0,
            score_bundles=[mock_bundle],
        )
        assert len(listings) > 0
        for listing in listings:
            assert "composite" in listing.nearest_cell_scores
            assert listing.nearest_cell_scores["composite"] == 0.82

    @pytest.mark.asyncio
    async def test_mock_listings_for_region(self):
        from unittest.mock import MagicMock
        from app.core.listings.listing_service import ListingService

        mock_settings = MagicMock()
        mock_settings.MOCK_INTEGRATIONS = True

        service = ListingService(db_session=None, settings=mock_settings)
        listings, is_stale = await service.get_listings_in_region(
            analysis_id="mock-analysis-id-123",
        )
        assert isinstance(listings, list)
        assert is_stale is False


# ── LandWatch Scraper Mock Tests (no I/O) ─────────────────────────────────────

class TestLandWatchScraperMock:
    """Test LandWatchScraper mock mode."""

    @pytest.mark.asyncio
    async def test_mock_returns_five_nc_listings(self):
        from unittest.mock import MagicMock
        from app.core.listings.landwatch_scraper import LandWatchScraper

        mock_settings = MagicMock()
        mock_settings.MOCK_INTEGRATIONS = True

        scraper = LandWatchScraper(settings=mock_settings)
        listings = await scraper.scrape_state("NC")

        assert len(listings) == 5
        for listing in listings:
            assert listing["source"] == "landwatch"
            assert listing["state"] == "NC"
            assert listing["acres"] > 20.0
            assert listing["lat"] is not None
            assert listing["lng"] is not None

    @pytest.mark.asyncio
    async def test_mock_state_code_uppercased(self):
        from unittest.mock import MagicMock
        from app.core.listings.landwatch_scraper import LandWatchScraper

        mock_settings = MagicMock()
        mock_settings.MOCK_INTEGRATIONS = True

        scraper = LandWatchScraper(settings=mock_settings)
        listings = await scraper.scrape_state("nc")  # lowercase
        assert all(l["state"] == "NC" for l in listings)

    def test_mock_listings_have_all_required_fields(self):
        from unittest.mock import MagicMock
        from app.core.listings.landwatch_scraper import LandWatchScraper

        mock_settings = MagicMock()
        mock_settings.MOCK_INTEGRATIONS = True

        scraper = LandWatchScraper(settings=mock_settings)
        listings = scraper._mock_listings("NC")

        required_fields = {"source", "state", "acres", "lat", "lng", "scraped_at"}
        for listing in listings:
            missing = required_fields - set(listing.keys())
            assert not missing, f"Listing missing fields: {missing}"


# ── County Parcel Fetcher Mock Tests (no I/O) ─────────────────────────────────

class TestCountyParcelFetcherMock:
    """Test CountyParcelFetcher mock mode."""

    @pytest.mark.asyncio
    async def test_mock_returns_parcels(self):
        from unittest.mock import MagicMock
        from app.core.listings.county_parcel_fetcher import CountyParcelFetcher

        mock_settings = MagicMock()
        mock_settings.MOCK_INTEGRATIONS = True

        fetcher = CountyParcelFetcher(settings=mock_settings)
        parcels = await fetcher.fetch_state_parcels("NC", min_acres=20.0)

        assert len(parcels) > 0
        for parcel in parcels:
            assert parcel["source"] == "county_parcel"
            assert parcel["acres"] >= 20.0
            assert parcel["lat"] is not None

    @pytest.mark.asyncio
    async def test_unsupported_state_returns_empty_in_real_mode(self):
        from unittest.mock import MagicMock
        from app.core.listings.county_parcel_fetcher import CountyParcelFetcher

        mock_settings = MagicMock()
        mock_settings.MOCK_INTEGRATIONS = False  # real mode

        fetcher = CountyParcelFetcher(settings=mock_settings)
        # WY has no source configured
        parcels = await fetcher.fetch_state_parcels("WY")
        assert parcels == []


# ── Haversine Distance Tests ───────────────────────────────────────────────────

class TestHaversineDistance:
    """Test the haversine distance utility used by listing service."""

    def test_same_point_is_zero(self):
        from app.core.listings.listing_service import _haversine_km

        dist = _haversine_km(35.95, -78.9, 35.95, -78.9)
        assert dist < 0.001

    def test_known_distance(self):
        from app.core.listings.listing_service import _haversine_km

        # Raleigh, NC to Durham, NC is approximately 34 km
        dist = _haversine_km(35.7796, -78.6382, 35.9940, -78.8986)
        assert 30 < dist < 40
