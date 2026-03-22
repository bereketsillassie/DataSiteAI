"""
app/core/layers/geological_layer.py
─────────────────────────────────────
Builds the Geological & Terrain GeoJSON layer.
Score source: bundle.scores.get("geological")
Label example: "Geology: High — PGA 0.08g, Slope 1.5°"
"""

from app.core.layers.base import BaseLayerBuilder
from app.models.responses import ScoreBundle


class GeologicalLayerBuilder(BaseLayerBuilder):
    layer_id = "geological"
    label = "Geological & Terrain"
    description = (
        "Scores each location based on seismic hazard (USGS PGA), terrain slope, "
        "soil bearing capacity, and distance from wetlands and Superfund sites."
    )

    def build(self, score_bundles: list[ScoreBundle]) -> dict:
        features = []
        scores = []

        for bundle in score_bundles:
            score = bundle.scores.get("geological", 0.0)
            scores.append(score)
            m = bundle.metrics.geological

            quality = "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"
            label = (
                f"Geology: {quality} — PGA {m.seismic_hazard_pga:.2f}g, "
                f"Slope {m.slope_degrees:.1f}\u00b0"
            )
            metrics_subset = {
                "seismic_hazard_pga": m.seismic_hazard_pga,
                "slope_degrees": m.slope_degrees,
                "elevation_m": m.elevation_m,
                "soil_bearing_capacity": m.soil_bearing_capacity,
                "nearest_wetland_km": m.nearest_wetland_km,
                "nearest_superfund_km": m.nearest_superfund_km,
            }
            features.append(self._make_feature(bundle, score, label, metrics_subset))

        return self._make_feature_collection(features, self._score_range(scores))
