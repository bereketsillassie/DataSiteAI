# =============================================================================
# app/core/scoring/weights.py
# =============================================================================
#
# ┌─────────────────────────────────────────────────────────────────────────┐
# │  SCORING WEIGHTS — THE ONLY FILE YOU NEED TO EDIT TO CHANGE SCORES     │
# └─────────────────────────────────────────────────────────────────────────┘
#
# WHO SHOULD EDIT THIS FILE:
#   The scoring partner. This is the only file in the entire codebase that
#   controls how locations are ranked. Everything else (the math, the data
#   fetching, the API) is off-limits and you don't need to touch it.
#
# WHAT THIS FILE DOES:
#   Each land parcel gets scored in 7 categories:
#     1. power         — How good is the electrical grid nearby?
#     2. water         — Is it in a flood zone? Is water available?
#     3. geological    — Any earthquake risk? Is the terrain flat?
#     4. climate       — Is it hot and humid? Tornado/hurricane risk?
#     5. connectivity  — Is there fiber internet nearby? Major highways?
#     6. economic      — Low taxes? Cheap land? Available skilled workers?
#     7. environmental — Far from dense population? Good air quality?
#
#   Within each category, there are sub-metrics (individual data points).
#   Example: the "power" category uses 4 sub-metrics:
#     - grid_proximity   (how close to a substation)
#     - electricity_cost (cents per kWh)
#     - renewable_pct    (% of power from renewables)
#     - grid_reliability (how often does the power go out?)
#
# HOW SCORING WORKS (simplified):
#   1. Each sub-metric is scored from 0.0 (worst possible) to 1.0 (best possible)
#   2. Sub-metric scores are combined using the sub-weights below → category score
#   3. The 7 category scores are combined using CATEGORY_WEIGHTS → final score
#
# HOW TO CHANGE A WEIGHT:
#   ✅ Find the weight you want to change below
#   ✅ Change the number on the right side of the colon
#   ✅ Save the file, commit, and redeploy
#   ✅ That's it. The engine handles everything else automatically.
#
# IMPORTANT RULES:
#   • Weights in CATEGORY_WEIGHTS do NOT need to add up to 1.0 (or any specific total)
#     The system normalizes them automatically.
#     Example: {power: 2, water: 1} is the same as {power: 0.67, water: 0.33}
#
#   • Weights in each {CATEGORY}_SUB_WEIGHTS MUST add up to 1.0 exactly.
#     (The system checks this and will log a warning if they don't.)
#
#   • To completely DISABLE a category: set its weight to 0.0
#     Example: "environmental": 0.0  ← this category is ignored entirely
#
#   • Minimum weight value: 0.0 (disabled)
#   • Maximum weight value: any positive number (there's no cap)
#
# FULL DOCUMENTATION: docs/SCORING_INTERNALS.md
# =============================================================================


# -----------------------------------------------------------------------------
# CATEGORY WEIGHTS
# Controls how much each of the 7 categories influences the final score.
# Higher number = more influence on where a data center should be built.
# -----------------------------------------------------------------------------
CATEGORY_WEIGHTS: dict[str, float] = {
    "power":          0.20,   # ← Electrical grid quality and cost
    "water":          0.15,   # ← Flood risk and water availability
    "geological":     0.15,   # ← Earthquake risk and terrain
    "climate":        0.15,   # ← Heat, humidity, and weather disasters
    "connectivity":   0.10,   # ← Fiber internet and road access
    "economic":       0.15,   # ← Taxes, land cost, and labor market
    "environmental":  0.10,   # ← Proximity to people and protected land
}


# -----------------------------------------------------------------------------
# POWER SUB-WEIGHTS  (must sum to 1.0)
# Controls how the 4 power metrics combine into the power category score.
# -----------------------------------------------------------------------------
POWER_SUB_WEIGHTS: dict[str, float] = {
    "grid_proximity":    0.35,  # ← Distance to nearest substation/transmission line
    "electricity_cost":  0.35,  # ← Commercial electricity rate (cents per kWh)
    "renewable_pct":     0.20,  # ← What % of local power comes from renewables
    "grid_reliability":  0.10,  # ← How reliable is the grid (fewer outages = better)
}
# Sum check: 0.35 + 0.35 + 0.20 + 0.10 = 1.00 ✓


