"""
app/core/layers/connectivity_layer.py
───────────────────────────────────────
Builds the Connectivity & Access GeoJSON layer.
Score source: bundle.scores.get("connectivity")
Label example: "Connectivity: High — 3 fiber routes, IX 72km"
"""

from app.core.layers.base import BaseLayerBuilder
from app.models.responses import ScoreBundle


class ConnectivityLayerBuilder(BaseLayerBuilder):
    layer_id = "connectivity"
    label = "Connectivity & Access"
    description = (
        "Scores each location based on fiber optic route density, "
        "distance to internet exchange points, highway access, and airport proximity."
    )

    def build(self, score_bundles: list[ScoreBundle]) -> dict:
        features = []
        scores = []

        for bundle in score_bundles:
            score = bundle.scores.get("connectivity", 0.0)
            scores.append(score)
            m = bundle.metrics.connectivity

            quality = "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"
            label = (
                f"Connectivity: {quality} — {m.fiber_routes_within_5km} fiber routes, "
                f"IX {m.nearest_ix_point_km:.0f}km"
            )
            metrics_subset = {
                "fiber_routes_within_5km": m.fiber_routes_within_5km,
                "nearest_ix_point_km": m.nearest_ix_point_km,
                "nearest_highway_km": m.nearest_highway_km,
                "nearest_airport_km": m.nearest_airport_km,
            }
            features.append(self._make_feature(bundle, score, label, metrics_subset))

        return self._make_feature_collection(features, self._score_range(scores))
