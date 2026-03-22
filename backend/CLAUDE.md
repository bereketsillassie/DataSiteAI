# CLAUDE.md — DataCenter Site Selector Backend

> This file is the single source of truth for Claude Code when building this project.
> Read this entire file before writing a single line of code.
> When in doubt about any decision, refer back here first.

---

## Project Overview

You are building the backend for **DataCenter Site Selector** — a SaaS tool that analyzes geographic, environmental, utility, economic, and geological data to score and rank land across the USA for suitability as data center locations. After scoring, the system finds land currently for sale near the best-scoring locations and returns everything to a frontend map UI.

**This is the backend only.** A separate frontend engineer is consuming your API. Your job is clean, well-documented code with a rock-solid API contract.

---

## Team & Ownership

| Role | Owns |
|---|---|
| Backend engineer (you) | Everything in this repo |
| Frontend engineer (partner) | Map UI, layer toggles, score display |
| Scoring engineer (partner) | `app/core/scoring/weights.py` only — edits weights and redeploys |

---

## Core Philosophy — Read This First

1. **The backend computes all scores and applies all weights.** The frontend receives finished scores and renders them. It never does math.
2. **Weights live in one file only:** `app/core/scoring/weights.py`. No weight values anywhere else in the codebase. Ever.
3. **Individual scorers never touch weights.** Each scorer returns raw `0.0–1.0` scores. Only `engine.py` applies weights.
4. **Every metric must produce both a score AND a GeoJSON layer.** The frontend map needs to toggle any individual metric as an overlay.
5. **All data sources are 100% free.** No paid APIs. No exceptions.
6. **Mock mode must exist for every integration.** Set `MOCK_INTEGRATIONS=true` and the entire system runs without any real API keys. The frontend partner needs this to build locally.
7. **WGS84 (EPSG:4326) everywhere.** All coordinates, all geometries, no exceptions.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Framework | **FastAPI** (async) | Auto-generates OpenAPI docs at `/docs` |
| Language | **Python 3.11+** | GEE SDK, shapely, rasterio are Python-native |
| Database | **PostgreSQL 15 + PostGIS** | Hosted on Supabase free tier (500MB) |
| Cache | **Redis** via Upstash | Free tier — 10K requests/day |
| Raster processing | **rasterio + rio-tiler** | Serve COG tiles from GCS |
| Geospatial | **Shapely + GeoPandas** | All vector operations |
| Storage | **Google Cloud Storage** | GEE exports + GeoJSON cache |
| Hosting | **Cloud Run** | Serverless, free tier: 2M requests/month |
| Jobs | **Cloud Run Jobs** | Scheduled ingestion — no always-on server |
| Scraping | **httpx + BeautifulSoup** | Land listing acquisition |
| Migrations | **Alembic** | Schema versioning |
| Testing | **pytest + pytest-asyncio** | Every scorer has isolated tests with mock data |

---

## Project Structure

Build this exact structure. Do not deviate.

```
datacenter-site-selector/
├── CLAUDE.md                            ← this file
├── README.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── .env.example
├── alembic.ini
│
├── app/
│   ├── main.py                          ← FastAPI app + router registration
│   ├── config.py                        ← Settings via pydantic-settings
│   ├── dependencies.py                  ← DB session, Redis, auth deps
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── router.py                ← Mounts all v1 sub-routers
│   │       ├── analyze.py               ← POST /analyze
│   │       ├── layers.py                ← GET /layers, GET /layers/{layer_id}
│   │       ├── scores.py                ← GET /scores
│   │       ├── listings.py              ← GET /listings
│   │       ├── scoring_schema.py        ← GET /scoring/schema
│   │       └── health.py                ← GET /health
│   │
│   ├── core/
│   │   ├── scoring/
│   │   │   ├── weights.py               ← ONLY file scoring partner edits
│   │   │   ├── base.py                  ← BaseScorer abstract class
│   │   │   ├── engine.py                ← Orchestrates scorers + applies weights
│   │   │   ├── power.py
│   │   │   ├── water.py
│   │   │   ├── geological.py
│   │   │   ├── climate.py
│   │   │   ├── connectivity.py
│   │   │   ├── economic.py
│   │   │   └── environmental.py
│   │   │
│   │   ├── layers/
│   │   │   ├── base.py                  ← BaseLayerBuilder abstract class
│   │   │   ├── power_layer.py
│   │   │   ├── water_layer.py
│   │   │   ├── geological_layer.py
│   │   │   ├── climate_layer.py
│   │   │   ├── connectivity_layer.py
│   │   │   ├── economic_layer.py
│   │   │   ├── environmental_layer.py
│   │   │   └── optimal_layer.py         ← Uses composite_score.composite
│   │   │
│   │   ├── listings/
│   │   │   ├── landwatch_scraper.py
│   │   │   ├── county_parcel_fetcher.py
│   │   │   └── listing_service.py
│   │   │
│   │   └── grid.py                      ← Generates candidate location grid from bbox
│   │
│   ├── integrations/
│   │   ├── base.py                      ← BaseIntegrationClient with mock support
│   │   ├── gee.py                       ← Google Earth Engine
│   │   ├── osm.py                       ← OpenStreetMap Overpass
│   │   ├── fema.py                      ← FEMA Flood Hazard Layer
│   │   ├── usgs.py                      ← USGS seismic + elevation
│   │   ├── eia.py                       ← Energy Information Administration
│   │   ├── noaa.py                      ← NOAA Climate Data Online
│   │   ├── census.py                    ← US Census Bureau
│   │   ├── nasa_power.py                ← NASA POWER climate API
│   │   └── epa.py                       ← EPA Superfund + AirNow + NWI
│   │
│   ├── models/
│   │   ├── domain.py                    ← Internal domain types (BoundingBox, CellScore, etc.)
│   │   ├── requests.py                  ← API request schemas
│   │   └── responses.py                 ← API response schemas — the frontend contract
│   │
│   └── db/
│       ├── session.py                   ← Async SQLAlchemy session factory
│       ├── models.py                    ← ORM models
│       └── migrations/                  ← Alembic migration files
│
├── jobs/
│   ├── ingest_gee.py                    ← GEE raster export → GCS (weekly)
│   ├── ingest_osm.py                    ← OSM vector data → PostGIS (weekly)
│   ├── ingest_listings.py               ← LandWatch scrape → DB (weekly)
│   └── ingest_economic.py               ← EIA + Census + NOAA → DB (monthly)
│
├── tests/
│   ├── conftest.py                      ← Shared fixtures, mock bbox, mock responses
│   ├── test_scoring/
│   │   ├── test_engine.py
│   │   ├── test_power.py
│   │   ├── test_water.py
│   │   ├── test_geological.py
│   │   ├── test_climate.py
│   │   ├── test_connectivity.py
│   │   ├── test_economic.py
│   │   └── test_environmental.py
│   ├── test_layers/
│   │   └── test_layer_builders.py
│   └── test_api/
│       ├── test_analyze.py
│       ├── test_layers.py
│       └── test_listings.py
│
└── docs/
    ├── FRONTEND_INTEGRATION.md          ← Everything the frontend partner needs
    └── SCORING_INTERNALS.md             ← Everything the scoring partner needs
```

