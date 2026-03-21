"""
tests/test_scoring/test_engine.py
──────────────────────────────────
Tests for the ScoringEngine.
All tests use mock scorers — no real API calls, no real integration clients.

Run with:
  pytest tests/test_scoring/test_engine.py -v
or:
  MOCK_INTEGRATIONS=true pytest tests/test_scoring/test_engine.py -v
"""

import pytest
from unittest.mock import MagicMock

from app.models.domain import BoundingBox, CellScore
from app.core.scoring.engine import ScoringEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bbox():
    """A small bbox over the Research Triangle area of North Carolina."""
    return BoundingBox(min_lat=35.7, min_lng=-79.2, max_lat=36.2, max_lng=-78.6)


def make_mock_scorer(category_id: str, score_value: float = 0.75):
    """
    Create a mock scorer that returns a fixed score for every grid cell.
    Uses a 25km grid resolution to keep test execution fast.
    """
    scorer = MagicMock()
    scorer.category_id = category_id

    async def mock_score(bbox):
        from app.core.grid import generate_grid
        # Large cell size = fewer cells = faster tests
        grid = generate_grid(bbox, cell_size_km=25.0)
        return [
            CellScore(
                lat=cell.lat,
                lng=cell.lng,
                raw_scores={category_id: score_value},
                sub_scores={f"{category_id}_test_sub": score_value},
                metrics={},
            )
            for cell in grid
        ]

    scorer.score = mock_score
    return scorer


CATEGORY_IDS = [
    "power", "water", "geological", "climate",
    "connectivity", "economic", "environmental"
]


@pytest.fixture
def engine_with_uniform_scorers():
    """Engine where all scorers return 0.75 — composite should be ~0.75."""
    return ScoringEngine(
        power_scorer=make_mock_scorer("power", 0.75),
        water_scorer=make_mock_scorer("water", 0.75),
        geological_scorer=make_mock_scorer("geological", 0.75),
        climate_scorer=make_mock_scorer("climate", 0.75),
        connectivity_scorer=make_mock_scorer("connectivity", 0.75),
        economic_scorer=make_mock_scorer("economic", 0.75),
        environmental_scorer=make_mock_scorer("environmental", 0.75),
    )


@pytest.fixture
def engine_with_varied_scorers():
    """Engine with different scores per category for testing weight application."""
    return ScoringEngine(
        power_scorer=make_mock_scorer("power", 0.80),
        water_scorer=make_mock_scorer("water", 0.90),
        geological_scorer=make_mock_scorer("geological", 0.70),
        climate_scorer=make_mock_scorer("climate", 0.85),
        connectivity_scorer=make_mock_scorer("connectivity", 0.60),
        economic_scorer=make_mock_scorer("economic", 0.75),
        environmental_scorer=make_mock_scorer("environmental", 0.95),
    )


# ---------------------------------------------------------------------------
# Engine integration tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_region_returns_bundles(engine_with_uniform_scorers, mock_bbox):
    """score_region should return at least one ScoreBundle."""
    bundles = await engine_with_uniform_scorers.score_region(mock_bbox, grid_resolution_km=25.0)
    assert len(bundles) > 0, "Expected at least one ScoreBundle from score_region"


@pytest.mark.asyncio
async def test_composite_score_in_range(engine_with_varied_scorers, mock_bbox):
    """Every composite score must be in [0.0, 1.0]."""
    bundles = await engine_with_varied_scorers.score_region(mock_bbox, grid_resolution_km=25.0)
    for b in bundles:
        assert 0.0 <= b.composite_score.composite <= 1.0, (
            f"Composite score {b.composite_score.composite} out of range for cell "
            f"({b.location.lat}, {b.location.lng})"
        )


@pytest.mark.asyncio
async def test_sorted_by_composite_descending(engine_with_varied_scorers, mock_bbox):
    """Bundles must be sorted by composite score, highest first."""
    bundles = await engine_with_varied_scorers.score_region(mock_bbox, grid_resolution_km=25.0)
    scores = [b.composite_score.composite for b in bundles]
    assert scores == sorted(scores, reverse=True), (
        "ScoreBundles must be sorted by composite score descending"
    )


