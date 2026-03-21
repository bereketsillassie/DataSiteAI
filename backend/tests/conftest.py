"""
tests/conftest.py
──────────────────
Shared pytest fixtures for all tests.
All fixtures use mock data — no real DB or API connections required.
"""

import pytest
from app.models.domain import BoundingBox


@pytest.fixture
def mock_bbox() -> BoundingBox:
    """
    A bounding box covering the Research Triangle area of North Carolina.
    Used as the standard test region across all scorer and integration tests.
    """
    return BoundingBox(
        min_lat=35.7,
        min_lng=-79.2,
        max_lat=36.2,
        max_lng=-78.6,
    )


@pytest.fixture
def mock_bbox_dict() -> dict:
    """The same bbox as a dict (for API request bodies)."""
    return {
        "min_lat": 35.7,
        "min_lng": -79.2,
        "max_lat": 36.2,
        "max_lng": -78.6,
    }