---

## Build Order — Follow Exactly

### Phase 1 — Foundation

**Do these in order. Do not skip ahead.**

1. `pyproject.toml` — all dependencies pinned
2. `requirements.txt` — generated from pyproject.toml
3. `.env.example` — all required variables with descriptions
4. `docker-compose.yml` — FastAPI + PostgreSQL + Redis for local dev
5. `Dockerfile` — multi-stage, python:3.11-slim base
6. `app/config.py` — pydantic-settings `Settings` class reading from env
7. `app/models/domain.py` — **start here for types** (BoundingBox, CellScore, GridCell)
8. `app/models/responses.py` — **full API contract** (ScoreBundle, CompositeScore, ScoreMetrics, all response types)
9. `app/models/requests.py` — request schemas
10. `app/main.py` — FastAPI app, CORS, router registration, lifespan
11. `app/dependencies.py` — DB session dep, Redis dep
12. `app/api/v1/health.py` — GET /health (smoke test endpoint)

**Checkpoint:** `docker-compose up` starts without errors. `GET /health` returns 200.

---

### Phase 2 — Database

1. `app/db/session.py` — async SQLAlchemy engine + session factory
2. `app/db/models.py` — all ORM models (see schema below)
3. `alembic.ini` + `app/db/migrations/` — Alembic setup
4. Initial migration — creates all tables, enables PostGIS, adds spatial indexes

**Schema — implement exactly:**

```sql
-- analysis_regions: one row per user search
CREATE TABLE analysis_regions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bbox            GEOMETRY(POLYGON, 4326) NOT NULL,
    state           VARCHAR(2) NOT NULL,
    grid_res_km     DECIMAL(5,2) NOT NULL DEFAULT 5.0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    cache_expires_at TIMESTAMPTZ,
    INDEX idx_regions_bbox USING GIST (bbox)
);

-- location_scores: one row per grid cell per analysis
CREATE TABLE location_scores (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region_id           UUID REFERENCES analysis_regions(id) ON DELETE CASCADE,
    point               GEOMETRY(POINT, 4326) NOT NULL,
    cell_polygon        GEOMETRY(POLYGON, 4326),
    -- Composite (weighted)
    composite_score     DECIMAL(5,4),
    -- Individual raw scores (0.0–1.0, pre-weighting)
    score_power         DECIMAL(5,4),
    score_water         DECIMAL(5,4),
    score_geological    DECIMAL(5,4),
    score_climate       DECIMAL(5,4),
    score_connectivity  DECIMAL(5,4),
    score_economic      DECIMAL(5,4),
    score_environmental DECIMAL(5,4),
    -- Full raw metric values + weight breakdown
    metrics             JSONB,
    composite_detail    JSONB,   -- weighted_contributions + weights_used
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_scores_point   USING GIST (point),
    INDEX idx_scores_region  (region_id),
    INDEX idx_scores_composite (composite_score DESC)
);

-- layer_cache: cached GeoJSON per layer per analysis
CREATE TABLE layer_cache (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region_id   UUID REFERENCES analysis_regions(id) ON DELETE CASCADE,
    layer_id    VARCHAR(50) NOT NULL,
    geojson     JSONB NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    UNIQUE (region_id, layer_id)
);

-- land_listings: scraped land parcels for sale
CREATE TABLE land_listings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     VARCHAR(200),
    source          VARCHAR(50) NOT NULL,    -- "landwatch" | "county_parcel"
    point           GEOMETRY(POINT, 4326),
    polygon         GEOMETRY(MULTIPOLYGON, 4326),
    address         TEXT,
    state           VARCHAR(2),
    county          VARCHAR(100),
    acres           DECIMAL(12,2),
    price_usd       BIGINT,
    price_per_acre  DECIMAL(12,2),
    zoning          VARCHAR(200),
    listing_url     TEXT,
    raw_data        JSONB,
    scraped_at      TIMESTAMPTZ DEFAULT NOW(),
    INDEX idx_listings_point USING GIST (point),
    INDEX idx_listings_state (state)
);
```