@pytest.mark.asyncio
async def test_weights_used_sum_to_one(engine_with_varied_scorers, mock_bbox):
    """The normalized weights_used must sum to exactly 1.0."""
    bundles = await engine_with_varied_scorers.score_region(mock_bbox, grid_resolution_km=25.0)
    assert len(bundles) > 0

    weights_used = bundles[0].composite_score.weights_used
    total = sum(weights_used.values())
    assert abs(total - 1.0) < 0.001, (
        f"Normalized weights_used should sum to 1.0, got {total:.6f}. "
        f"weights_used = {weights_used}"
    )


@pytest.mark.asyncio
async def test_all_seven_categories_present_in_scores(engine_with_varied_scorers, mock_bbox):
    """Each ScoreBundle.scores should contain all 7 category keys."""
    bundles = await engine_with_varied_scorers.score_region(mock_bbox, grid_resolution_km=25.0)
    assert len(bundles) > 0

    scores = bundles[0].scores
    expected_categories = {"power", "water", "geological", "climate", "connectivity", "economic", "environmental"}
    assert set(scores.keys()) == expected_categories, (
        f"Expected categories {expected_categories}, got {set(scores.keys())}"
    )


@pytest.mark.asyncio
async def test_uniform_scores_produce_same_composite(engine_with_uniform_scorers, mock_bbox):
    """
    When all scorers return the same score (0.75), the composite should also be ~0.75,
    regardless of how the weights are set (as long as they're all non-zero).
    """
    bundles = await engine_with_uniform_scorers.score_region(mock_bbox, grid_resolution_km=25.0)
    assert len(bundles) > 0

    composite = bundles[0].composite_score.composite
    assert abs(composite - 0.75) < 0.001, (
        f"All category scores are 0.75, so composite should be ~0.75, got {composite}"
    )


@pytest.mark.asyncio
async def test_bundle_has_location_and_metrics(engine_with_varied_scorers, mock_bbox):
    """Each ScoreBundle must have location, composite_score, scores, and metrics."""
    bundles = await engine_with_varied_scorers.score_region(mock_bbox, grid_resolution_km=25.0)
    assert len(bundles) > 0
    b = bundles[0]

    assert b.location is not None
    assert b.location.lat is not None
    assert b.location.lng is not None
    assert b.location.cell_polygon is not None
    assert b.composite_score is not None
    assert b.scores is not None
    assert b.metrics is not None


@pytest.mark.asyncio
async def test_cell_polygon_is_valid_geojson(engine_with_varied_scorers, mock_bbox):
    """cell_polygon must be a valid GeoJSON Polygon dict."""
    bundles = await engine_with_varied_scorers.score_region(mock_bbox, grid_resolution_km=25.0)
    assert len(bundles) > 0

    polygon = bundles[0].location.cell_polygon
    assert polygon.get("type") == "Polygon", f"Expected Polygon, got {polygon.get('type')}"
    assert "coordinates" in polygon
    ring = polygon["coordinates"][0]
    assert len(ring) >= 4, "Polygon ring must have at least 4 points (3 + closing)"
    # First and last points must be the same (closed ring)
    assert ring[0] == ring[-1], "GeoJSON Polygon ring must be closed (first == last point)"


# ---------------------------------------------------------------------------
# _apply_weights unit tests — test the weight math directly
# ---------------------------------------------------------------------------

def make_minimal_engine():
    """Create an engine with stub scorers for unit testing _apply_weights."""
    scorers = [make_mock_scorer(cat) for cat in CATEGORY_IDS]
    return ScoringEngine(*scorers)


def test_apply_weights_equal_scores_equal_weights():
    """Equal scores + equal weights → composite equals the score."""
    engine = make_minimal_engine()
    raw = {"power": 0.8, "water": 0.8}
    weights = {"power": 1.0, "water": 1.0}
    result = engine._apply_weights(raw, weights)
    assert abs(result.composite - 0.8) < 0.001, (
        f"Equal scores and equal weights should produce composite = score value, got {result.composite}"
    )


def test_apply_weights_asymmetric():
    """power=1.0, water=0.0, equal weights → composite = 0.5."""
    engine = make_minimal_engine()
    raw = {"power": 1.0, "water": 0.0}
    weights = {"power": 1.0, "water": 1.0}
    result = engine._apply_weights(raw, weights)
    assert abs(result.composite - 0.5) < 0.001, (
        f"Scores 1.0 and 0.0 with equal weights → composite should be 0.5, got {result.composite}"
    )