# -----------------------------------------------------------------------------
# WATER SUB-WEIGHTS  (must sum to 1.0)
# Controls how the 3 water metrics combine into the water category score.
# -----------------------------------------------------------------------------
WATER_SUB_WEIGHTS: dict[str, float] = {
    "flood_risk":          0.50,  # ← FEMA flood zone (Zone X = safe, Zone AE = danger)
    "water_availability":  0.30,  # ← Distance to rivers/lakes for cooling water
    "drought_risk":        0.20,  # ← USDM drought classification for the area
}
# Sum check: 0.50 + 0.30 + 0.20 = 1.00 ✓


# -----------------------------------------------------------------------------
# GEOLOGICAL SUB-WEIGHTS  (must sum to 1.0)
# Controls how the 4 geological metrics combine into the geological score.
# -----------------------------------------------------------------------------
GEOLOGICAL_SUB_WEIGHTS: dict[str, float] = {
    "seismic_hazard":   0.35,  # ← Earthquake risk (PGA value from USGS)
    "terrain_slope":    0.25,  # ← How steep is the land (flatter = easier to build on)
    "soil_stability":   0.20,  # ← Soil bearing capacity for heavy server buildings
    "hazard_proximity": 0.20,  # ← Distance from wetlands and Superfund sites
}
# Sum check: 0.35 + 0.25 + 0.20 + 0.20 = 1.00 ✓


# -----------------------------------------------------------------------------
# CLIMATE SUB-WEIGHTS  (must sum to 1.0)
# Controls how the 5 climate metrics combine into the climate category score.
# -----------------------------------------------------------------------------
CLIMATE_SUB_WEIGHTS: dict[str, float] = {
    "cooling_efficiency":  0.35,  # ← Annual cooling degree days (fewer = cheaper cooling)
    "humidity":            0.25,  # ← Average relative humidity (lower = better for servers)
    "tornado_risk":        0.15,  # ← Historical tornado frequency per 100 sq km
    "hurricane_risk":      0.15,  # ← Proximity to historical hurricane paths
    "hail_risk":           0.10,  # ← Historical hail event frequency per 100 sq km
}
# Sum check: 0.35 + 0.25 + 0.15 + 0.15 + 0.10 = 1.00 ✓


# -----------------------------------------------------------------------------
# CONNECTIVITY SUB-WEIGHTS  (must sum to 1.0)
# Controls how the 4 connectivity metrics combine into the connectivity score.
# -----------------------------------------------------------------------------
CONNECTIVITY_SUB_WEIGHTS: dict[str, float] = {
    "fiber_density":      0.40,  # ← Number of fiber routes within 5 km
    "ix_proximity":       0.30,  # ← Distance to nearest internet exchange point
    "road_access":        0.20,  # ← Distance to nearest highway
    "airport_proximity":  0.10,  # ← Distance to nearest commercial airport
}
# Sum check: 0.40 + 0.30 + 0.20 + 0.10 = 1.00 ✓


# -----------------------------------------------------------------------------
# ECONOMIC SUB-WEIGHTS  (must sum to 1.0)
# Controls how the 4 economic metrics combine into the economic score.
# -----------------------------------------------------------------------------
ECONOMIC_SUB_WEIGHTS: dict[str, float] = {
    "tax_environment":  0.30,  # ← Corporate tax rate + data center tax exemptions
    "land_cost":        0.25,  # ← Median land price per acre in the area
    "labor_market":     0.25,  # ← Tech worker density in the region
    "permitting":       0.20,  # ← How easy/hard is it to get permits?
}
# Sum check: 0.30 + 0.25 + 0.25 + 0.20 = 1.00 ✓


# -----------------------------------------------------------------------------
# ENVIRONMENTAL SUB-WEIGHTS  (must sum to 1.0)
# Controls how the 4 environmental metrics combine into the environmental score.
# Note: "environmental" here means "proximity to sensitive things" — lower
# population nearby is BETTER for a data center (noise, traffic, opposition).
# -----------------------------------------------------------------------------
ENVIRONMENTAL_SUB_WEIGHTS: dict[str, float] = {
    "population_proximity":  0.35,  # ← People within 5 km (fewer = better)
    "sensitive_sites":       0.30,  # ← Distance from schools and hospitals
    "air_quality":           0.20,  # ← EPA AQI (lower = cleaner air)
    "land_sensitivity":      0.15,  # ← Protected/conservation land nearby
}
# Sum check: 0.35 + 0.30 + 0.20 + 0.15 = 1.00 ✓