**Checkpoint:** `alembic upgrade head` runs clean. All tables exist with PostGIS indexes.

---

### Phase 3 — Integration Clients

Build one file per data source. Every client must:
- Extend `BaseIntegrationClient` from `integrations/base.py`
- Support mock mode: when `settings.MOCK_INTEGRATIONS=True`, return realistic static fixture data instead of calling the real API
- Use async `httpx.AsyncClient`
- Implement retry with exponential backoff (max 3 retries)
- Check Redis cache before making any network call
- Raise typed exceptions (`IntegrationError`) — never let raw HTTP errors bubble up

**`integrations/base.py`** — build this first:
```python
class BaseIntegrationClient:
    def __init__(self, redis_client, settings):
        self.redis = redis_client
        self.settings = settings
        self.mock = settings.MOCK_INTEGRATIONS

    async def _get_cached(self, key: str) -> dict | None: ...
    async def _set_cached(self, key: str, data: dict, ttl_hours: int = 24): ...
    async def _fetch_with_retry(self, url: str, params: dict = None) -> dict: ...
```

**Build these clients:**

#### `integrations/gee.py` — Google Earth Engine
```
Methods:
  get_land_cover(bbox) → dict         # NLCD 2021 land cover classes
  get_elevation(bbox) → dict          # SRTM 30m elevation grid
  get_ndvi(bbox) → dict               # Sentinel-2 NDVI (vegetation index)
  get_surface_temp(bbox) → dict       # MODIS land surface temperature

Auth: Service account JSON key from GEE_KEY_FILE env var
Export: Save results to GCS as Cloud-Optimized GeoTIFF
Cache TTL: 7 days (data changes slowly)
Mock: Return a 10x10 grid of realistic values for a North Carolina bbox
```

#### `integrations/osm.py` — OpenStreetMap Overpass API
```
Methods:
  get_power_lines(bbox) → list[Feature]      # LineStrings, voltage attr
  get_substations(bbox) → list[Feature]      # Points, voltage attr
  get_fiber_routes(bbox) → list[Feature]     # LineStrings
  get_highways(bbox, types) → list[Feature]  # LineStrings, highway attr
  get_amenities(bbox, types) → list[Feature] # Points (schools, hospitals)

Base URL: https://overpass-api.de/api/interpreter
Rate limit: 1 request/second — enforce this with asyncio.sleep
Cache TTL: 48 hours
```

#### `integrations/fema.py` — FEMA National Flood Hazard Layer
```
Methods:
  get_flood_zones(bbox) → list[Feature]  # Polygons with FLD_ZONE attr

Base URL: https://hazards.fema.gov/gis/nfhl/rest/services/public/NFHL/MapServer/28/query
No API key required
Cache TTL: 30 days
```

#### `integrations/usgs.py` — USGS APIs
```
Methods:
  get_seismic_hazard(lat, lng) → float   # PGA value (g) from USGS hazard API
  get_elevation_slope(bbox) → dict        # Slope in degrees from 3DEP

Seismic URL: https://earthquake.usgs.gov/hazards/designmaps/us/
Elevation URL: https://nationalmap.gov/epqs/pqs.php
Cache TTL: 30 days
```

#### `integrations/eia.py` — Energy Information Administration
```
Methods:
  get_retail_electricity_rate(state) → float    # Cents/kWh, commercial rate
  get_utility_territories(bbox) → list[Feature] # Polygons with utility name
  get_renewable_pct(state) → float              # % renewable in generation mix
  get_reliability_index(state) → float          # SAIDI reliability score 0–100

Base URL: https://api.eia.gov/v2/
Requires: EIA_API_KEY env var (free at api.eia.gov)
Cache TTL: 7 days
```

#### `integrations/noaa.py` — NOAA Climate Data Online
```
Methods:
  get_climate_normals(lat, lng) → dict   # Avg temp, precip, humidity (30yr normals)
  get_cooling_degree_days(state) → float # Annual CDD
  get_storm_events(state) → dict         # Tornado/hurricane/hail counts per 100sqkm

Base URL: https://www.ncei.noaa.gov/cdo-web/api/v2/
Requires: NOAA_API_KEY env var (free at ncei.noaa.gov)
Cache TTL: 7 days
```

#### `integrations/nasa_power.py` — NASA POWER
```
Methods:
  get_climate_data(lat, lng) → dict   # Annual humidity, solar, temperature normals

Base URL: https://power.larc.nasa.gov/api/temporal/climatology/point
No API key required
Cache TTL: 7 days
```

#### `integrations/census.py` — US Census Bureau
```
Methods:
  get_population_density(bbox) → dict      # Persons/sqkm by block group
  get_labor_data(state, county) → dict     # Employment, wages (BLS integration)

Base URL: https://api.census.gov/data/
Requires: CENSUS_API_KEY env var (free at api.census.gov)
Cache TTL: 30 days (Census data updates annually)
```

#### `integrations/epa.py` — EPA
```
Methods:
  get_superfund_sites(bbox) → list[Feature]  # Points from CERCLIS
  get_air_quality(lat, lng) → float          # AQI from AirNow API
  get_wetlands(bbox) → list[Feature]         # NWI polygons

Superfund URL: https://enviro.epa.gov/enviro/efservice/
AirNow URL: https://www.airnowapi.org/aq/observation/latLong/current/
Wetlands URL: https://www.fws.gov/program/national-wetlands-inventory (WFS)
Cache TTL: 7 days
```

**Checkpoint:** `MOCK_INTEGRATIONS=true pytest tests/` passes for all integration mocks.

