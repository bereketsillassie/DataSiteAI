# DataSiteAI

**AI-Powered Data Center Site Selection Platform**

DataSiteAI combines an interactive Leaflet map, a real-time scoring engine, and a Gemini-powered AI assistant to help analysts identify, score, and evaluate optimal data center locations across the continental United States.

---

## Architecture

```
DataSiteAI/
├── backend/          # FastAPI (Python 3.13.5) — scoring engine + AI chat
│   ├── app/
│   │   ├── main.py           # App factory, CORS, router registration
│   │   ├── config.py         # Pydantic-settings (.env loader)
│   │   ├── api/v1/           # REST endpoints (/analyze, /layers, /scores, /health)
│   │   ├── core/scoring/     # 7-category weighted scoring engine
│   │   └── chatbot/          # Gemini 2.5 Flash chat router (POST /chat)
│   └── requirements.txt
└── frontend/         # React 19 + Vite + Tailwind v4 + shadcn/ui
    └── src/
        ├── App.tsx             # Layout shell + selectedLocation state
        ├── MapView.tsx         # Leaflet map with click handler
        ├── components/
        │   ├── Sidebar.tsx     # Overlays + live scoring panel
        │   └── ChatWidget.tsx  # Floating AI assistant
        └── components/ui/      # shadcn/ui primitives (Button, Switch, Progress…)
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.13.5 |
| Node.js | 18+ |
| npm | 9+ |

---

## Local Setup

### 1 — Clone and configure

```bash
git clone <repo-url>
cd DataSiteAI
cp backend/.env.example backend/.env
# Fill in GEMINI_API_KEY (and optional EIA_API_KEY, NOAA_API_KEY, etc.)
# For local dev without all integrations, set: MOCK_INTEGRATIONS=true
```

### 2 — Backend (FastAPI on port 8001)

```bash
cd backend

# Create and activate a virtual environment
python3.13 -m venv venv
source venv/bin/activate          # macOS/Linux
# .\venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

The API will be live at **http://127.0.0.1:8001**
- Interactive docs: http://127.0.0.1:8001/docs
- Health check: http://127.0.0.1:8001/api/v1/health

### 3 — Frontend (Vite dev server)

```bash
cd frontend

npm install
npm run dev
```

The app will be live at **http://localhost:5173**

---

## How It Works

1. **Click the map** — drops a pin at any US location and triggers the scoring engine via `POST /api/v1/analyze`
2. **Sidebar updates** — displays the Suitability Score, Power Grid, Connectivity, and Cooling Efficiency scores from the backend response in real time
3. **Chat widget** — click the ✨ button (bottom-right) to ask the Gemini AI about the selected site; your map coordinates are automatically included in every API call

---

## API Contract

### Chat endpoint

```
POST http://127.0.0.1:8001/chat

{
  "message": string,
  "history": [{ "role": "user" | "assistant", "content": string }],
  "location_context": { "lat": number, "lng": number } | null
}

→ { "reply": string }
```

### Site scoring endpoint

```
POST http://127.0.0.1:8001/api/v1/analyze

{
  "bbox": { "min_lat": float, "min_lng": float, "max_lat": float, "max_lng": float },
  "state": "US",
  "grid_resolution_km": 5.0,
  "include_listings": false
}

→ { "grid_cells": [ScoreBundle…], "analysis_id": string, … }
```

---

## Environment Variables

Create `backend/.env` from this template:

```bash
ENVIRONMENT=development
LOG_LEVEL=INFO
MOCK_INTEGRATIONS=true        # Set false only when all API keys are configured

# Database (required for full operation)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/datasiteai

# Redis (required for full operation)
REDIS_URL=redis://localhost:6379

# AI Brain
GEMINI_API_KEY=your_key_here   # Required for /chat endpoint

# Optional external data APIs (all free to register)
EIA_API_KEY=                   # api.eia.gov
CENSUS_API_KEY=                # api.census.gov
NOAA_API_KEY=                  # ncei.noaa.gov
```

---

## Key Dependencies

### Backend
| Package | Version | Purpose |
|---|---|---|
| fastapi | >=0.115.0 | Web framework |
| uvicorn | 0.29.0 | ASGI server |
| pydantic | >=2.10.0 | Data validation |
| sqlalchemy | >=2.0.48 | ORM (no 2.1.0 betas) |
| asyncpg | >=0.30.0 | Async PostgreSQL driver |
| greenlet | >=3.3.0 | Async context support |
| google-genai | latest | Gemini 2.5 Flash |
| geopandas / shapely | >=2.0.6 | Geospatial analysis |

### Frontend
| Package | Version | Purpose |
|---|---|---|
| react | 19.x | UI framework |
| vite | 8.x | Build tool |
| tailwindcss | 4.x | Styling |
| react-leaflet | 5.x | Interactive map |
| @radix-ui/* | latest | Accessible UI primitives |
| lucide-react | latest | Icons |

---

## Scoring System

The backend scores each candidate location across 7 weighted categories:

| Category | Default Weight | Data Sources |
|---|---|---|
| Power & Energy | 20% | EIA, OpenStreetMap |
| Water | 15% | FEMA NFHL, USGS |
| Geological | 15% | USGS Seismic, SRTM |
| Climate | 15% | NOAA, NASA POWER |
| Connectivity | 10% | OpenStreetMap, PeeringDB |
| Economic | 15% | Census, EIA, state data |
| Environmental | 10% | EPA, USFWS NWI |

Weights are configured in `backend/app/core/scoring/weights.py` — the only file the scoring engineer needs to edit.

---

## Development Notes

- **MOCK_INTEGRATIONS=true** lets the frontend run without any real API keys — the backend returns realistic static data for all scoring categories
- The Leaflet map uses standard OpenStreetMap tiles (light theme), which matches the Premium Light Mode UI perfectly
- CORS is wide-open in `development` mode (`allow_origins=["*"]`); tighten this in production via the `ENVIRONMENT` env var
- The `PYTHONPATH` and `.env` loading in `app/main.py` use `Path(__file__).parent.parent / ".env"` — do not move `.env` out of the `backend/` root

---

## Branch Structure

| Branch | Purpose |
|---|---|
| `main` | Production-ready, merged UI + backend |
| `aidan-ml-dev` | Active development |

---

*Built with FastAPI, React, Leaflet, Tailwind CSS, shadcn/ui, and Google Gemini 2.5 Flash.*
