"""
app/core/layers/water_layer.py
───────────────────────────────
Builds the Water & Flood Risk GeoJSON layer.
Score source: bundle.scores.get("water")
Label example: "Water: High — Zone X, Drought: None"
"""

from app.core.layers.base import BaseLayerBuilder
from app.models.responses import ScoreBundle


class WaterLayerBuilder(BaseLayerBuilder):
    layer_id = "water"
    label = "Water & Flood Risk"
    description = (
        "Scores each location based on FEMA flood zone designation, "
        "proximity to water bodies for cooling, and drought risk level."
    )

    def build(self, score_bundles: list[ScoreBundle]) -> dict:
        features = []
        scores = []

        for bundle in score_bundles:
            score = bundle.scores.get("water", 0.0)
            scores.append(score)
            m = bundle.metrics.water

            quality = "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"
            label = (
                f"Water: {quality} — Zone {m.fema_flood_zone}, "
                f"Drought: {m.drought_risk_level}"
            )
            metrics_subset = {
                "fema_flood_zone": m.fema_flood_zone,
                "flood_risk_pct": m.flood_risk_pct,
                "nearest_water_body_km": m.nearest_water_body_km,
                "groundwater_availability": m.groundwater_availability,
                "drought_risk_level": m.drought_risk_level,
            }
            features.append(self._make_feature(bundle, score, label, metrics_subset))

        return self._make_feature_collection(features, self._score_range(scores))
