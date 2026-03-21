"""
app/core/layers/optimal_layer.py
──────────────────────────────────
Builds the Optimal Score GeoJSON layer.
This is the most important layer — it shows the composite weighted score
that combines all 7 categories according to weights.py.

Score source: bundle.composite_score.composite
Label example: "Optimal Score: 0.87 — Power 22%, Water 17%, Geological 15%"
"""

from app.core.layers.base import BaseLayerBuilder
from app.models.responses import ScoreBundle


class OptimalLayerBuilder(BaseLayerBuilder):
    layer_id = "optimal"
    label = "Optimal Data Center Score"
    description = (
        "The composite weighted score combining all 7 categories according to the "
        "weights defined in weights.py. Higher score = better data center location."
    )

    def build(self, score_bundles: list[ScoreBundle]) -> dict:
        features = []
        scores = []

        for bundle in score_bundles:
            composite = bundle.composite_score.composite
            scores.append(composite)

            contributions = bundle.composite_score.weighted_contributions
            label = self._make_label(composite, contributions)

            # Include full breakdown for the optimal layer
            metrics_subset = {
                "composite": composite,
                "weighted_contributions": contributions,
                "weights_used": bundle.composite_score.weights_used,
                "raw_category_scores": bundle.scores,
            }
            features.append(self._make_feature(bundle, composite, label, metrics_subset))

        return self._make_feature_collection(features, self._score_range(scores))

    def _make_label(self, composite: float, contributions: dict[str, float]) -> str:
        """
        Build a human-readable label showing the composite score and
        the top 3 contributing categories.
        """
        # Sort contributions by value descending
        top = sorted(contributions.items(), key=lambda x: x[1], reverse=True)[:3]
        total = sum(contributions.values()) or 1.0
        top_str = ", ".join(
            f"{cat.capitalize()} {v / total * 100:.0f}%"
            for cat, v in top
        )
        return f"Optimal Score: {composite:.2f} — {top_str}"
