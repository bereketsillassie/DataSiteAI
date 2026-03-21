# SCORING_INTERNALS.md
# DataCenter Site Selector — Scoring System Documentation

> **Who this document is for:** The scoring partner.
> You own `app/core/scoring/weights.py`. That is the **only** file you need to edit.
> This document explains what everything does so you can change weights confidently.

---

## Table of Contents

1. [Quick Start — How to Change a Weight](#1-quick-start--how-to-change-a-weight)
2. [How Scores Flow Through the System](#2-how-scores-flow-through-the-system)
3. [Quick Reference Table](#3-quick-reference-table)
4. [The Composite Score Formula](#4-the-composite-score-formula)
5. [Per-Category Deep Dives](#5-per-category-deep-dives)
   - [5.1 Power & Energy](#51-power--energy)
   - [5.2 Water & Flood Risk](#52-water--flood-risk)
   - [5.3 Geological & Terrain](#53-geological--terrain)
   - [5.4 Climate & Weather](#54-climate--weather)
   - [5.5 Connectivity & Access](#55-connectivity--access)
   - [5.6 Economic Environment](#56-economic-environment)
   - [5.7 Environmental Impact](#57-environmental-impact)
6. [How to Add a New Scoring Category](#6-how-to-add-a-new-scoring-category)
7. [Accessing Scores in Code](#7-accessing-scores-in-code)
8. [Score Debugging Guide](#8-score-debugging-guide)

---

## 1. Quick Start — How to Change a Weight

**The only file you ever need to edit:** `app/core/scoring/weights.py`

### Example: Make power infrastructure matter twice as much

Open `weights.py`. Find `CATEGORY_WEIGHTS`. Change `"power": 0.20` to `"power": 0.40`:

```python
CATEGORY_WEIGHTS: dict[str, float] = {
    "power":          0.40,   # Changed from 0.20 to 0.40
    "water":          0.15,
    "geological":     0.15,
    "climate":        0.15,
    "connectivity":   0.10,
    "economic":       0.15,
    "environmental":  0.10,
}
```

Save, commit, redeploy. Done. The system normalizes weights automatically — they do not need to sum to any specific number.

### Example: Disable a category entirely

Set its weight to `0.0`:

```python
"environmental":  0.0,   # This category is now ignored in composite scoring
```

### Example: Change a sub-metric within a category

The `POWER_SUB_WEIGHTS` dict controls how 4 power metrics combine into one power score.
To make electricity cost matter more than substation proximity:

```python
POWER_SUB_WEIGHTS: dict[str, float] = {
    "grid_proximity":    0.20,   # Reduced
    "electricity_cost":  0.50,   # Increased
    "renewable_pct":     0.20,
    "grid_reliability":  0.10,
}
# IMPORTANT: Sub-weights must always sum to exactly 1.0
```

### To apply changes

1. Edit `weights.py`
2. Commit the change: `git add app/core/scoring/weights.py && git commit -m "Update scoring weights"`
3. Redeploy to Cloud Run

To confirm your change took effect, call `GET /api/v1/scoring/schema` after deployment. The `current_weights` field is read directly from `weights.py` at runtime — it always reflects what is currently live.

---

## 2. How Scores Flow Through the System

```
Raw Data Sources                Individual Scores           Weighted Composite
------------------------------------------------------------------------------

OSM power lines     --+
EIA electricity     --+--> PowerScorer      --> power: 0.82   --+
                      |                                          |
FEMA flood zones    --+--> WaterScorer      --> water: 0.91   --+
                      |                                          |
USGS seismic data   --+--> GeologicalScorer --> geological: 0.78 -+
                      |                                          |  --> ScoringEngine
NOAA climate data   --+--> ClimateScorer    --> climate: 0.85  --+    |
                      |                                          |     | Applies
OSM fiber/highways  --+--> ConnectivityScorer -> connectivity: 0.65 --+  CATEGORY_WEIGHTS
                      |                                          |     | from weights.py
Census + tax data   --+--> EconomicScorer   --> economic: 0.72 --+    |
                      |                                          |     v
EPA + Census pop    --+--> EnvironmentalScorer -> environmental: 0.55 -+--> composite: 0.774
```

**The key rule:** Individual scorers never touch `weights.py`. Only `engine.py` applies weights. Scorers just measure things and return a number between 0.0 and 1.0.

---

## 3. Quick Reference Table

| Category | File | Data Sources | Weight Variable |
|---|---|---|---|
| Power & Energy | `scoring/power.py` | OSM (power lines, substations) + EIA API (rates, reliability) | `POWER_SUB_WEIGHTS` |
| Water & Flood | `scoring/water.py` | FEMA NFHL (flood zones) + OSM (water bodies) + NOAA/USDM (drought) | `WATER_SUB_WEIGHTS` |
| Geological | `scoring/geological.py` | USGS Seismic Hazard API + USGS 3DEP (elevation/slope) + EPA Superfund + USFWS NWI (wetlands) | `GEOLOGICAL_SUB_WEIGHTS` |
| Climate | `scoring/climate.py` | NOAA Climate Data Online + NASA POWER | `CLIMATE_SUB_WEIGHTS` |
| Connectivity | `scoring/connectivity.py` | OSM (fiber, highways) + PeeringDB (internet exchange points) | `CONNECTIVITY_SUB_WEIGHTS` |
| Economic | `scoring/economic.py` | State tax tables (hardcoded in `economic.py`) + US Census API | `ECONOMIC_SUB_WEIGHTS` |
| Environmental | `scoring/environmental.py` | EPA AirNow (AQI) + US Census (population) + OSM (amenities) + GEE NLCD (land cover) | `ENVIRONMENTAL_SUB_WEIGHTS` |

All category weights are controlled by: `CATEGORY_WEIGHTS` in `weights.py`

---

## 4. The Composite Score Formula

Every grid cell gets a composite score from 0.0 (worst) to 1.0 (best).

### Step 1: Individual category scores

Each of the 7 scorers produces a raw score (0.0–1.0) for each grid cell. These are produced independently and in parallel.

### Step 2: Normalize category weights

The engine reads `CATEGORY_WEIGHTS` from `weights.py` and normalizes them so they sum to 1.0:

```
Given weights: {power: 0.20, water: 0.15, geological: 0.15, climate: 0.15,
                connectivity: 0.10, economic: 0.15, environmental: 0.10}

Total = 0.20 + 0.15 + 0.15 + 0.15 + 0.10 + 0.15 + 0.10 = 1.00

Normalized weights (divided by total):
  power         = 0.20 / 1.00 = 0.200
  water         = 0.15 / 1.00 = 0.150
  geological    = 0.15 / 1.00 = 0.150
  climate       = 0.15 / 1.00 = 0.150
  connectivity  = 0.10 / 1.00 = 0.100
  economic      = 0.15 / 1.00 = 0.150
  environmental = 0.10 / 1.00 = 0.100
```

Because the engine always normalizes, the actual values you write in `weights.py` are relative proportions, not percentages. `{power: 2, water: 1}` and `{power: 0.40, water: 0.20}` produce the same result.

### Step 3: Multiply and sum

```
Example grid cell with raw scores:
  power=0.82, water=0.91, geological=0.78, climate=0.85,
  connectivity=0.65, economic=0.72, environmental=0.55

composite = (0.82 x 0.200) + (0.91 x 0.150) + (0.78 x 0.150) + (0.85 x 0.150)
          + (0.65 x 0.100) + (0.72 x 0.150) + (0.55 x 0.100)

          = 0.164 + 0.137 + 0.117 + 0.128 + 0.065 + 0.108 + 0.055

          = 0.774  <- final composite score
```

### Reading the breakdown in the API response

The API response includes `weighted_contributions` for every grid cell so you can see exactly how much each category contributed to the final score. This is useful for auditing weight changes.

```json
{
  "composite_score": {
    "composite": 0.774,
    "weighted_contributions": {
      "power":         0.164,
      "water":         0.137,
      "geological":    0.117,
      "climate":       0.128,
      "connectivity":  0.065,
      "economic":      0.108,
      "environmental": 0.055
    },
    "weights_used": {
      "power":         0.200,
      "water":         0.150,
      "geological":    0.150,
      "climate":       0.150,
      "connectivity":  0.100,
      "economic":      0.150,
      "environmental": 0.100
    }
  }
}
```

---

## 5. Per-Category Deep Dives

Each sub-metric score is a number between 0.0 and 1.0. The formulas use two helper functions:

- `clamp(x)` forces any number into the range 0.0–1.0. If x < 0, returns 0. If x > 1, returns 1. Otherwise returns x unchanged.
- `linear_scale(value, worst, best)` maps a raw value to 0.0–1.0 where `worst` maps to 0.0 and `best` maps to 1.0.

### 5.1 Power & Energy

**What it measures:** How good is the electrical infrastructure near this location?

**Why it matters for data centers:** Data centers consume enormous amounts of electricity — often 20–100 megawatts for a hyperscale facility. Cheap, reliable power close to the site is the single most important infrastructure factor. Every kilometer of new transmission line a developer must build costs millions of dollars. States with high electricity rates eliminate locations from consideration immediately.

**Data source:** OpenStreetMap (substation and transmission line locations) + EIA API (commercial electricity rates, grid reliability statistics)

**Sub-metrics and formulas:**

| Sub-Metric | Formula | Best | Worst | Notes |
|---|---|---|---|---|
| `grid_proximity` | `1.0 - clamp(min(dist_substation_km, dist_line_km) / 20.0)` | 0 km | 20+ km | Uses whichever is closer: substation or transmission line |
| `electricity_cost` | `1.0 - clamp((rate_cents - 5.0) / 15.0)` | 5 cents/kWh | 20 cents/kWh | Commercial industrial rate from EIA |
| `renewable_pct` | `renewable_pct / 100.0` | 100% renewable | 0% renewable | Important for ESG and sustainability commitments |
| `grid_reliability` | `reliability_index / 100.0` | 100 (zero outages) | 0 (frequent outages) | SAIDI-based index from EIA |

**Weight variable:** `POWER_SUB_WEIGHTS` in `weights.py`

**Default sub-weights:**
```python
POWER_SUB_WEIGHTS: dict[str, float] = {
    "grid_proximity":   0.35,
    "electricity_cost": 0.35,
    "renewable_pct":    0.20,
    "grid_reliability": 0.10,
}
```

---

### 5.2 Water & Flood Risk

**What it measures:** Flood danger, water availability for cooling systems, and drought risk.

**Why it matters for data centers:** A single flooding event can cause hundreds of millions of dollars in hardware damage and destroy years of uptime records. FEMA flood zone designation is the most important binary filter — no serious developer builds in Zone AE or VE. Water is also needed in large quantities for cooling towers; proximity to a water source reduces infrastructure cost.

**Data source:** FEMA National Flood Hazard Layer (flood zone polygons) + OpenStreetMap (rivers, lakes, reservoirs) + NOAA/US Drought Monitor (drought severity)

**Sub-metrics and formulas:**

| Sub-Metric | Formula | Best | Worst | Notes |
|---|---|---|---|---|
| `flood_risk` | Zone lookup table (see below) | Zone X (minimal risk) | Zone AE, VE, or AO | Not a continuous formula — uses FEMA zone codes |
| `water_availability` | `1.0 - clamp(nearest_water_km / 10.0)` + 0.2 bonus if groundwater = "high" | 0 km + high groundwater | 10+ km, no groundwater | Bonus cannot push score above 1.0 |
| `drought_risk` | Level lookup table (see below) | None (no drought) | D4 (exceptional drought) | Scores reflect 30-year historical drought frequency |

**Flood zone score lookup:**

| FEMA Zone | Score | Meaning |
|---|---|---|
| X (unshaded) | 1.0 | Minimal flood risk — outside 500-year floodplain |
| B or X500 (shaded) | 0.7 | Moderate risk — inside 500-year floodplain |
| A (general) | 0.3 | High risk — 100-year floodplain, no detailed study available |
| AE, AO, AH | 0.0 | High risk — 100-year floodplain with detailed base flood elevations |
| VE, V | 0.0 | Coastal high hazard — wave action zone |

**Drought score lookup:**

| USDM Level | Score | Meaning |
|---|---|---|
| None | 1.0 | No drought conditions |
| D0 | 0.9 | Abnormally dry |
| D1 | 0.7 | Moderate drought |
| D2 | 0.5 | Severe drought |
| D3 | 0.2 | Extreme drought |
| D4 | 0.0 | Exceptional drought |

**Weight variable:** `WATER_SUB_WEIGHTS` in `weights.py`

**Default sub-weights:**
```python
WATER_SUB_WEIGHTS: dict[str, float] = {
    "flood_risk":         0.50,
    "water_availability": 0.30,
    "drought_risk":       0.20,
}
```

---

### 5.3 Geological & Terrain

**What it measures:** Earthquake risk, terrain flatness, soil bearing capacity, and proximity to environmental hazards like wetlands and Superfund sites.

**Why it matters for data centers:** Building a massive server hall requires a flat, stable foundation. Grading steep terrain is extremely expensive. Soft or unstable soils require deep pilings that can double foundation costs. Earthquakes can destroy entire facilities — the seismic hazard premium on construction costs in high-risk areas can reach 30–50%. Proximity to wetlands and EPA Superfund sites creates environmental regulatory risk that can delay or block permitting for years.

**Data source:** USGS Seismic Hazard Design API (peak ground acceleration) + USGS 3DEP 1-meter elevation data (slope calculation) + EPA CERCLIS Superfund database + USFWS National Wetlands Inventory

**Sub-metrics and formulas:**

| Sub-Metric | Formula | Best | Worst | Notes |
|---|---|---|---|---|
| `seismic_hazard` | `1.0 - clamp(pga_g / 2.0)` | PGA near 0 g | PGA >= 2.0 g | PGA = Peak Ground Acceleration as fraction of gravity (g) |
| `terrain_slope` | `1.0 - clamp(slope_degrees / 15.0)` | 0 degrees (flat) | 15+ degrees | Calculated from USGS 3DEP 1m elevation grid |
| `soil_stability` | High -> 1.0, Moderate -> 0.6, Low -> 0.2, Unknown -> 0.5 | High bearing capacity | Low bearing capacity | From SSURGO soil survey data via GEE |
| `hazard_proximity` | `clamp(min(wetland_km, superfund_km) / 5.0)` | 5+ km from both | 0 km (on site) | Higher score = farther away from hazards |

**Note on seismic hazard:** PGA of 0.08g is typical for the eastern US (low risk). PGA of 1.5g+ occurs near major fault lines in California, the Pacific Northwest, and parts of the Intermountain West.

**Weight variable:** `GEOLOGICAL_SUB_WEIGHTS` in `weights.py`

**Default sub-weights:**
```python
GEOLOGICAL_SUB_WEIGHTS: dict[str, float] = {
    "seismic_hazard":   0.35,
    "terrain_slope":    0.25,
    "soil_stability":   0.20,
    "hazard_proximity": 0.20,
}
```

---

### 5.4 Climate & Weather

**What it measures:** How much electricity it costs to cool the facility, average humidity levels, and the risk of catastrophic weather events.

**Why it matters for data centers:** Cooling accounts for 30–40% of a data center's total energy bill. A facility in Phoenix, Arizona uses vastly more energy for cooling than one in Wenatchee, Washington — this difference compounds over decades of operation. High humidity increases the risk of condensation on equipment and requires more aggressive environmental controls. A single tornado or hurricane strike can be a total-loss event.

**Data source:** NOAA Climate Data Online 30-year normals (temperature, humidity, storm events) + NASA POWER API (additional climate variables)

**Sub-metrics and formulas:**

| Sub-Metric | Formula | Best | Worst | Notes |
|---|---|---|---|---|
| `cooling_efficiency` | `1.0 - clamp((annual_cdd - 500) / 3500)` | 500 CDD/year | 4,000 CDD/year | CDD = Cooling Degree Days. Below 500 is mountain/northern climate. Above 4,000 is desert Southwest. |
| `humidity` | `1.0 - clamp((avg_rh_pct - 30) / 60)` | 30% average RH | 90% average RH | Annual average relative humidity |
| `tornado_risk` | `1.0 - clamp(tornado_events_per_100sqkm_30yr / 5.0)` | 0 events | 5+ events per 100 sq km | 30-year historical tornado density from NOAA Storm Events |
| `hurricane_risk` | `1.0 - clamp(hurricane_proximity_score / 1.0)` | 0.0 (fully inland) | 1.0 (coastal high risk) | Composite score based on historical track density and distance from coast |
| `hail_risk` | `1.0 - clamp(hail_events_per_100sqkm_30yr / 10.0)` | 0 events | 10+ events per 100 sq km | 30-year historical hail density from NOAA Storm Events |

**Weight variable:** `CLIMATE_SUB_WEIGHTS` in `weights.py`

**Default sub-weights:**
```python
CLIMATE_SUB_WEIGHTS: dict[str, float] = {
    "cooling_efficiency": 0.35,
    "humidity":           0.25,
    "tornado_risk":       0.15,
    "hurricane_risk":     0.15,
    "hail_risk":          0.10,
}
```

---

### 5.5 Connectivity & Access

**What it measures:** Availability of fiber internet infrastructure, proximity to internet exchange points (IXPs), road access for equipment delivery, and airport proximity.

**Why it matters for data centers:** Data centers are fiber-hungry by nature — a hyperscale facility may terminate dozens of diverse fiber routes. Distance to an internet exchange point (where ISPs interconnect) directly affects latency to end users and interconnection costs. Highway access is critical during construction (heavy equipment) and ongoing operations (server hardware shipments). Airport proximity matters for rapid response to critical hardware failures requiring on-site specialists.

**Data source:** OpenStreetMap (fiber conduit routes, highway network) + PeeringDB API (internet exchange point locations) + FAA airport data

**Sub-metrics and formulas:**

| Sub-Metric | Formula | Best | Worst | Notes |
|---|---|---|---|---|
| `fiber_density` | `clamp(fiber_routes_within_5km / 5.0)` | 5+ routes within 5 km | 0 routes | Counts distinct OSM fiber route ways within 5 km radius |
| `ix_proximity` | `1.0 - clamp(nearest_ix_km / 200.0)` | 0 km | 200+ km | Distance to nearest internet exchange point from PeeringDB |
| `road_access` | `1.0 - clamp(nearest_highway_km / 10.0)` | 0 km | 10+ km | Distance to nearest interstate or US highway |
| `airport_proximity` | `1.0 - clamp(nearest_airport_km / 50.0)` | 0 km | 50+ km | Distance to nearest commercial service airport |

**Weight variable:** `CONNECTIVITY_SUB_WEIGHTS` in `weights.py`

**Default sub-weights:**
```python
CONNECTIVITY_SUB_WEIGHTS: dict[str, float] = {
    "fiber_density":     0.40,
    "ix_proximity":      0.30,
    "road_access":       0.20,
    "airport_proximity": 0.10,
}
```

---

### 5.6 Economic Environment

**What it measures:** Corporate tax burden, data center-specific tax incentives, land acquisition costs, availability of skilled labor, and regulatory permitting difficulty.

**Why it matters for data centers:** A 1% difference in corporate tax rate across a $100M data center investment is $1M per year. Many US states have enacted data center-specific tax exemptions on equipment purchases and electricity — these exemptions can save tens of millions of dollars on a large build. Land costs in rural areas can be 100x cheaper than suburban areas while still offering necessary infrastructure. Technical labor availability affects both operational costs and staffing risk.

**Data source:** Curated state corporate tax rate table (maintained in `scoring/economic.py`) + state data center tax exemption list (`DC_TAX_EXEMPTION_STATES` constant) + US Census Bureau API (labor market data) + land listing price data from the listing scraper

**Sub-metrics and formulas:**

| Sub-Metric | Formula | Best | Worst | Notes |
|---|---|---|---|---|
| `tax_environment` | `1.0 - clamp(corp_tax_rate / 12.0)` + 0.2 bonus if state has DC exemption | 0% tax + exemption | 12%+ tax | Bonus cannot push score above 1.0 |
| `land_cost` | `1.0 - clamp(price_per_acre_usd / 50000)` | $0 per acre | $50,000+ per acre | Based on current listing prices in area |
| `labor_market` | `clamp(tech_workers_per_1000_residents / 20.0)` | 20+ tech workers per 1,000 residents | 0 | From Census ACS occupational data |
| `permitting` | Easy -> 1.0, Moderate -> 0.6, Difficult -> 0.2 | Easy (auto-approved) | Difficult (multi-year process) | Curated state/county permitting index |

**States with data center tax exemptions** (as of 2024 — maintained as `DC_TAX_EXEMPTION_STATES` in `app/core/scoring/economic.py`):

NC, VA, TX, GA, TN, CO, AZ, NV, WY, UT, OH, IN, IA, KS, NE, ID, OR, WA, SC, MS

**Weight variable:** `ECONOMIC_SUB_WEIGHTS` in `weights.py`

**Default sub-weights:**
```python
ECONOMIC_SUB_WEIGHTS: dict[str, float] = {
    "tax_environment": 0.30,
    "land_cost":       0.25,
    "labor_market":    0.25,
    "permitting":      0.20,
}
```

---

### 5.7 Environmental Impact

**What it measures:** How much the data center will impact nearby communities, and how much nearby communities may impact the data center's regulatory environment.

**Why it matters for data centers:** A data center near a dense residential area faces noise ordinance challenges, community opposition during permitting, and higher property acquisition costs for the surrounding buffer. Proximity to schools and hospitals adds regulatory scrutiny in most jurisdictions. Poor air quality at a site creates additional environmental review requirements. Protected land designations within 1 km can trigger federal environmental review under NEPA, adding years to permitting timelines.

**Data source:** EPA AirNow API (Air Quality Index) + US Census Bureau (population by block group) + OpenStreetMap (school and hospital locations) + GEE NLCD land cover classification

**Sub-metrics and formulas:**

| Sub-Metric | Formula | Best | Worst | Notes |
|---|---|---|---|---|
| `population_proximity` | `1.0 - clamp(population_within_5km / 50000)` | 0 people | 50,000+ people | Census block group population summed within 5 km radius |
| `sensitive_sites` | `clamp(min(nearest_school_km, nearest_hospital_km) / 2.0)` | 2+ km from both | 0 km (directly adjacent) | Whichever is closer: nearest school or nearest hospital |
| `air_quality` | `1.0 - clamp(aqi / 300.0)` | AQI 0 (perfect) | AQI 300+ (hazardous) | EPA AQI annual average |
| `land_sensitivity` | `0.0 if protected_land_within_1km else 1.0` | No protected land nearby | Protected land within 1 km | Binary: National parks, wilderness areas, wildlife refuges |

**Weight variable:** `ENVIRONMENTAL_SUB_WEIGHTS` in `weights.py`

**Default sub-weights:**
```python
ENVIRONMENTAL_SUB_WEIGHTS: dict[str, float] = {
    "population_proximity": 0.35,
    "sensitive_sites":      0.30,
    "air_quality":          0.20,
    "land_sensitivity":     0.15,
}
```

---

## 6. How to Add a New Scoring Category

Follow these 9 steps exactly. Do not skip any step.

### Step 1: Add the category weight to `weights.py`

```python
CATEGORY_WEIGHTS: dict[str, float] = {
    # ... existing categories ...
    "my_new_category": 0.10,   # Add this line
}
```

### Step 2: Add the sub-weights to `weights.py`

```python
MY_NEW_CATEGORY_SUB_WEIGHTS: dict[str, float] = {
    "sub_metric_a": 0.60,
    "sub_metric_b": 0.40,
}
# Sub-weights MUST sum to exactly 1.0
```

### Step 3: Add a new metrics model to `app/models/responses.py`

```python
class MyNewCategoryMetrics(BaseModel):
    my_raw_value_a: float          # The actual measured value (not the 0-1 score)
    my_raw_value_b: str            # Can be string for categorical values
```

### Step 4: Add it to `ScoreMetrics` in `app/models/responses.py`

```python
class ScoreMetrics(BaseModel):
    power:           PowerMetrics
    water:           WaterMetrics
    geological:      GeologicalMetrics
    climate:         ClimateMetrics
    connectivity:    ConnectivityMetrics
    economic:        EconomicMetrics
    environmental:   EnvironmentalMetrics
    my_new_category: MyNewCategoryMetrics   # Add this line
```

### Step 5: Add a new integration client (if your data comes from a new source)

Create `app/integrations/my_source.py` following the pattern in `integrations/base.py`. The class must:
- Extend `BaseIntegrationClient`
- Return mock data when `self.mock` is `True`
- Cache results in Redis

### Step 6: Create the scorer at `app/core/scoring/my_new_category.py`

```python
from app.core.scoring.base import BaseScorer
from app.core.scoring.weights import MY_NEW_CATEGORY_SUB_WEIGHTS
from app.models.domain import BoundingBox, CellScore

class MyNewCategoryScorer(BaseScorer):
    category_id = "my_new_category"   # Must match key in CATEGORY_WEIGHTS

    def __init__(self, my_integration_client, redis_client, settings):
        self.client = my_integration_client
        super().__init__(redis_client, settings)

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        # 1. Fetch raw data from your integration client
        raw_data = await self.client.get_my_data(bbox)

        results = []
        for cell in generate_grid(bbox):
            # 2. Compute sub-metric scores (each 0.0-1.0)
            sub_a_score = self._clamp(raw_data[cell]["value_a"] / 100.0)
            sub_b_score = 1.0 - self._clamp(raw_data[cell]["value_b"] / 50.0)

            # 3. Combine sub-metrics using sub-weights from weights.py
            category_score = (
                sub_a_score * MY_NEW_CATEGORY_SUB_WEIGHTS["sub_metric_a"] +
                sub_b_score * MY_NEW_CATEGORY_SUB_WEIGHTS["sub_metric_b"]
            )

            results.append(CellScore(
                lat=cell.lat,
                lng=cell.lng,
                raw_scores={"my_new_category": category_score},
                sub_scores={"sub_metric_a": sub_a_score, "sub_metric_b": sub_b_score},
                metrics={
                    "my_raw_value_a": raw_data[cell]["value_a"],
                    "my_raw_value_b": raw_data[cell]["value_b"],
                },
            ))

        return results
```

### Step 7: Register the scorer in `engine.py`

Open `app/core/scoring/engine.py`. Add your scorer to the `create_scoring_engine()` factory function and to the `asyncio.gather()` call inside `score_region()`.

### Step 8: Create a layer builder at `app/core/layers/my_new_category_layer.py`

```python
from app.core.layers.base import BaseLayerBuilder
from app.models.responses import ScoreBundle

class MyNewCategoryLayerBuilder(BaseLayerBuilder):
    layer_id = "my_new_category"
    label = "My New Category"
    description = "Scores locations based on ..."

    def build(self, score_bundles: list[ScoreBundle]) -> dict:
        features = []
        for bundle in score_bundles:
            score = bundle.scores["my_new_category"]
            features.append({
                "type": "Feature",
                "geometry": bundle.location.cell_polygon,
                "properties": {
                    "layer_id": self.layer_id,
                    "score": score,
                    "label": f"My Category: {self._score_label(score)}",
                    "color_hex": self._score_to_color(score),
                    "metrics": {
                        "my_raw_value_a": bundle.metrics.my_new_category.my_raw_value_a,
                    }
                }
            })
        return {"type": "FeatureCollection", "features": features}
```

### Step 9: Add the category to `/scoring/schema` in `app/api/v1/scoring_schema.py`

Add an entry to the `categories` list in the schema endpoint. Import `MY_NEW_CATEGORY_SUB_WEIGHTS` from `weights.py` — never hardcode values in the endpoint.

---

## 7. Accessing Scores in Code

```python
from app.core.scoring.engine import create_scoring_engine
from app.models.domain import BoundingBox

# Create engine with all scorers injected
engine = create_scoring_engine(redis_client=redis, settings=settings)

# Define a bounding box (Research Triangle, NC)
bbox = BoundingBox(min_lat=35.7, min_lng=-79.2, max_lat=36.2, max_lng=-78.6)

# Run full analysis
# Returns list[ScoreBundle] sorted by composite score descending (best first)
bundles = await engine.score_region(bbox, grid_resolution_km=5.0)


# ---- Read the composite score --------------------------------------------
bundles[0].composite_score.composite        # 0.774 -- best location in the grid
bundles[-1].composite_score.composite       # 0.521 -- worst location in the grid


# ---- Read individual category scores (raw 0.0-1.0, before weight application) ----
bundles[0].scores["power"]                  # 0.82
bundles[0].scores["water"]                  # 0.91
bundles[0].scores["geological"]             # 0.78
bundles[0].scores["climate"]                # 0.85
bundles[0].scores["connectivity"]           # 0.65
bundles[0].scores["economic"]               # 0.72
bundles[0].scores["environmental"]          # 0.55


# ---- Read the actual measured values (the raw data behind each score) ----
bundles[0].metrics.power.electricity_rate_cents_per_kwh   # 8.2
bundles[0].metrics.power.nearest_substation_km            # 1.8
bundles[0].metrics.water.fema_flood_zone                  # "X"
bundles[0].metrics.geological.seismic_hazard_pga          # 0.08
bundles[0].metrics.climate.annual_cooling_degree_days     # 1850.0
bundles[0].metrics.climate.avg_humidity_pct               # 71.0
bundles[0].metrics.economic.data_center_tax_exemption     # True
bundles[0].metrics.connectivity.fiber_routes_within_5km   # 3
bundles[0].metrics.environmental.population_within_5km    # 4200


# ---- Read how weights were applied ---------------------------------------
bundles[0].composite_score.weighted_contributions
# {"power": 0.164, "water": 0.137, "geological": 0.117,
#  "climate": 0.128, "connectivity": 0.065, "economic": 0.108, "environmental": 0.055}

bundles[0].composite_score.weights_used
# {"power": 0.20, "water": 0.15, "geological": 0.15,
#  "climate": 0.15, "connectivity": 0.10, "economic": 0.15, "environmental": 0.10}


# ---- Find the top 5 locations --------------------------------------------
top_5 = bundles[:5]
for bundle in top_5:
    lat = bundle.location.lat
    lng = bundle.location.lng
    score = bundle.composite_score.composite
    print(f"({lat:.4f}, {lng:.4f}) -> composite: {score:.3f}")


# ---- Run a single scorer in isolation (useful for testing one category) --
from app.core.scoring.power import PowerScorer

scorer = PowerScorer(osm_client=osm, eia_client=eia, redis_client=redis, settings=settings)
cell_scores = await scorer.score(bbox)

cell_scores[0].raw_scores["power"]   # The combined power category score: 0.82
cell_scores[0].sub_scores
# {"grid_proximity": 0.91, "electricity_cost": 0.87,
#  "renewable_pct": 0.65, "grid_reliability": 0.80}
cell_scores[0].metrics
# {"nearest_substation_km": 1.8, "electricity_rate_cents_per_kwh": 8.2, ...}


# ---- Filter to only cells above a threshold ------------------------------
high_quality = [b for b in bundles if b.composite_score.composite >= 0.70]
print(f"{len(high_quality)} out of {len(bundles)} cells scored above 70%")


# ---- Check which category is dragging down a specific location -----------
worst_category = min(bundles[0].scores.items(), key=lambda x: x[1])
print(f"Weakest category: {worst_category[0]} with raw score {worst_category[1]:.3f}")
```

---

## 8. Score Debugging Guide

### Enable debug logging

Set `LOG_LEVEL=DEBUG` in your `.env` file before starting the server:

```bash
# In your .env file:
LOG_LEVEL=DEBUG
MOCK_INTEGRATIONS=true

# Then start:
uvicorn app.main:app --reload
```

Debug logging shows:
- Which integration client was called (real API) or skipped (mock mode)
- Redis cache hits and misses for each data source
- Per-cell scoring results from each scorer
- Integration errors with which grid cell was affected
- Timing information for each scorer

### What debug output looks like

```
INFO  ScoringEngine: Starting analysis for BoundingBox(min_lat=35.7, min_lng=-79.2, ...)
INFO  ScoringEngine: Grid resolution 5.0 km -> 36 candidate cells
INFO  Launching 7 scorers in parallel via asyncio.gather
DEBUG OSMClient: Cache MISS for key integration:osm:substations:35.7:-79.2:36.2:-78.6
DEBUG OSMClient: Fetching substations from Overpass API...
DEBUG OSMClient: Cache HIT for key integration:eia:electricity_rate:NC
DEBUG EIAClient: Returning cached rate: 8.2 cents/kWh
INFO  PowerScorer: Scored 36 cells. Min=0.41 Max=0.88 Mean=0.67
INFO  WaterScorer: Scored 36 cells. Min=0.55 Max=1.00 Mean=0.84
INFO  GeologicalScorer: Scored 36 cells. Min=0.63 Max=0.95 Mean=0.79
INFO  ClimateScorer: Scored 36 cells. Min=0.52 Max=0.91 Mean=0.71
INFO  ConnectivityScorer: Scored 36 cells. Min=0.21 Max=0.78 Mean=0.54
INFO  EconomicScorer: Scored 36 cells. Min=0.48 Max=0.89 Mean=0.69
INFO  EnvironmentalScorer: Scored 36 cells. Min=0.60 Max=0.98 Mean=0.81
INFO  ScoringEngine: All 7 scorers complete. Merging 36 cells.
INFO  ScoringEngine: Top composite score: 0.7841 at (35.9500, -78.8500)
```

### Diagnosing an unexpectedly low score

1. Identify the cell you are investigating. Look at `bundle.composite_score.composite`.
2. Find the weakest category score: compare all values in `bundle.scores`.
3. Look at `bundle.composite_score.weighted_contributions` — which category is pulling the composite down most?
4. Look at the raw metric values for that category: `bundle.metrics.{category}.{metric_name}`.
5. That raw metric value tells you what the integration client returned, which tells you what data source is responsible.

**Example: Power score is 0.31 — why?**

```python
bundle.scores["power"]                                    # 0.31 -- confirmed low
bundle.metrics.power.electricity_rate_cents_per_kwh       # 17.8 -- electricity is expensive here
bundle.metrics.power.nearest_substation_km                # 2.1  -- substation proximity is fine

# Conclusion: The electricity rate is driving the low power score.
# The electricity_cost formula: 1.0 - clamp((17.8 - 5.0) / 15.0) = 1.0 - 0.853 = 0.147
# This low sub-score is heavily weighted (0.35) and drags the combined power score down.
```

### Verify weight changes took effect after deployment

```bash
curl http://localhost:8000/api/v1/scoring/schema | python -m json.tool | grep -A 10 "current_weights"
```

The `current_weights` field is read directly from `weights.py` at runtime on every request. If your updated values do not appear here, the deployment did not complete successfully.

### Test a single scorer without running the full analysis

```bash
# Run with mock data to check one scorer's behavior in isolation
MOCK_INTEGRATIONS=true python -c "
import asyncio
from app.core.scoring.power import PowerScorer
from app.models.domain import BoundingBox
from app.config import get_settings

settings = get_settings()
scorer = PowerScorer(osm_client=None, eia_client=None, redis_client=None, settings=settings)
bbox = BoundingBox(min_lat=35.7, min_lng=-79.2, max_lat=36.2, max_lng=-78.6)
results = asyncio.run(scorer.score(bbox))
print(f'Scored {len(results)} cells')
min_score = min(r.raw_scores['power'] for r in results)
max_score = max(r.raw_scores['power'] for r in results)
print(f'Score range: {min_score:.3f} - {max_score:.3f}')
"
```