def test_apply_weights_zero_weight_excludes_category():
    """A weight of 0.0 should completely exclude that category."""
    engine = make_minimal_engine()
    raw = {"power": 0.9, "water": 0.0}
    weights = {"power": 1.0, "water": 0.0}  # water is disabled
    result = engine._apply_weights(raw, weights)
    # Only power contributes, so composite should equal the power score
    assert abs(result.composite - 0.9) < 0.001, (
        f"Zero-weight category should be excluded. Expected 0.9, got {result.composite}"
    )
    assert "water" not in result.weights_used, "Zero-weight category should not appear in weights_used"


def test_apply_weights_contributions_sum_to_composite():
    """The weighted_contributions values should sum to the composite score."""
    engine = make_minimal_engine()
    raw = {"power": 0.8, "water": 0.6, "geological": 0.9}
    weights = {"power": 0.4, "water": 0.3, "geological": 0.3}
    result = engine._apply_weights(raw, weights)
    contributions_sum = sum(result.weighted_contributions.values())
    assert abs(contributions_sum - result.composite) < 0.001, (
        f"weighted_contributions should sum to composite. "
        f"Sum={contributions_sum:.6f}, composite={result.composite:.6f}"
    )


def test_apply_weights_normalized_weights_sum_to_one():
    """weights_used should always sum to 1.0 regardless of input weight magnitudes."""
    engine = make_minimal_engine()
    # Use large non-normalized values
    raw = {"power": 0.7, "economic": 0.8, "connectivity": 0.5}
    weights = {"power": 200.0, "economic": 150.0, "connectivity": 50.0}
    result = engine._apply_weights(raw, weights)
    total = sum(result.weights_used.values())
    assert abs(total - 1.0) < 0.001, (
        f"weights_used should sum to 1.0 after normalization, got {total:.6f}"
    )


def test_apply_weights_empty_scores_returns_zero():
    """Empty raw_scores should return composite=0.0."""
    engine = make_minimal_engine()
    result = engine._apply_weights({}, {"power": 0.2, "water": 0.15})
    assert result.composite == 0.0
    assert result.weights_used == {}
    assert result.weighted_contributions == {}


# ---------------------------------------------------------------------------
# Architecture guard: CATEGORY_WEIGHTS must not appear in individual scorer files
# ---------------------------------------------------------------------------

def test_category_weights_not_in_scorer_files():
    """
    Verifies that individual scorer files do not USE CATEGORY_WEIGHTS in code.
    Only engine.py is allowed to import/use CATEGORY_WEIGHTS.
    This test enforces the architectural rule from CLAUDE.md.

    Note: docstring MENTIONS of CATEGORY_WEIGHTS (for documentation) are allowed.
    This test uses AST inspection to detect actual code usage, not string search.
    """
    import ast
    import os

    scorer_files = [
        "app/core/scoring/power.py",
        "app/core/scoring/water.py",
        "app/core/scoring/geological.py",
        "app/core/scoring/climate.py",
        "app/core/scoring/connectivity.py",
        "app/core/scoring/economic.py",
        "app/core/scoring/environmental.py",
    ]

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    for fname in scorer_files:
        path = os.path.join(base_dir, fname)
        if not os.path.exists(path):
            continue  # File not yet created — skip

        with open(path) as f:
            source = f.read()

        tree = ast.parse(source)

        # Check for actual Name node references (real usage, not docstring mentions)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "CATEGORY_WEIGHTS":
                raise AssertionError(
                    f"{fname} line {node.lineno}: Must NOT use CATEGORY_WEIGHTS in code. "
                    f"Only engine.py is allowed to apply category weights. "
                    f"See CLAUDE.md Critical Rules."
                )
            if isinstance(node, ast.ImportFrom):
                if any(alias.name == "CATEGORY_WEIGHTS" for alias in node.names):
                    raise AssertionError(
                        f"{fname} line {node.lineno}: Must NOT import CATEGORY_WEIGHTS. "
                        f"Only engine.py is allowed to apply category weights. "
                        f"See CLAUDE.md Critical Rules."
                    )