---

### Phase 4 — Scoring Engine

#### `core/scoring/weights.py` — Build this FIRST in this phase

This is the most important file in the scoring system. Write it with thorough comments. The scoring partner edits only this file.

```python
# app/core/scoring/weights.py
#
# SCORING WEIGHTS CONFIGURATION
# ==============================
# This is the ONLY file you need to edit to change how locations are scored.
#
# HOW IT WORKS:
#   1. Each location is scored in 7 categories (power, water, geological, etc.)
#   2. Each category produces a raw score from 0.0 (worst) to 1.0 (best)
#   3. CATEGORY_WEIGHTS below controls how much each category influences
#      the final composite "optimal" score
#   4. Within each category, sub-metric weights control how individual
#      data points roll up to the category score
#
# RULES:
#   - Weights are relative — they do NOT need to sum to 1.0
#     The engine normalizes them automatically
#   - Set a weight to 0.0 to completely exclude that category
#   - Higher number = more influence on final score
#
# TO APPLY CHANGES: edit the values below, commit, and redeploy to Cloud Run.
#
# FOR FULL FORMULA DOCUMENTATION: see docs/SCORING_INTERNALS.md

CATEGORY_WEIGHTS: dict[str, float] = {
    "power":         0.20,  # Grid proximity, electricity cost, renewables
    "water":         0.15,  # Flood risk, water availability, drought
    "geological":    0.15,  # Seismic hazard, terrain slope, soil
    "climate":       0.15,  # Cooling efficiency, humidity, disaster risk
    "connectivity":  0.10,  # Fiber density, IXP distance, roads
    "economic":      0.15,  # Tax incentives, zoning, labor, land cost
    "environmental": 0.10,  # Human impact, wetlands, EPA proximity
}

# Sub-metric weights — must sum to 1.0 within each dict
POWER_SUB_WEIGHTS: dict[str, float] = {
    "grid_proximity":   0.35,
    "electricity_cost": 0.35,
    "renewable_pct":    0.20,
    "grid_reliability": 0.10,
}

WATER_SUB_WEIGHTS: dict[str, float] = {
    "flood_risk":         0.50,
    "water_availability": 0.30,
    "drought_risk":       0.20,
}

GEOLOGICAL_SUB_WEIGHTS: dict[str, float] = {
    "seismic_hazard":      0.35,
    "terrain_slope":       0.25,
    "soil_stability":      0.20,
    "hazard_proximity":    0.20,
}

CLIMATE_SUB_WEIGHTS: dict[str, float] = {
    "cooling_efficiency": 0.35,
    "humidity":           0.25,
    "tornado_risk":       0.15,
    "hurricane_risk":     0.15,
    "hail_risk":          0.10,
}

CONNECTIVITY_SUB_WEIGHTS: dict[str, float] = {
    "fiber_density":    0.40,
    "ix_proximity":     0.30,
    "road_access":      0.20,
    "airport_proximity":0.10,
}

ECONOMIC_SUB_WEIGHTS: dict[str, float] = {
    "tax_environment": 0.30,
    "land_cost":       0.25,
    "labor_market":    0.25,
    "permitting":      0.20,
}

ENVIRONMENTAL_SUB_WEIGHTS: dict[str, float] = {
    "population_proximity":  0.35,
    "sensitive_sites":       0.30,
    "air_quality":           0.20,
    "land_sensitivity":      0.15,
}
```

#### `core/scoring/base.py` — BaseScorer

```python
from abc import ABC, abstractmethod
from app.models.domain import BoundingBox, CellScore

class BaseScorer(ABC):
    """
    All scorers extend this class.
    Scorers return raw 0.0–1.0 scores ONLY.
    They never read from weights.py — that is engine.py's job.
    """
    category_id: str  # Must match key in CATEGORY_WEIGHTS

    @abstractmethod
    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """
        Score all candidate grid cells within bbox.
        Returns one CellScore per grid cell.
        CellScore.raw_scores[self.category_id] must be populated.
        CellScore.metrics must be fully populated.
        """
        ...

    def _clamp(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        return max(min_val, min(max_val, value))

    def _linear_scale(self, value: float, worst: float, best: float) -> float:
        """Scale a raw value to 0.0–1.0. worst=0.0, best=1.0."""
        if best == worst:
            return 0.5
        score = (value - worst) / (best - worst)
        return self._clamp(score)
```

#### `core/scoring/engine.py` — ScoringEngine

```python
# Orchestrates all 7 scorers and applies weights from weights.py.
# This is the only place in the codebase that touches weights.

import asyncio
from app.core.scoring.weights import CATEGORY_WEIGHTS
from app.models.responses import ScoreBundle, CompositeScore

class ScoringEngine:
    def __init__(self, ...all 7 scorers injected...):
        ...

    async def score_region(self, bbox: BoundingBox) -> list[ScoreBundle]:
        """
        1. Run all 7 scorers in parallel via asyncio.gather
        2. Merge results by grid cell location
        3. Apply CATEGORY_WEIGHTS to produce composite score per cell
        4. Return sorted list (highest composite first)
        """

    def _apply_weights(
        self,
        raw_scores: dict[str, float],
        weights: dict[str, float]
    ) -> CompositeScore:
        """
        Normalize weights, multiply by raw scores, sum to composite.
        Returns CompositeScore with:
          - composite: float (0.0–1.0 final score)
          - weighted_contributions: how much each category contributed
          - weights_used: the normalized weights actually applied
        """
        normalized = {k: v / sum(weights.values()) for k, v in weights.items()}
        contributions = {cat: raw_scores.get(cat, 0.0) * w for cat, w in normalized.items()}
        return CompositeScore(
            composite=round(sum(contributions.values()), 4),
            weighted_contributions=contributions,
            weights_used=normalized,
        )
```

