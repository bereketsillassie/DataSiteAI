# FRONTEND_INTEGRATION.md
# DataCenter Site Selector — Frontend Integration Guide

> **Who this document is for:** The frontend engineer.
> This document contains everything you need to integrate with the backend API.
> You should never need to ask questions after reading this.

---

## Table of Contents

1. [Base URLs and Local Setup](#1-base-urls-and-local-setup)
2. [All Endpoints](#2-all-endpoints)
3. [Full TypeScript Types](#3-full-typescript-types)
4. [Map Layer Integration (Mapbox GL JS)](#4-map-layer-integration-mapbox-gl-js)
5. [Score Display Guide](#5-score-display-guide)
6. [Error Handling](#6-error-handling)
7. [Mock Mode for Local Development](#7-mock-mode-for-local-development)
8. [Data Freshness](#8-data-freshness)

---

## 1. Base URLs and Local Setup

| Environment | Base URL |
|---|---|
| Local development | `http://localhost:8000` |
| Production (Cloud Run) | TBD — will be provided after first deploy |

All API endpoints are prefixed with `/api/v1/`.

### Start the local backend in 3 commands

```bash
cp .env.example .env            # Copy env file (mock mode is already enabled by default)
docker-compose up -d db redis   # Start PostgreSQL and Redis
docker-compose up api           # Start the API -- available at http://localhost:8000
```

**Useful URLs once running:**

- OpenAPI docs (Swagger UI): http://localhost:8000/docs
- Alternative docs (ReDoc): http://localhost:8000/redoc
- Health check: http://localhost:8000/api/v1/health

**No API keys needed for local development.** The backend runs entirely in mock mode by default when started with docker-compose. All endpoints return realistic data without making any external API calls.

---

## 2. All Endpoints

### POST /api/v1/analyze

Run a full analysis on a geographic bounding box. This is the main entry point — call this first, then use the returned `analysis_id` for all subsequent requests.

**Request body:**

```typescript
{
  bbox: {
    min_lat: number,   // South boundary (latitude)
    min_lng: number,   // West boundary (longitude)
    max_lat: number,   // North boundary (latitude)
    max_lng: number    // East boundary (longitude)
  },
  state: string,                  // 2-letter US state code, e.g. "NC"
  grid_resolution_km: number,     // Grid cell size in km. Default: 5. Min: 1. Max: 25.
  min_acres?: number,             // Minimum listing size. Default: 20.
  max_acres?: number | null,      // Optional maximum listing size.
  include_listings?: boolean      // Whether to include land listings. Default: true.
}
```

**Example request:**

```typescript
const response = await fetch('http://localhost:8000/api/v1/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    bbox: { min_lat: 35.7, min_lng: -79.2, max_lat: 36.2, max_lng: -78.6 },
    state: 'NC',
    grid_resolution_km: 5.0,
    min_acres: 20,
    include_listings: true,
  }),
});
const data: AnalyzeResponse = await response.json();
const analysisId = data.analysis_id;  // Save this — you will use it everywhere
```

**Validation rules:**
- `bbox` must be within continental USA bounds: latitude 24–50, longitude -125 to -66
- `bbox` area must not exceed 50,000 sq km (roughly the size of West Virginia)
- `state` must be a valid 2-letter US state code

**Typical response time:** 5–30 seconds for a real analysis. Under 2 seconds in mock mode.

**Response:** See `AnalyzeResponse` in the TypeScript types section.

---

### GET /api/v1/layers/{layer_id}

Get a complete GeoJSON FeatureCollection for one scoring layer. Add the URL directly as a Mapbox source — no pre-processing needed.

**Path parameter:**
- `layer_id`: one of `power | water | geological | climate | connectivity | economic | environmental | optimal`

**Query parameters:**
- `analysis_id` (required): UUID from POST /analyze response
- `format` (optional): `geojson` (default)

**Examples:**

```
GET /api/v1/layers/optimal?analysis_id=3fa85f64-5717-4562-b3fc-2c963f66afa6
GET /api/v1/layers/power?analysis_id=3fa85f64-5717-4562-b3fc-2c963f66afa6
GET /api/v1/layers/water?analysis_id=3fa85f64-5717-4562-b3fc-2c963f66afa6
```

**Response:** A `GeoJSONLayer` object (see TypeScript types). Each feature has a `color_hex` property you can use directly in Mapbox paint expressions.

The response is cached in Redis. First call after analysis takes ~100ms. Subsequent calls return in ~5ms.

---

### GET /api/v1/layers

List metadata for all available layers for an analysis. Use this to build a layer toggle panel.

```
GET /api/v1/layers?analysis_id=3fa85f64-5717-4562-b3fc-2c963f66afa6
```

**Response:**

```json
{
  "analysis_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "layers": [
    {
      "layer_id": "optimal",
      "label": "Optimal Score",
      "description": "Composite weighted score across all 7 categories",
      "geojson_url": "/api/v1/layers/optimal?analysis_id=3fa85f64-5717-4562-b3fc-2c963f66afa6"
    },
    {
      "layer_id": "power",
      "label": "Power & Energy",
      "description": "Scores based on grid proximity, electricity cost, and renewables",
      "geojson_url": "/api/v1/layers/power?analysis_id=3fa85f64-5717-4562-b3fc-2c963f66afa6"
    }
    // ... 6 more layers
  ]
}
```

---

### GET /api/v1/scores

Get all scored grid cells for a completed analysis. Reads from the database cache — no re-processing.

```
GET /api/v1/scores?analysis_id=3fa85f64-5717-4562-b3fc-2c963f66afa6
```

**Response:**

```json
{
  "analysis_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "scores": [ /* array of ScoreBundle, sorted composite desc */ ]
}
```

Use this endpoint (not POST /analyze) if you need to reload scores for a previously-run analysis.

---

### GET /api/v1/listings

Search land listings. Supports two search modes: by analysis ID or by point-radius.

```
# Mode 1: All listings within an analysis's bbox
GET /api/v1/listings?analysis_id=3fa85f64-5717-4562-b3fc-2c963f66afa6&limit=20

# Mode 2: Point-radius search
GET /api/v1/listings?lat=35.9&lng=-78.9&radius_km=50&min_acres=20&limit=20

# Mode 3: Combined with filters
GET /api/v1/listings?analysis_id=3fa85f64&min_acres=50&max_price_usd=500000&state=NC&limit=50
```

**Query parameters:**

| Parameter | Type | Description | Default |
|---|---|---|---|
| `analysis_id` | string | UUID from POST /analyze | — |
| `lat` | number | Center latitude for point-radius search | — |
| `lng` | number | Center longitude for point-radius search | — |
| `radius_km` | number | Search radius (max 500) | 50 |
| `min_acres` | number | Minimum parcel size | — |
| `max_acres` | number | Maximum parcel size | — |
| `max_price_usd` | number | Maximum listing price | — |
| `state` | string | Filter by 2-letter state code | — |
| `limit` | number | Results to return (max 100) | 20 |

Either `analysis_id` or `lat`+`lng` must be provided.

**Response:**

```json
{
  "listings": [ /* array of Listing objects */ ],
  "total": 47
}
```

---

### GET /api/v1/scoring/schema

Get the full scoring schema including current weights, all categories, all sub-metrics, and the formula for each metric. Use this to build a "How we score" explanation UI.

```
GET /api/v1/scoring/schema
```

The `current_weights` field reflects the weights that are live right now — it is read from `weights.py` at runtime, not hardcoded.

---

### GET /api/v1/health

Check backend and dependency health. Use this to detect degraded state before running an analysis.

```
GET /api/v1/health
```

**Response:**

```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok",
  "gee": "ok"
}
```

If any value is `"error"`, that service is unreachable. In mock mode, `gee` always shows `"ok"` even without GEE credentials.

---

## 3. Full TypeScript Types

Copy these types directly into your TypeScript project.

```typescript
// ============================================================
// Composite Score
// ============================================================

interface CompositeScore {
  /** Final weighted score: 0.0 (worst) to 1.0 (best) */
  composite: number;
  /** How much each category contributed to the composite score */
  weighted_contributions: Record<string, number>;
  /** The normalized weight applied to each category */
  weights_used: Record<string, number>;
}

// ============================================================
// Per-Category Metrics (raw data values, not scores)
// ============================================================

interface PowerMetrics {
  nearest_transmission_line_km: number;
  nearest_substation_km: number;
  electricity_rate_cents_per_kwh: number;
  renewable_energy_pct: number;
  grid_reliability_index: number;  // 0-100
  utility_territory: string;       // Name of the electric utility
}

interface WaterMetrics {
  fema_flood_zone: string;         // "X" | "A" | "AE" | "VE" | "AO" | etc.
  flood_risk_pct: number;          // 0-100
  nearest_water_body_km: number;
  groundwater_availability: "high" | "moderate" | "low";
  drought_risk_level: "None" | "D0" | "D1" | "D2" | "D3" | "D4";
}

interface GeologicalMetrics {
  seismic_hazard_pga: number;      // Peak ground acceleration in g (e.g. 0.08)
  slope_degrees: number;
  elevation_m: number;
  soil_bearing_capacity: "high" | "moderate" | "low" | "unknown";
  nearest_wetland_km: number;
  nearest_superfund_km: number;
}

interface ClimateMetrics {
  avg_annual_temp_c: number;
  avg_summer_temp_c: number;
  avg_humidity_pct: number;
  annual_cooling_degree_days: number;
  tornado_risk_index: number;      // 0-100
  hurricane_risk_index: number;    // 0-100
  hail_risk_index: number;         // 0-100
}

interface ConnectivityMetrics {
  fiber_routes_within_5km: number;
  nearest_ix_point_km: number;     // Internet exchange point
  nearest_highway_km: number;
  nearest_airport_km: number;
}

interface EconomicMetrics {
  state_corporate_tax_rate_pct: number;
  data_center_tax_exemption: boolean;
  permitting_difficulty: "easy" | "moderate" | "difficult";
  median_electrician_wage_usd: number;
  median_land_cost_per_acre_usd: number;
  tech_workers_per_1000_residents: number;
}

interface EnvironmentalMetrics {
  population_within_5km: number;
  nearest_school_km: number;
  nearest_hospital_km: number;
  air_quality_index: number;           // EPA AQI
  protected_land_within_1km: boolean;
  land_cover_type: string;             // NLCD class name, e.g. "Cultivated Crops"
}

interface ScoreMetrics {
  power:         PowerMetrics;
  water:         WaterMetrics;
  geological:    GeologicalMetrics;
  climate:       ClimateMetrics;
  connectivity:  ConnectivityMetrics;
  economic:      EconomicMetrics;
  environmental: EnvironmentalMetrics;
}

// ============================================================
// Score Bundle (one per grid cell)
// ============================================================

interface LocationPoint {
  lat: number;
  lng: number;
  cell_polygon: GeoJSON.Polygon;  // The grid cell boundary
}

interface ScoreBundle {
  location:        LocationPoint;
  /** Final weighted composite score plus breakdown */
  composite_score: CompositeScore;
  /** Raw 0.0-1.0 per category, BEFORE weight application */
  scores: {
    power:         number;
    water:         number;
    geological:    number;
    climate:       number;
    connectivity:  number;
    economic:      number;
    environmental: number;
  };
  /** All underlying raw data values used to produce the scores */
  metrics: ScoreMetrics;
}

// ============================================================
// Land Listing
// ============================================================

interface Listing {
  id:             string;
  source:         "landwatch" | "county_parcel";
  address:        string | null;
  state:          string;          // 2-letter state code
  county:         string | null;
  acres:          number;
  price_usd:      number | null;
  price_per_acre: number | null;
  zoning:         string | null;
  coordinates:    { lat: number; lng: number };
  polygon:        GeoJSON.MultiPolygon | null;
  listing_url:    string | null;
  /** Scores from the nearest analyzed grid cell */
  nearest_cell_scores: {
    composite:     number;
    power:         number;
    water:         number;
    geological:    number;
    climate:       number;
    connectivity:  number;
    economic:      number;
    environmental: number;
  };
  scraped_at: string;  // ISO 8601 timestamp
}

// ============================================================
// API Response Types
// ============================================================

interface AnalysisMetadata {
  grid_cells_analyzed: number;
  processing_time_ms:  number;
  weights_used:        Record<string, number>;  // category -> normalized weight
  data_freshness:      Record<string, string>;  // source -> ISO date string
  /** True if listing data is more than 14 days old */
  listings_stale:      boolean;
}

interface RegionInfo {
  bbox:               GeoJSON.Polygon;
  state:              string;
  grid_resolution_km: number;
}

interface AnalyzeResponse {
  analysis_id:      string;
  region:           RegionInfo;
  /** Grid cells sorted by composite score descending (best locations first) */
  grid_cells:       ScoreBundle[];
  listings:         Listing[];
  /** The 8 available layer IDs */
  layers_available: string[];
  /** Map of layer_id -> relative URL to fetch that layer's GeoJSON */
  layer_urls:       Record<string, string>;
  metadata:         AnalysisMetadata;
}

interface ScoresResponse {
  analysis_id: string;
  scores:      ScoreBundle[];
}

interface LayerMetadata {
  layer_id:    string;
  label:       string;
  description: string;
  geojson_url: string;
}

interface LayersListResponse {
  analysis_id: string;
  layers:      LayerMetadata[];
}

interface ListingsResponse {
  listings: Listing[];
  total:    number;
}

// ============================================================
// GeoJSON Layer (returned by GET /layers/{layer_id})
// ============================================================

/** Properties on every feature in a layer GeoJSON response */
interface LayerFeatureProperties {
  layer_id:  string;
  /** Score for this cell on this specific layer (0.0-1.0) */
  score:     number;
  /** Human-readable label, e.g. "Power: High — Substation 1.8km" */
  label:     string;
  /** Pre-computed hex color: green (#2ECC71) at 1.0, red (#E74C3C) at 0.0 */
  color_hex: string;
  lat:       number;
  lng:       number;
  /** Category-specific subset of metrics relevant to this layer */
  metrics:   Record<string, unknown>;
}

interface GeoJSONLayer {
  type: "FeatureCollection";
  metadata: {
    layer_id:     string;
    label:        string;
    /** [min_score, max_score] across all features in this layer */
    score_range:  [number, number];
    generated_at: string;  // ISO 8601
  };
  features: Array<{
    type: "Feature";
    geometry: GeoJSON.Polygon;
    properties: LayerFeatureProperties;
  }>;
}
```

---

## 4. Map Layer Integration (Mapbox GL JS)

### Complete working example

```typescript
import mapboxgl from 'mapbox-gl';

mapboxgl.accessToken = 'your-mapbox-token';

const map = new mapboxgl.Map({
  container: 'map',
  style: 'mapbox://styles/mapbox/light-v11',
  center: [-78.9, 35.95],  // Research Triangle, NC
  zoom: 8,
});

// ---- Step 1: Run the analysis -------------------------------------------
async function runAnalysis() {
  const res = await fetch('http://localhost:8000/api/v1/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bbox: { min_lat: 35.7, min_lng: -79.2, max_lat: 36.2, max_lng: -78.6 },
      state: 'NC',
      grid_resolution_km: 5.0,
      include_listings: true,
    }),
  });

  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail);
  }

  return res.json() as Promise<AnalyzeResponse>;
}

// ---- Step 2: Add all 8 layers to the map --------------------------------
map.on('load', async () => {
  const data = await runAnalysis();
  const baseUrl = 'http://localhost:8000';

  // Add each layer as a source + fill layer
  for (const [layerId, url] of Object.entries(data.layer_urls)) {
    // Add GeoJSON source -- Mapbox fetches the GeoJSON directly from the API
    map.addSource(`${layerId}-source`, {
      type: 'geojson',
      data: `${baseUrl}${url}`,
    });

    // Add a filled polygon layer using the pre-computed color_hex from each feature
    map.addLayer({
      id: `${layerId}-fill`,
      type: 'fill',
      source: `${layerId}-source`,
      // Hide all layers except optimal by default
      layout: { visibility: layerId === 'optimal' ? 'visible' : 'none' },
      paint: {
        'fill-color': ['get', 'color_hex'],
        'fill-opacity': 0.65,
      },
    });

    // Add a thin outline for each cell
    map.addLayer({
      id: `${layerId}-outline`,
      type: 'line',
      source: `${layerId}-source`,
      layout: { visibility: layerId === 'optimal' ? 'visible' : 'none' },
      paint: {
        'line-color': '#555555',
        'line-width': 0.5,
        'line-opacity': 0.3,
      },
    });
  }

  // Add land listing markers
  addListingMarkers(data.listings);
});

// ---- Step 3: Toggle a layer on or off -----------------------------------
function setActiveLayer(layerId: string) {
  const allLayers = [
    'power', 'water', 'geological', 'climate',
    'connectivity', 'economic', 'environmental', 'optimal',
  ];

  for (const id of allLayers) {
    const visibility = id === layerId ? 'visible' : 'none';
    map.setLayoutProperty(`${id}-fill`, 'visibility', visibility);
    map.setLayoutProperty(`${id}-outline`, 'visibility', visibility);
  }
}

// ---- Step 4: Popup on click ---------------------------------------------
map.on('click', (e) => {
  // Check each layer for a feature under the click
  const layers = ['optimal-fill', 'power-fill', 'water-fill'];  // whichever are visible
  const features = map.queryRenderedFeatures(e.point, { layers });

  if (!features.length) return;

  const props = features[0].properties as LayerFeatureProperties;

  new mapboxgl.Popup({ maxWidth: '300px' })
    .setLngLat(e.lngLat)
    .setHTML(`
      <div style="font-family: sans-serif">
        <h3 style="margin: 0 0 8px">${props.label}</h3>
        <div style="font-size: 2rem; font-weight: bold; color: ${props.color_hex}">
          ${Math.round(props.score * 100)}%
        </div>
        <div style="font-size: 0.8rem; color: #666; margin-top: 4px">
          ${props.layer_id} score
        </div>
      </div>
    `)
    .addTo(map);
});

// Change cursor to pointer when hovering over a scored cell
map.on('mouseenter', 'optimal-fill', () => {
  map.getCanvas().style.cursor = 'pointer';
});
map.on('mouseleave', 'optimal-fill', () => {
  map.getCanvas().style.cursor = '';
});
```

### Adding land listing markers

```typescript
function addListingMarkers(listings: Listing[]) {
  for (const listing of listings) {
    const { lat, lng } = listing.coordinates;

    // Create a custom marker element
    const el = document.createElement('div');
    el.className = 'listing-marker';
    el.style.cssText = `
      width: 12px;
      height: 12px;
      border-radius: 50%;
      background: #3498DB;
      border: 2px solid white;
      cursor: pointer;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    `;

    const formatPrice = (price: number | null) =>
      price ? `$${price.toLocaleString()}` : 'Price not listed';

    const score = listing.nearest_cell_scores.composite;
    const scoreColor = score >= 0.75 ? '#2ECC71' : score >= 0.50 ? '#F39C12' : '#E74C3C';

    new mapboxgl.Marker(el)
      .setLngLat([lng, lat])
      .setPopup(
        new mapboxgl.Popup({ offset: 12, maxWidth: '280px' }).setHTML(`
          <div style="font-family: sans-serif; font-size: 13px">
            <h4 style="margin: 0 0 6px">${listing.address || 'Land Parcel'}</h4>
            <div><strong>${listing.acres} acres</strong> &mdash; ${formatPrice(listing.price_usd)}</div>
            ${listing.price_per_acre ? `<div>$${listing.price_per_acre.toLocaleString()}/acre</div>` : ''}
            ${listing.county ? `<div style="color:#666">${listing.county} County, ${listing.state}</div>` : ''}
            <div style="margin-top: 8px">
              Optimal Score:
              <strong style="color: ${scoreColor}">${Math.round(score * 100)}%</strong>
            </div>
            ${listing.listing_url ? `
              <a href="${listing.listing_url}" target="_blank" rel="noopener"
                style="display:block; margin-top:8px; color:#3498DB">
                View Listing &rarr;
              </a>
            ` : ''}
          </div>
        `)
      )
      .addTo(map);
  }
}
```

---

## 5. Score Display Guide

### Displaying the composite score

```typescript
// From ScoreBundle
const score = bundle.composite_score.composite;  // e.g. 0.774

// As a percentage (most common)
const pct = Math.round(score * 100);  // 77

// As a letter grade
function scoreToGrade(score: number): string {
  if (score >= 0.85) return 'A';
  if (score >= 0.70) return 'B';
  if (score >= 0.55) return 'C';
  if (score >= 0.40) return 'D';
  return 'F';
}

// As a color (matches the API's color_hex values)
function scoreToColor(score: number): string {
  if (score >= 0.75) return '#2ECC71';  // green
  if (score >= 0.50) return '#F39C12';  // yellow/orange
  return '#E74C3C';                      // red
}

// As a text label
function scoreToLabel(score: number): string {
  if (score >= 0.85) return 'Excellent';
  if (score >= 0.70) return 'Good';
  if (score >= 0.55) return 'Fair';
  if (score >= 0.40) return 'Poor';
  return 'Very Poor';
}
```

### Displaying the score breakdown

The `weighted_contributions` object shows exactly how much each category contributed to the final composite score. Use this to build a breakdown bar chart.

```typescript
// bundle.composite_score.weighted_contributions:
// { power: 0.164, water: 0.137, geological: 0.117, climate: 0.128,
//   connectivity: 0.065, economic: 0.108, environmental: 0.055 }

// bundle.composite_score.weights_used:
// { power: 0.20, water: 0.15, geological: 0.15, climate: 0.15,
//   connectivity: 0.10, economic: 0.15, environmental: 0.10 }

// Build a sorted breakdown for a chart
const breakdown = Object.entries(bundle.composite_score.weighted_contributions)
  .sort(([, a], [, b]) => b - a)  // sort by contribution, largest first
  .map(([category, contribution]) => ({
    category,
    label: categoryLabels[category],   // see labels below
    contribution,
    rawScore: bundle.scores[category],                            // 0.0-1.0 pre-weight
    weight: bundle.composite_score.weights_used[category],        // normalized weight
    /** How much of the final score this category accounts for */
    pctOfTotal: contribution / bundle.composite_score.composite,
  }));

// Human-readable category labels
const categoryLabels: Record<string, string> = {
  power:         'Power & Energy',
  water:         'Water & Flood Risk',
  geological:    'Geological & Terrain',
  climate:       'Climate & Weather',
  connectivity:  'Connectivity & Access',
  economic:      'Economic Environment',
  environmental: 'Environmental Impact',
};
```

### Key metric display values

| Field path | Display label | Suggested format |
|---|---|---|
| `metrics.power.electricity_rate_cents_per_kwh` | Electricity Rate | `8.2¢/kWh` |
| `metrics.power.nearest_substation_km` | Nearest Substation | `1.8 km` |
| `metrics.power.renewable_energy_pct` | Renewable Mix | `42%` |
| `metrics.water.fema_flood_zone` | Flood Zone | `Zone X` |
| `metrics.water.drought_risk_level` | Drought Risk | `D1 — Moderate` |
| `metrics.geological.seismic_hazard_pga` | Seismic Risk | `0.08g` |
| `metrics.geological.slope_degrees` | Terrain Slope | `2.3°` |
| `metrics.climate.annual_cooling_degree_days` | Cooling Degree Days | `1,850 CDD/yr` |
| `metrics.climate.avg_humidity_pct` | Avg Humidity | `71%` |
| `metrics.connectivity.fiber_routes_within_5km` | Fiber Routes (5km) | `3 routes` |
| `metrics.connectivity.nearest_ix_point_km` | Nearest IX Point | `72 km` |
| `metrics.economic.state_corporate_tax_rate_pct` | Corp. Tax Rate | `2.5%` |
| `metrics.economic.data_center_tax_exemption` | DC Tax Exemption | `Yes` or `No` |
| `metrics.economic.permitting_difficulty` | Permitting | `Easy` |
| `metrics.environmental.population_within_5km` | Population (5km) | `4,200 people` |
| `metrics.environmental.air_quality_index` | Air Quality | `42 — Good` |
| `metrics.environmental.protected_land_within_1km` | Protected Land | `None nearby` or `Present` |

### AQI display labels

```typescript
function aqiCategory(aqi: number): { label: string; color: string } {
  if (aqi <= 50)  return { label: 'Good',                              color: '#00E400' };
  if (aqi <= 100) return { label: 'Moderate',                         color: '#FFFF00' };
  if (aqi <= 150) return { label: 'Unhealthy for Sensitive Groups',   color: '#FF7E00' };
  if (aqi <= 200) return { label: 'Unhealthy',                        color: '#FF0000' };
  if (aqi <= 300) return { label: 'Very Unhealthy',                   color: '#8F3F97' };
  return           { label: 'Hazardous',                              color: '#7E0023' };
}
```

### FEMA flood zone display labels

```typescript
const floodZoneDescriptions: Record<string, string> = {
  'X':   'Minimal Risk (Zone X)',
  'B':   'Moderate Risk (Zone B)',
  'A':   'High Risk — 100yr Floodplain (Zone A)',
  'AE':  'High Risk — Detailed Study (Zone AE)',
  'AO':  'High Risk — Sheet Flow (Zone AO)',
  'AH':  'High Risk — Ponding (Zone AH)',
  'VE':  'Coastal High Hazard (Zone VE)',
  'V':   'Coastal Hazard (Zone V)',
};

// Usage:
const zoneLabel = floodZoneDescriptions[metrics.water.fema_flood_zone] ?? `Zone ${metrics.water.fema_flood_zone}`;
```

---

## 6. Error Handling

All error responses from this API use this consistent shape:

```typescript
interface ErrorResponse {
  detail: string;  // Human-readable description of what went wrong
}
```

| HTTP Code | When it happens | Recommended UI response |
|---|---|---|
| `400 Bad Request` | Malformed request body | Show `detail` message to user |
| `404 Not Found` | `analysis_id` not found in database | Prompt user to run a new analysis |
| `422 Unprocessable Entity` | Validation failed (bbox too large, invalid state code, etc.) | Show specific `detail` message — it describes which field failed |
| `500 Internal Server Error` | Scoring engine failure or DB error | Show "Analysis failed — please try again" |
| `503 Service Unavailable` | Backend overloaded or starting up | Retry after a short delay |

### Wrapper function with full error handling

```typescript
async function analyzeRegion(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  const response = await fetch('/api/v1/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error: ErrorResponse = await response.json();

    switch (response.status) {
      case 400:
        throw new Error(`Bad request: ${error.detail}`);
      case 422:
        // Validation errors contain field-specific messages
        throw new ValidationError(`Invalid input: ${error.detail}`);
      case 500:
        throw new Error('Analysis failed. Please try a smaller area or try again.');
      default:
        throw new Error(`Unexpected error (${response.status}): ${error.detail}`);
    }
  }

  return response.json() as Promise<AnalyzeResponse>;
}

// Example: bbox validation error from the API
// status: 422
// body: { "detail": "Bounding box area 87,432 sq km exceeds maximum of 50,000 sq km" }
```

---

## 7. Mock Mode for Local Development

The backend starts in mock mode by default when launched with docker-compose. You do not need to configure anything.

**What mock mode provides:**

- All 7 scoring categories return realistic scores for a North Carolina bounding box
- 5 pre-defined land parcels with realistic NC coordinates, acreage, and pricing
- All 8 GeoJSON layers are fully generated with mock scores and color values
- `GET /api/v1/health` returns `{ "status": "ok", ... }` for all services
- Responses look identical to production — the frontend cannot tell the difference

**To verify mock mode is active:**

```bash
curl http://localhost:8000/api/v1/health
# { "status": "ok", "db": "ok", "redis": "ok", "gee": "ok" }

curl http://localhost:8000/api/v1/scoring/schema | python -m json.tool | head -20
# Should return full schema with current weights
```

**To switch to real data** (requires all API keys to be filled in `.env`):

```bash
# In .env:
MOCK_INTEGRATIONS=false
```

Then restart: `docker-compose restart api`

---

## 8. Data Freshness

The `metadata.data_freshness` object in the analyze response tells you how current each data source is:

```typescript
// data.metadata.data_freshness example:
{
  "gee":     "2023-12-01",  // Google Earth Engine land cover (updated ~annually)
  "osm":     "2024-03-21",  // OpenStreetMap infrastructure (scraped each run)
  "listings":"2024-03-21",  // Land listings (scraped weekly by background job)
  "eia":     "2024-03-21",  // Electricity rates (cached 7 days)
  "noaa":    "2023-01-01",  // Climate normals (30-year averages, very stable)
  "census":  "2022-01-01"   // Census data (updates annually)
}
```

### Handling stale listing data

```typescript
// data.metadata.listings_stale is true when listing data is more than 14 days old
if (data.metadata.listings_stale) {
  // Show a warning — this is important for users making purchase decisions
  showBanner({
    type: 'warning',
    message: 'Land listing prices may be outdated. Verify current pricing directly with sellers.',
  });
}
```

### Displaying data freshness in the UI

```typescript
function formatDataDate(isoDate: string): string {
  const date = new Date(isoDate);
  const now = new Date();
  const daysAgo = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

  if (daysAgo === 0) return 'Updated today';
  if (daysAgo === 1) return 'Updated yesterday';
  if (daysAgo < 7)  return `Updated ${daysAgo} days ago`;
  if (daysAgo < 30) return `Updated ${Math.floor(daysAgo / 7)} weeks ago`;
  return `Updated ${date.toLocaleDateString()}`;
}

// Usage in a "data sources" tooltip or panel:
const freshnessItems = Object.entries(data.metadata.data_freshness).map(([source, date]) => ({
  source: sourceLabels[source] ?? source,
  freshness: formatDataDate(date),
}));

const sourceLabels: Record<string, string> = {
  gee:      'Satellite Imagery',
  osm:      'Infrastructure (OSM)',
  listings: 'Land Listings',
  eia:      'Electricity Rates',
  noaa:     'Climate Data',
  census:   'Census & Demographics',
};
```

### Which fields have timestamps

| Field | Type | Description |
|---|---|---|
| `listing.scraped_at` | ISO 8601 string | When this specific listing was last fetched from the source |
| `metadata.data_freshness` | `Record<string, string>` | Per-source data dates for the analysis |
| `metadata.listings_stale` | boolean | True when `listings` data age > 14 days |
| `layer.metadata.generated_at` | ISO 8601 string | When the GeoJSON layer was built (from `GET /layers/{id}` response) |
