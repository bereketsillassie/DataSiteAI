# DataCenter Site Selector — Backend

Scores and ranks land across the USA for data center suitability using free public data sources (FEMA, USGS, OSM, EIA, NOAA, EPA, NASA POWER, US Census, GEE).

## Quick Start (5 commands)

```bash
git clone <repo-url>
cd datacenter-site-selector

cp .env.example .env            # Mock mode is on by default — no API keys needed

docker-compose up -d db redis   # Start PostgreSQL + Redis

docker-compose run api alembic upgrade head   # Create database tables

docker-compose up api           # API live at http://localhost:8000
```

- **OpenAPI Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/v1/health

## Run Your First Analysis

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "bbox": { "min_lat": 35.7, "min_lng": -79.2, "max_lat": 36.2, "max_lng": -78.6 },
    "state": "NC",
    "grid_resolution_km": 5.0,
    "include_listings": true
  }'
```

## Project Structure

```
app/
├── main.py                      FastAPI app
├── config.py                    Settings (pydantic-settings)
├── api/v1/                      API endpoints
├── core/
│   ├── scoring/
│   │   ├── weights.py           ← ONLY file the scoring partner edits
│   │   ├── engine.py            Applies weights, produces ScoreBundles
│   │   └── {category}.py       7 individual scorers
│   ├── layers/                  8 GeoJSON layer builders
│   └── listings/                LandWatch scraper + listing service
├── integrations/                9 external data source clients
├── models/                      Pydantic request/response models
└── db/                          SQLAlchemy models + Alembic migrations
```

## Architecture

```
POST /analyze
  │
  ├─ ScoringEngine
  │   ├─ PowerScorer      ← OSM + EIA
  │   ├─ WaterScorer      ← FEMA + OSM
  │   ├─ GeologicalScorer ← USGS + EPA
  │   ├─ ClimateScorer    ← NOAA + NASA POWER
  │   ├─ ConnectivityScorer ← OSM + PeeringDB
  │   ├─ EconomicScorer   ← Census + state tax data
  │   └─ EnvironmentalScorer ← EPA + Census + GEE
  │
  ├─ 8 GeoJSON Layer Builders → Redis cache
  └─ ListingService → LandWatch + County Parcels
```

## Configuration

All settings in `.env` (see `.env.example`). Key variables:

| Variable | Default | Description |
|---|---|---|
| `MOCK_INTEGRATIONS` | `false` | `true` = no real API calls, use fixture data |
| `DATABASE_URL` | local postgres | PostgreSQL + PostGIS connection string |
| `REDIS_URL` | local redis | Redis for caching |
| `EIA_API_KEY` | — | Free at api.eia.gov |
| `CENSUS_API_KEY` | — | Free at api.census.gov |
| `NOAA_API_KEY` | — | Free at ncei.noaa.gov |
| `AIRNOW_API_KEY` | — | Free at airnowapi.org |

**GEE** requires a service account with Earth Engine access. See: https://developers.google.com/earth-engine/guides/service_account

## API Keys

All data sources are free:

| Source | Key Required | Register At |
|---|---|---|
| EIA (electricity rates) | Yes | api.eia.gov |
| NOAA (climate data) | Yes | ncei.noaa.gov |
| US Census | Yes | api.census.gov |
| EPA AirNow | Yes | airnowapi.org |
| USGS, FEMA, NASA POWER, OSM, EPA Superfund | No | — |

## Running Tests

```bash
# With mock integrations (no API keys needed)
MOCK_INTEGRATIONS=true pytest tests/ -v

# Specific test files
MOCK_INTEGRATIONS=true pytest tests/test_scoring/ -v
MOCK_INTEGRATIONS=true pytest tests/test_layers/ -v
```

## Deployment

### Cloud Run (production)

```bash
# Build and deploy via Cloud Build
gcloud builds submit --config cloudbuild.yaml

# Or manually
docker build --target=production -t gcr.io/YOUR_PROJECT/datacenter-site-selector .
docker push gcr.io/YOUR_PROJECT/datacenter-site-selector
gcloud run deploy datacenter-site-selector \
  --image gcr.io/YOUR_PROJECT/datacenter-site-selector \
  --region us-east1 \
  --memory 2Gi
```

### Scheduled Jobs (Cloud Run Jobs)

```bash
# GEE data ingest — weekly (Sunday 2am UTC)
gcloud scheduler jobs create http ingest-gee \
  --schedule="0 2 * * 0" \
  --uri="https://YOUR_CLOUD_RUN_JOB_URL" \
  --message-body='{"state": "NC"}'

# Listing scrape — weekly (Monday 3am UTC)
gcloud scheduler jobs create http ingest-listings \
  --schedule="0 3 * * 1" \
  --uri="https://YOUR_CLOUD_RUN_JOB_URL"
```

## Documentation

- **Frontend Integration:** `docs/FRONTEND_INTEGRATION.md` — TypeScript types, Mapbox examples, all endpoints
- **Scoring System:** `docs/SCORING_INTERNALS.md` — how to change weights, formulas, add new categories

## Team

| Role | File(s) Owned |
|---|---|
| Backend engineer | Everything in this repo |
| Frontend engineer | Map UI (separate repo) |
| Scoring partner | `app/core/scoring/weights.py` **only** |