#### Individual Scorers — implement all 7

Each scorer lives in its own file. Each one:
- Takes a `BoundingBox`
- Calls its relevant integration clients
- Computes sub-metric scores using the formulas below
- Rolls up sub-metrics using the corresponding `{CATEGORY}_SUB_WEIGHTS` from `weights.py`
- Returns `List[CellScore]`

**Power scorer formulas (`power.py`):**
```
grid_proximity:   1.0 - clamp(min(dist_substation_km, dist_line_km) / 20.0)
electricity_cost: 1.0 - clamp((rate_cents - 5.0) / 15.0)   # 5¢=best, 20¢=worst
renewable_pct:    renewable_pct / 100.0
grid_reliability: reliability_index / 100.0
```

**Water scorer formulas (`water.py`):**
```
flood_risk:        Zone X→1.0, Zone B/X500→0.7, Zone A→0.3, Zone AE/VE/AO→0.0
water_availability:1.0 - clamp(nearest_water_body_km / 10.0)
                   + 0.2 bonus if groundwater="high"
drought_risk:      D0→0.9, D1→0.7, D2→0.5, D3→0.2, D4→0.0
```

**Geological scorer formulas (`geological.py`):**
```
seismic_hazard:   1.0 - clamp(pga_g / 2.0)
terrain_slope:    1.0 - clamp(slope_degrees / 15.0)
soil_stability:   high→1.0, moderate→0.6, low→0.2, unknown→0.5
hazard_proximity: clamp(min(wetland_km, superfund_km) / 5.0)
```

**Climate scorer formulas (`climate.py`):**
```
cooling_efficiency: 1.0 - clamp((annual_cdd - 500) / 3500)  # 500=best, 4000=worst
humidity:           1.0 - clamp((avg_rh_pct - 30) / 60)     # 30%=best, 90%=worst
tornado_risk:       1.0 - clamp(tornado_events_per_100sqkm_30yr / 5.0)
hurricane_risk:     1.0 - clamp(hurricane_proximity_score / 1.0)
hail_risk:          1.0 - clamp(hail_events_per_100sqkm_30yr / 10.0)
```

**Connectivity scorer formulas (`connectivity.py`):**
```
fiber_density:     clamp(fiber_routes_within_5km / 5.0)
ix_proximity:      1.0 - clamp(nearest_ix_km / 200.0)
road_access:       1.0 - clamp(nearest_highway_km / 10.0)
airport_proximity: 1.0 - clamp(nearest_airport_km / 50.0)
```

**Economic scorer formulas (`economic.py`):**
```
tax_environment:  1.0 - clamp(state_corp_tax_rate / 12.0)
                  + 0.2 bonus if state has DC-specific tax exemption
                  (exemption states list: app/core/scoring/economic.py → DC_TAX_EXEMPTION_STATES)
land_cost:        1.0 - clamp(price_per_acre_usd / 50000)
labor_market:     clamp(tech_workers_per_1000_residents / 20.0)
permitting:       easy→1.0, moderate→0.6, difficult→0.2
```

**Environmental scorer formulas (`environmental.py`):**
```
population_proximity:  1.0 - clamp(population_within_5km / 50000)
sensitive_sites:       clamp(min(nearest_school_km, nearest_hospital_km) / 2.0)
air_quality:           1.0 - clamp(aqi / 300.0)
land_sensitivity:      0.0 if protected_land_within_1km else 1.0
```

**Checkpoint:** `pytest tests/test_scoring/` all pass with mock data. Engine correctly normalizes weights and produces composite scores.

---

### Phase 5 — GeoJSON Layer System

#### `core/layers/base.py` — BaseLayerBuilder

```python
class BaseLayerBuilder(ABC):
    layer_id: str
    label: str
    description: str

    @abstractmethod
    def build(self, score_bundles: list[ScoreBundle]) -> dict:
        """
        Convert ScoreBundle list → GeoJSON FeatureCollection.
        Each Feature must have these properties:
          layer_id, score (0.0–1.0), label (human string), color_hex, metrics (relevant subset)
        """

    def _score_to_color(self, score: float) -> str:
        """Map 0.0–1.0 to red-yellow-green hex. 0.0=#E74C3C, 0.5=#F39C12, 1.0=#2ECC71"""
```

#### Build one LayerBuilder per category (7 individual + 1 optimal = 8 total)

Each individual layer builder:
- Takes `list[ScoreBundle]`
- Uses `bundle.scores[category_id]` as the feature score
- Includes the relevant subset of `bundle.metrics` in feature properties
- Includes a human-readable `label` string (e.g. "Power: High — Substation 1.8km")

**Optimal layer builder (`optimal_layer.py`):**
- Uses `bundle.composite_score.composite` as the feature score
- Includes `bundle.composite_score.weighted_contributions` in properties
- Label: "Optimal Score: 0.87"

**All layer outputs must:**
- Be valid GeoJSON FeatureCollections
- Pass through `json.dumps` without error
- Include a top-level `metadata` property: `{ layer_id, label, score_range: [min, max], generated_at }`

**Caching:** After building, store in Redis (key: `layer:{layer_id}:{analysis_id}`, TTL: 24h) and GCS (path: `layers/{analysis_id}/{layer_id}.geojson`).

**Checkpoint:** All 8 layer builders produce valid GeoJSON from mock ScoreBundle data.

---

### Phase 6 — Land Listing System

