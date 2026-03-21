"""
app/db/models.py
─────────────────
SQLAlchemy ORM models for all database tables.
Schema is defined in CLAUDE.md. PostGIS geometry columns use GeoAlchemy2.
All geometries are stored in WGS84 (EPSG:4326).
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, String, Numeric, Boolean, Text, Integer,
    DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry

from app.db.session import Base


def _uuid():
    return str(uuid.uuid4())


class AnalysisRegion(Base):
    """One row per user-submitted analysis request."""
    __tablename__ = "analysis_regions"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    bbox = Column(Geometry("POLYGON", srid=4326), nullable=False)
    state = Column(String(2), nullable=False)
    grid_res_km = Column(Numeric(5, 2), nullable=False, default=5.0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    cache_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    scores = relationship("LocationScore", back_populates="region", cascade="all, delete-orphan")
    layer_cache = relationship("LayerCache", back_populates="region", cascade="all, delete-orphan")


class LocationScore(Base):
    """One row per grid cell per analysis. Stores all raw and composite scores."""
    __tablename__ = "location_scores"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    region_id = Column(UUID(as_uuid=False), ForeignKey("analysis_regions.id", ondelete="CASCADE"), nullable=False)

    # Geometry
    point = Column(Geometry("POINT", srid=4326), nullable=False)
    cell_polygon = Column(Geometry("POLYGON", srid=4326), nullable=True)

    # Composite score (weighted)
    composite_score = Column(Numeric(5, 4), nullable=True)

    # Individual raw scores (0.0–1.0, pre-weighting)
    score_power = Column(Numeric(5, 4), nullable=True)
    score_water = Column(Numeric(5, 4), nullable=True)
    score_geological = Column(Numeric(5, 4), nullable=True)
    score_climate = Column(Numeric(5, 4), nullable=True)
    score_connectivity = Column(Numeric(5, 4), nullable=True)
    score_economic = Column(Numeric(5, 4), nullable=True)
    score_environmental = Column(Numeric(5, 4), nullable=True)

    # Full metric values and weight breakdown (stored as JSON)
    metrics = Column(JSONB, nullable=True)
    composite_detail = Column(JSONB, nullable=True)  # weighted_contributions + weights_used

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationship
    region = relationship("AnalysisRegion", back_populates="scores")


class LayerCache(Base):
    """Cached GeoJSON for each layer per analysis. Avoids rebuilding on every request."""
    __tablename__ = "layer_cache"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    region_id = Column(UUID(as_uuid=False), ForeignKey("analysis_regions.id", ondelete="CASCADE"), nullable=False)
    layer_id = Column(String(50), nullable=False)
    geojson = Column(JSONB, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    region = relationship("AnalysisRegion", back_populates="layer_cache")

    __table_args__ = (
        UniqueConstraint("region_id", "layer_id", name="uq_layer_cache_region_layer"),
    )


class LandListing(Base):
    """Land parcels currently for sale, scraped from LandWatch and county portals."""
    __tablename__ = "land_listings"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    external_id = Column(String(200), nullable=True)
    source = Column(String(50), nullable=False)  # "landwatch" | "county_parcel"

    # Geometry
    point = Column(Geometry("POINT", srid=4326), nullable=True)
    polygon = Column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)

    # Listing details
    address = Column(Text, nullable=True)
    state = Column(String(2), nullable=True)
    county = Column(String(100), nullable=True)
    acres = Column(Numeric(12, 2), nullable=True)
    price_usd = Column(Integer, nullable=True)
    price_per_acre = Column(Numeric(12, 2), nullable=True)
    zoning = Column(String(200), nullable=True)
    listing_url = Column(Text, nullable=True)
    raw_data = Column(JSONB, nullable=True)
    scraped_at = Column(DateTime(timezone=True), default=datetime.utcnow)
