"""
app/models/requests.py
───────────────────────
Request body and query parameter schemas for all API endpoints.
Pydantic validates all incoming data automatically.
"""

from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
import re

# Valid US state codes
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

# USA geographic bounds (approximate)
USA_MIN_LAT = 24.0
USA_MAX_LAT = 50.0
USA_MIN_LNG = -125.0
USA_MAX_LNG = -66.0


class BBoxRequest(BaseModel):
    """Geographic bounding box for the analysis area. Must be within the continental USA."""
    min_lat: float = Field(..., ge=USA_MIN_LAT, le=USA_MAX_LAT, description="South boundary (latitude)")
    min_lng: float = Field(..., ge=USA_MIN_LNG, le=USA_MAX_LNG, description="West boundary (longitude)")
    max_lat: float = Field(..., ge=USA_MIN_LAT, le=USA_MAX_LAT, description="North boundary (latitude)")
    max_lng: float = Field(..., ge=USA_MIN_LNG, le=USA_MAX_LNG, description="East boundary (longitude)")

    @model_validator(mode="after")
    def validate_bbox_orientation(self) -> "BBoxRequest":
        if self.max_lat <= self.min_lat:
            raise ValueError("max_lat must be greater than min_lat")
        if self.max_lng <= self.min_lng:
            raise ValueError("max_lng must be greater than min_lng")
        return self


class AnalyzeRequest(BaseModel):
    """Request body for POST /api/v1/analyze"""
    bbox: BBoxRequest
    state: str = Field(..., min_length=2, max_length=2, description="2-letter US state code (e.g. NC)")
    grid_resolution_km: float = Field(
        5.0,
        ge=1.0, le=25.0,
        description="Grid cell size in km. Smaller = more detail but slower. Default: 5km."
    )
    min_acres: float = Field(20.0, ge=1.0, description="Minimum parcel size for land listings (acres)")
    max_acres: Optional[float] = Field(None, ge=1.0, description="Maximum parcel size for land listings (acres)")
    include_listings: bool = Field(True, description="Whether to include land listings in the response")

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        v = v.upper()
        if v not in US_STATES:
            raise ValueError(f"'{v}' is not a valid US state code. Must be one of: {sorted(US_STATES)}")
        return v

    @model_validator(mode="after")
    def validate_bbox_area(self) -> "AnalyzeRequest":
        import math
        bbox = self.bbox
        lat_km = (bbox.max_lat - bbox.min_lat) * 111.0
        center_lat = (bbox.min_lat + bbox.max_lat) / 2
        lng_km = (bbox.max_lng - bbox.min_lng) * 111.0 * math.cos(math.radians(center_lat))
        area = abs(lat_km * lng_km)
        if area > 50000:
            raise ValueError(
                f"Bounding box area ({area:.0f} sq km) exceeds the 50,000 sq km maximum. "
                "Please select a smaller area."
            )
        return self


class ListingsQueryParams(BaseModel):
    """Query parameters for GET /api/v1/listings"""
    analysis_id: Optional[str] = None
    lat: Optional[float] = Field(None, ge=USA_MIN_LAT, le=USA_MAX_LAT)
    lng: Optional[float] = Field(None, ge=USA_MIN_LNG, le=USA_MAX_LNG)
    radius_km: Optional[float] = Field(None, ge=0.1, le=500.0)
    min_acres: Optional[float] = Field(None, ge=0.1)
    max_acres: Optional[float] = Field(None, ge=0.1)
    max_price_usd: Optional[int] = Field(None, ge=0)
    state: Optional[str] = Field(None, min_length=2, max_length=2)
    limit: int = Field(20, ge=1, le=100)

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.upper()
        if v not in US_STATES:
            raise ValueError(f"'{v}' is not a valid US state code")
        return v

    @model_validator(mode="after")
    def validate_search_params(self) -> "ListingsQueryParams":
        has_analysis = self.analysis_id is not None
        has_point = self.lat is not None and self.lng is not None
        if not has_analysis and not has_point:
            raise ValueError("Must provide either analysis_id or both lat and lng")
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat and lng must both be provided together")
        return self