#### `core/listings/landwatch_scraper.py`

```
Target: https://www.landwatch.com/land-for-sale/{state}/{county}
Filter params: minAcres=20, propertyType=commercial,industrial
Rate limit: 1 request per 2 seconds — hard requirement
Respect robots.txt: check before scraping
Extract: price, acreage, address, county, listing URL, parcel description
Geocode: Use Nominatim (https://nominatim.openstreetmap.org) — free, no key
Store: land_listings table, source="landwatch"
Refresh: weekly via Cloud Run job
```

#### `core/listings/county_parcel_fetcher.py`

```
Priority states: NC, VA, TX, TN, GA, CO, AZ
Download bulk parcel GIS data from state/county open data portals
Convert FGDB/Shapefile → PostGIS via GDAL (fiona + geopandas)
Filter: parcels > 20 acres
Store: land_listings table, source="county_parcel"
```

#### `core/listings/listing_service.py`

```
get_listings_near(lat, lng, radius_km, filters) → list[Listing]
  - Spatial query using PostGIS ST_DWithin
  - Join nearest location_scores cell to attach scores to each listing
  - Returns Listing objects with nearest_cell_scores attached

get_listings_in_region(analysis_id, filters) → list[Listing]
  - Filter to listings within analysis bbox
  - Same score join as above
```

---

### Phase 7 — API Endpoints

Implement all endpoints with full Pydantic validation and OpenAPI docstrings.

#### `POST /api/v1/analyze`

```
Request body:
{
  "bbox": { "min_lat": float, "min_lng": float, "max_lat": float, "max_lng": float },
  "state": "NC",                    # 2-letter state code
  "grid_resolution_km": 5.0,        # Default 5, min 1, max 25
  "min_acres": 20.0,                # Filter listings
  "max_acres": 500.0,
  "include_listings": true
}

Validation:
  - bbox must be within USA bounds (lat 24–50, lng -125 to -66)
  - bbox area must not exceed 50,000 sq km
  - state must be valid 2-letter US state code

Process:
  1. Generate grid of candidate points within bbox at grid_resolution_km spacing
  2. Run ScoringEngine.score_region(bbox) → list[ScoreBundle]
  3. Persist all ScoreBundle data to location_scores table
  4. Build all 8 GeoJSON layers → cache in Redis + GCS
  5. If include_listings: query/scrape land listings in bbox
  6. Persist analysis_id and return full response

Response:
{
  "analysis_id": "uuid",
  "region": { "bbox": {...}, "state": "NC" },
  "grid_cells": [ ...ScoreBundle array, sorted composite desc... ],
  "listings": [ ...Listing array... ],
  "layers_available": ["power","water","geological","climate","connectivity","economic","environmental","optimal"],
  "layer_urls": {
    "power": "/api/v1/layers/power?analysis_id=...",
    "optimal": "/api/v1/layers/optimal?analysis_id=...",
    ...
  },
  "metadata": {
    "grid_cells_analyzed": int,
    "processing_time_ms": int,
    "weights_used": { ...from weights.py... },
    "data_freshness": { "gee": "date", "listings": "date" }
  }
}
```

#### `GET /api/v1/layers/{layer_id}`

```
Path param: layer_id — one of: power|water|geological|climate|connectivity|economic|environmental|optimal
Query param: analysis_id (required)
Query param: format — "geojson" (default) | "pmtiles"

Process:
  1. Check Redis cache → return if hit
  2. Check GCS cache → return if hit
  3. Load ScoreBundles from DB for analysis_id
  4. Build layer → cache → return

Response: GeoJSON FeatureCollection
  Each Feature.properties must include:
    layer_id, score, label, color_hex,
    and the relevant metric subset for that layer
```

#### `GET /api/v1/layers`

```
Query param: analysis_id (required)
Response: list of available layer metadata with geojson_url for each
```

#### `GET /api/v1/scores`

```
Query param: analysis_id (required)
Response: { "analysis_id": "uuid", "scores": [...ScoreBundle array...] }
Lighter than /analyze — no re-processing, reads from DB cache only
```

#### `GET /api/v1/listings`

```
Query params:
  analysis_id (optional)
  lat + lng + radius_km (optional point-radius search)
  min_acres, max_acres, max_price_usd, state
  limit (default 20, max 100)

Response: { "listings": [...], "total": int }
Each listing includes nearest_cell_scores (composite + individual raw scores)
```

#### `GET /api/v1/scoring/schema`

```
Response:
{
  "version": "1.0",
  "current_weights": { ...CATEGORY_WEIGHTS from weights.py... },
  "categories": [
    {
      "id": "power",
      "label": "Power & Energy",
      "description": "...",
      "weight": 0.20,
      "sub_weights": { ...POWER_SUB_WEIGHTS... },
      "metrics": [
        {
          "id": "nearest_transmission_line_km",
          "label": "Distance to transmission line",
          "unit": "km",
          "lower_is_better": true,
          "formula": "1.0 - clamp(distance / 20.0)"
        }
      ]
    },
    ...all 7 categories...
  ],
  "note": "Weights are applied server-side. To change: edit app/core/scoring/weights.py and redeploy."
}

IMPORTANT: This endpoint must read weights directly from weights.py at runtime
           so it always reflects current deployed weights — never hardcode values here.
```

#### `GET /api/v1/health`

```
Response: { "status": "ok", "db": "ok|error", "redis": "ok|error", "gee": "ok|error" }
Checks actual connectivity to each service
```

**Checkpoint:** All endpoints return correct responses with mock data. OpenAPI docs at /docs are complete.

---

### Phase 8 — Documentation

