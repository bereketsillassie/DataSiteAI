# DataSiteAI — Backend Database Integration Brief for Brady

## Context: What We've Built So Far

You're joining an active project. The frontend and backend are both live and talking to each other. Here is the current state:

**Frontend** (`/frontend/`) — React 19 + TypeScript + Vite + Tailwind CSS v4
- Full-screen dark map (CartoDB Dark Matter tiles via React-Leaflet)
- Floating panels: overlay toggles (carbon, wildfire, flood, seismic risk zones), site analysis scores, AI chat widget
- Calls two backend endpoints on every user interaction:
  - `POST http://127.0.0.1:8001/chat` — AI assistant (already wired and working)
  - `POST http://127.0.0.1:8001/api/v1/analyze` — site scoring engine (working in mock mode)

**Backend** (`/backend/`) — FastAPI + Python 3.13, running on port 8001
- `app/main.py` — app factory, CORS, lifespan hooks for DB + Redis init
- `app/api/v1/analyze.py` — the main scoring endpoint
- `app/chatbot/` — Gemini-powered chat with location context
- `app/core/scoring/` — the 7-category scoring engine
- `app/db/session.py` — async SQLAlchemy session factory (exists, needs real DB connection)
- `app/db/models.py` — ORM models (exist, need real migration run)
- `alembic.ini` — migration config (exists)

**The backend is currently running in `MOCK_INTEGRATIONS=true` mode.** The scoring engine returns computed scores, but nothing is being persisted to a database. Your job is to wire up the real PostgreSQL + PostGIS database (Supabase) so that analysis results are stored and retrievable.

---

## The API Contract — Do Not Break These

The frontend is hardcoded to consume these exact shapes. Changing the response structure will break the UI.

### `POST /api/v1/analyze`

**Request (what the frontend sends):**
```json
{
  "bbox": {
    "min_lat": 35.0,
    "min_lng": -79.1,
    "max_lat": 35.1,
    "max_lng": -79.0
  },
  "state": "NC",
  "grid_resolution_km": 5.0,
  "include_listings": false
}
```

**Response (what the frontend MUST receive — do not change this shape):**
```json
{
  "grid_cells": [
    {
      "composite_score": { "composite": 0.74 },
      "scores": {
        "power": 0.81,
        "connectivity": 0.68,
        "climate": 0.72
      },
      "metrics": {
        "power": {
          "electricity_rate_cents_per_kwh": 9.2,
          "renewable_energy_pct": 0.38,
          "grid_reliability_index": 0.91
        },
        "climate": {
          "avg_summer_temp_c": 27.4,
          "annual_cooling_degree_days": 1850
        },
        "connectivity": {
          "nearest_ix_point_km": 87
        },
        "environmental": {
          "air_quality_index": 42
        }
      }
    }
  ]
}
```

The frontend only reads: `grid_cells[0].composite_score.composite`, `grid_cells[0].scores`, and the metric fields listed above. You can add fields to the response, but **do not rename or remove any existing fields**.

### `POST /chat`

**Request:**
```json
{
  "message": "Is this a good site for a data center?",
  "history": [{ "role": "user", "content": "..." }, { "role": "assistant", "content": "..." }],
  "location_context": { "lat": 35.05, "lng": -79.05 }
}
```

**Response:**
```json
{ "reply": "Based on the selected location..." }
```

This endpoint is working. Don't touch the router or schemas for chat.

---

## Golden Rules — Read These Before Writing Any Code

1. **Do not change `app/main.py` env loading.** The first lines load `.env` before any imports. This order is critical. The `.env` file must stay at `backend/.env` (one level above `app/`).

2. **Do not change `app/main.py` startup order.** `init_db()` and `init_redis()` are called in the lifespan hook. They must remain there.

3. **`MOCK_INTEGRATIONS=true` must keep working.** This is how the frontend developer runs locally without a DB. If your changes break mock mode, you've broken local development.

