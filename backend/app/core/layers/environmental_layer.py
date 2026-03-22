"""
app/core/layers/environmental_layer.py
────────────────────────────────────────
Builds the Environmental Impact GeoJSON layer.
Score source: bundle.scores.get("environmental")
Label example: "Environmental: High — 4,200 pop within 5km, AQI 42"
"""

from app.core.layers.base import BaseLayerBuilder
from app.models.responses import ScoreBundle


class EnvironmentalLayerBuilder(BaseLayerBuilder):
    layer_id = "environmental"
    label = "Environmental Impact"
    description = (
        "Scores each location based on population density within 5km, proximity to schools and hospitals, "
        "air quality index, and whether the site is near protected land or wetlands."
    )

    def build(self, score_bundles: list[ScoreBundle]) -> dict:
        features = []
        scores = []

        for bundle in score_bundles:
            score = bundle.scores.get("environmental", 0.0)
            scores.append(score)
            m = bundle.metrics.environmental

            quality = "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"
            protected_str = " - Protected land nearby" if m.protected_land_within_1km else ""
            label = (
                f"Environmental: {quality} — {m.population_within_5km:,} pop/5km, "
                f"AQI {m.air_quality_index:.0f}{protected_str}"
            )
            metrics_subset = {
                "population_within_5km": m.population_within_5km,
                "nearest_school_km": m.nearest_school_km,
                "nearest_hospital_km": m.nearest_hospital_km,
                "air_quality_index": m.air_quality_index,
                "protected_land_within_1km": m.protected_land_within_1km,
                "land_cover_type": m.land_cover_type,
            }
            features.append(self._make_feature(bundle, score, label, metrics_subset))

        return self._make_feature_collection(features, self._score_range(scores))