#### `docs/SCORING_INTERNALS.md`

Write this document for the scoring partner. It must contain:

1. **Overview** — how scores flow from data source → scorer → engine → API response
2. **Quick reference table** — category, file, data source, sub-metrics, weight variable
3. **How to change a weight** — step by step, with the exact line to edit
4. **How to add a new scoring category** — full 9-step checklist
5. **Per-category deep dives** — for each of the 7 categories:
   - What it measures and why it matters for data centers
   - Data source + API used
   - Every sub-metric with its formula written out
   - The weight variable that controls it in `weights.py`
6. **How to access any score in code** — with working code examples:
   ```python
   # Run full scoring
   engine = ScoringEngine(...)
   bundles = await engine.score_region(bbox)

   # Read composite score
   bundles[0].composite_score.composite

   # Read individual category score
   bundles[0].scores["power"]

   # Read raw metric value
   bundles[0].metrics.power.electricity_rate_cents_per_kwh

   # Run a single scorer in isolation
   scorer = PowerScorer(...)
   results = await scorer.score(bbox)
   ```
7. **Score debugging guide** — how to enable debug logging, what it outputs
8. **Composite score formula** — written out explicitly with example numbers

#### `docs/FRONTEND_INTEGRATION.md`

Write this document for the frontend partner. It must contain:

1. **Base URL and local dev URL**
2. **All endpoints** with request/response examples (copy real response shapes)
3. **Full TypeScript types** for every response object:
   - `ScoreBundle`
   - `CompositeScore`
   - `ScoreMetrics` (all sub-objects)
   - `Listing`
   - `GeoJSONLayer`
4. **Map layer integration guide:**
   ```javascript
   // How to add a layer to Mapbox GL JS
   map.addSource('power-layer', { type: 'geojson', data: '/api/v1/layers/power?analysis_id=...' });
   map.addLayer({
     id: 'power-fill', type: 'fill', source: 'power-layer',
     paint: { 'fill-color': ['get', 'color_hex'], 'fill-opacity': 0.6 }
   });
   ```
5. **Score display guide** — what each field means, how to display breakdown
6. **Mock mode note** — `MOCK_INTEGRATIONS=true` works without API keys
7. **Data freshness** — which fields have `scraped_at` / `data_date` and how to display them
8. **Error response shapes** — all HTTP error codes and their `{ detail: string }` shape

---

### Phase 9 — Containerization & Deployment

1. **`Dockerfile`** — multi-stage build:
   ```
   Stage 1 (builder): python:3.11-slim, install all deps including GDAL
   Stage 2 (runtime): copy only what's needed, run as non-root user
   ```

2. **`docker-compose.yml`** — local dev stack:
   ```yaml
   services:
     api:       FastAPI on port 8000, hot reload, mounts ./app
     db:        postgres:15 with postgis/postgis image, port 5432
     redis:     redis:7-alpine, port 6379
   ```

3. **`cloudbuild.yaml`** — GCP Cloud Build config for CI/CD to Cloud Run

4. **Cloud Run Job configs** (in `jobs/`)  — one per ingestion job with schedule comments

5. **`README.md`** — local setup in 5 commands:
   ```bash
   git clone ...
   cp .env.example .env        # fill in your API keys
   docker-compose up -d db redis
   docker-compose run api alembic upgrade head
   docker-compose up api       # API live at http://localhost:8000
   ```

---

## Response Models — Full Specification

These are the authoritative shapes. Build `app/models/responses.py` to match exactly.

```python
from pydantic import BaseModel
from typing import Any

class CompositeScore(BaseModel):
    composite: float                              # 0.0–1.0 final weighted score
    weighted_contributions: dict[str, float]      # category → contribution amount
    weights_used: dict[str, float]                # category → normalized weight applied

class PowerMetrics(BaseModel):
    nearest_transmission_line_km: float
    nearest_substation_km: float
    electricity_rate_cents_per_kwh: float
    renewable_energy_pct: float
    grid_reliability_index: float
    utility_territory: str

class WaterMetrics(BaseModel):
    fema_flood_zone: str
    flood_risk_pct: float
    nearest_water_body_km: float
    groundwater_availability: str          # "high" | "moderate" | "low"
    drought_risk_level: str                # "D0"–"D4" | "None"

class GeologicalMetrics(BaseModel):
    seismic_hazard_pga: float
    slope_degrees: float
    elevation_m: float
    soil_bearing_capacity: str             # "high" | "moderate" | "low" | "unknown"
    nearest_wetland_km: float
    nearest_superfund_km: float

class ClimateMetrics(BaseModel):
    avg_annual_temp_c: float
    avg_summer_temp_c: float
    avg_humidity_pct: float
    annual_cooling_degree_days: float
    tornado_risk_index: float              # 0–100
    hurricane_risk_index: float            # 0–100
    hail_risk_index: float                 # 0–100

class ConnectivityMetrics(BaseModel):
    fiber_routes_within_5km: int
    nearest_ix_point_km: float
    nearest_highway_km: float
    nearest_airport_km: float

class EconomicMetrics(BaseModel):
    state_corporate_tax_rate_pct: float
    data_center_tax_exemption: bool
    permitting_difficulty: str             # "easy" | "moderate" | "difficult"
    median_electrician_wage_usd: float
    median_land_cost_per_acre_usd: float
    tech_workers_per_1000_residents: float

class EnvironmentalMetrics(BaseModel):
    population_within_5km: int
    nearest_school_km: float
    nearest_hospital_km: float
    air_quality_index: float
    protected_land_within_1km: bool
    land_cover_type: str                   # NLCD class name

class ScoreMetrics(BaseModel):
    power:         PowerMetrics
    water:         WaterMetrics
    geological:    GeologicalMetrics
    climate:       ClimateMetrics
    connectivity:  ConnectivityMetrics
    economic:      EconomicMetrics
    environmental: EnvironmentalMetrics

class LocationPoint(BaseModel):
    lat: float
    lng: float
    cell_polygon: dict                     # GeoJSON Polygon

class ScoreBundle(BaseModel):
    location: LocationPoint
    composite_score: CompositeScore        # Final weighted score + breakdown
    scores: dict[str, float]               # Raw 0.0–1.0 per category (pre-weight)
    metrics: ScoreMetrics                  # All underlying data values

class Listing(BaseModel):
    id: str
    source: str
    address: str | None
    state: str
    county: str | None
    acres: float
    price_usd: int | None
    price_per_acre: float | None
    zoning: str | None
    coordinates: dict                      # { lat, lng }
    polygon: dict | None                   # GeoJSON
    listing_url: str | None
    nearest_cell_scores: dict[str, float]  # composite + individual raw scores
    scraped_at: str
```

