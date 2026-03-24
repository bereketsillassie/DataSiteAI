"""
app/core/scoring/weights.py
────────────────────────────
SCORING WEIGHTS CONFIGURATION
==============================
This is the ONLY file you need to edit to change how locations are scored.

HOW IT WORKS:
  1. Each location is scored in 7 categories (power, water, geological, etc.)
  2. Each category produces a raw score from 0.0 (worst) to 1.0 (best)
  3. CATEGORY_WEIGHTS controls how much each category influences the final score
  4. Sub-metric weights control how individual data points roll up to a category score

RULES:
  - Weights are relative — they do NOT need to sum to 1.0
    The engine normalizes them automatically
  - Set a weight to 0.0 to completely exclude that category
  - Higher number = more influence on final score

TO APPLY CHANGES: edit the values below and restart the server.
"""

CATEGORY_WEIGHTS: dict[str, float] = {
    "power":         0.20,  # Grid proximity, electricity cost, renewables
    "water":         0.15,  # Flood risk, water availability, drought
    "geological":    0.15,  # Seismic hazard, terrain slope, soil
    "climate":       0.15,  # Cooling efficiency, humidity, disaster risk
    "connectivity":  0.10,  # Fiber density, IXP distance, roads
    "economic":      0.15,  # Tax incentives, zoning, labor, land cost
    "environmental": 0.10,  # Human impact, wetlands, EPA proximity
}

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
    "seismic_hazard":   0.35,
    "terrain_slope":    0.25,
    "soil_stability":   0.20,
    "hazard_proximity": 0.20,
}

CLIMATE_SUB_WEIGHTS: dict[str, float] = {
    "cooling_efficiency": 0.35,
    "humidity":           0.25,
    "tornado_risk":       0.15,
    "hurricane_risk":     0.15,
    "hail_risk":          0.10,
}

CONNECTIVITY_SUB_WEIGHTS: dict[str, float] = {
    "fiber_density":     0.40,
    "ix_proximity":      0.30,
    "road_access":       0.20,
    "airport_proximity": 0.10,
}

ECONOMIC_SUB_WEIGHTS: dict[str, float] = {
    "tax_environment": 0.30,
    "land_cost":       0.25,
    "labor_market":    0.25,
    "permitting":      0.20,
}

ENVIRONMENTAL_SUB_WEIGHTS: dict[str, float] = {
    "population_proximity": 0.35,
    "sensitive_sites":      0.30,
    "air_quality":          0.20,
    "land_sensitivity":     0.15,
}