4. **Branch from `main`, never commit directly to `main`.** Create a branch named `brady-db-integration` or similar. Open a PR when done. Main is the ground truth that other team members pull from.

5. **Never commit `.env` or API keys.** The `.gitignore` already excludes `.env`. Your Supabase credentials, EIA key, NOAA key, etc. go in `.env` locally only.

6. **Never commit `backend/venv/`.** Already in `.gitignore`. Do not re-add it.

7. **The weight system is sacred.** All scoring weights live in `app/core/scoring/weights.py` only. The scoring partner owns this file. Do not move weight values anywhere else.

---

## What You Need to Do: Database Integration

The database layer is scaffolded but not wired to a real connection. Here's the integration path:

### Step 1 — Get a Supabase project
- Free tier at supabase.com (500MB)
- Enable PostGIS extension: `CREATE EXTENSION IF NOT EXISTS postgis;`
- Get your connection string: `postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres`

### Step 2 — Set up your `.env`
Copy `.env.example` to `.env` and fill in:
```bash
ENVIRONMENT=development
MOCK_INTEGRATIONS=false
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PW@db.YOUR_PROJECT.supabase.co:5432/postgres
REDIS_URL=rediss://default:TOKEN@your-instance.upstash.io:6379
# ... other keys
```

### Step 3 — Run migrations
```bash
cd backend
source venv/bin/activate
alembic upgrade head
```
This creates `analysis_regions`, `location_scores`, `layer_cache`, and `land_listings` tables with PostGIS spatial indexes. If migrations don't exist yet, generate an initial one:
```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

### Step 4 — Wire persistence into the analyze endpoint
In `app/api/v1/analyze.py`, after the scoring engine returns results, persist them:
```python
# After engine.score_region(bbox) returns bundles:
async with get_db() as session:
    region = AnalysisRegion(bbox=..., state=request.state, grid_res_km=request.grid_resolution_km)
    session.add(region)
    for bundle in bundles:
        session.add(LocationScore(region_id=region.id, ...bundle fields...))
    await session.commit()
```
Return the same response shape as before — just now it's also saved to DB.

### Step 5 — Add `GET /api/v1/scores` for cache reads
Let the frontend request previously computed scores by `analysis_id` without re-running the engine. This is the main benefit of DB persistence.

### Step 6 — Verify mock mode still works
Set `MOCK_INTEGRATIONS=true` in `.env` and confirm:
```bash
curl -X POST http://127.0.0.1:8001/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"bbox":{"min_lat":35.0,"min_lng":-79.1,"max_lat":35.1,"max_lng":-79.0},"state":"NC","grid_resolution_km":5.0,"include_listings":false}'
```
Should return scores as before. No DB calls should fail if `MOCK_INTEGRATIONS=true`.

---

## How to Start the Backend

```bash
cd /Users/aidanmartin/DataSiteAI/backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

API docs available at: `http://127.0.0.1:8001/docs`

---

## Repo State

- **GitHub:** `github.com/bereketsillassie/DataSiteAI`
- **Ground truth branch:** `main` (everything currently on this machine)
- **Your branch:** create `brady-db-integration` off `main`
- **Backend location:** `/backend/`
- **Frontend location:** `/frontend/` — don't touch this unless coordinating with Aidan
- **DB schema spec:** Fully documented in `backend/CLAUDE.md` under "Phase 2 — Database"
- **Full architecture spec:** `backend/CLAUDE.md` — read it top to bottom before writing code

---

## The One Thing That Will Cause the Most Pain If You Get It Wrong

The frontend calls `/api/v1/analyze` and reads `response.grid_cells[0]`. If that key disappears, renames, or returns an empty array when it shouldn't, the entire right-side analysis panel goes blank.

As long as the response always contains `grid_cells` as a non-empty array with the shape above, the frontend will work regardless of what you change internally. Add `analysis_id` to the response, add caching headers, restructure the DB writes — all fine. Just don't rename `grid_cells`.