---

## Environment Variables

Every variable the app needs. Build `.env.example` from this list:

```bash
# ── Application ──────────────────────────────────────────────
ENVIRONMENT=development          # development | production
LOG_LEVEL=INFO                   # DEBUG | INFO | WARNING | ERROR
MOCK_INTEGRATIONS=false          # true = use mock data, no real API calls

# ── Database (Supabase free tier) ────────────────────────────
DATABASE_URL=postgresql+asyncpg://postgres:password@db.supabase.co:5432/postgres

# ── Redis (Upstash free tier) ────────────────────────────────
REDIS_URL=rediss://default:token@your-instance.upstash.io:6379

# ── Google Cloud ─────────────────────────────────────────────
GOOGLE_CLOUD_PROJECT=your-project-id
GCS_BUCKET_NAME=datacenter-selector-layers
GEE_SERVICE_ACCOUNT=gee-sa@your-project.iam.gserviceaccount.com
GEE_KEY_FILE=/run/secrets/gee-key.json

# ── External APIs (all free — see docs for registration links) ─
EIA_API_KEY=                     # api.eia.gov — free key
CENSUS_API_KEY=                  # api.census.gov — free key
NOAA_API_KEY=                    # ncei.noaa.gov — free key
# No key required: USGS, FEMA, NASA POWER, Overpass, Nominatim, EPA

# ── Caching ───────────────────────────────────────────────────
CACHE_TTL_HOURS=24
GEE_CACHE_TTL_HOURS=168          # 7 days
LISTINGS_CACHE_TTL_HOURS=168     # 7 days

# ── Analysis defaults ────────────────────────────────────────
GRID_RESOLUTION_DEFAULT_KM=5
MAX_BBOX_AREA_SQ_KM=50000
```

---

## Critical Rules — Never Violate These

1. **No weight values outside `weights.py`.** If you find yourself writing `0.20` next to a category name anywhere other than `weights.py`, stop and refactor.
2. **No scoring logic in API endpoint files.** Endpoints call the engine. The engine calls scorers. Scorers call integrations. No shortcuts.
3. **All geometries in WGS84 (EPSG:4326).** Reproject at the integration layer if a source uses a different CRS. Never let non-4326 geometries into the DB or responses.
4. **Never let integration exceptions reach the API response.** Catch at the scorer level, log the error, return a score of `null` for that cell with an error flag. Don't fail the entire analysis because one data source timed out.
5. **Mock mode must cover 100% of the happy path.** A developer with no API keys must be able to run `MOCK_INTEGRATIONS=true docker-compose up` and hit every endpoint with real-looking data.
6. **`/scoring/schema` reads from `weights.py` at runtime.** It must never have hardcoded weight values — import directly from `weights.py`.
7. **Listings data is best-effort.** Always include `scraped_at` timestamp. Warn in the API response metadata if listing data is older than 14 days.

---

## Free Data Sources Reference

| Source | Data | URL | Key Required |
|---|---|---|---|
| Google Earth Engine | Land cover, elevation, NDVI, temperature | earthengine.google.com | Service account (free, non-commercial) |
| USGS National Map | Elevation (3DEP), geology, hydro | nationalmap.gov | No |
| FEMA NFHL | Flood zones | hazards.fema.gov | No |
| USGS Seismic Hazard | Earthquake PGA | earthquake.usgs.gov | No |
| OpenStreetMap Overpass | Power, fiber, roads, amenities | overpass-api.de | No |
| EPA Superfund | Contaminated sites | enviro.epa.gov | No |
| EPA AirNow | AQI | airnowapi.org | Free key |
| USFWS NWI | Wetlands | fws.gov/program/national-wetlands-inventory | No |
| EIA Open Data | Electricity rates, utility territories | api.eia.gov | Free key |
| US Census | Population, economics | api.census.gov | Free key |
| NOAA CDO | Climate normals, storm events | ncei.noaa.gov | Free key |
| NASA POWER | Humidity, solar, temperature | power.larc.nasa.gov | No |
| PeeringDB | Internet exchange points | peeringdb.com/api | No |
| LandWatch | Land listings | landwatch.com | Scraping |
| Nominatim | Geocoding | nominatim.openstreetmap.org | No |

---

## Start Here

When Claude Code reads this file, the first thing to build is:

**`app/models/responses.py`**

This is the API contract. Everything else in the system is built to produce and serve these types. Once this file exists, the frontend partner can start building against it in parallel.

After `responses.py`, follow the Phase order exactly. Ask before making any assumption not covered in this document.