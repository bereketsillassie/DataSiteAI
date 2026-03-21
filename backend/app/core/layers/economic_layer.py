"""
app/core/layers/economic_layer.py
───────────────────────────────────
Builds the Economic Environment GeoJSON layer.
Score source: bundle.scores.get("economic")
Label example: "Economic: High — 2.5% corp tax, $8,500/acre"
"""

from app.core.layers.base import BaseLayerBuilder
from app.models.responses import ScoreBundle


class EconomicLayerBuilder(BaseLayerBuilder):
    layer_id = "economic"
    label = "Economic Environment"
    description = (
        "Scores each location based on state corporate tax rates, data center tax exemptions, "
        "land costs, tech labor availability, and permitting ease."
    )

    def build(self, score_bundles: list[ScoreBundle]) -> dict:
        features = []
        scores = []

        for bundle in score_bundles:
            score = bundle.scores.get("economic", 0.0)
            scores.append(score)
            m = bundle.metrics.economic

            quality = "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"
            exemption_str = " + DC exemption" if m.data_center_tax_exemption else ""
            label = (
                f"Economic: {quality} — {m.state_corporate_tax_rate_pct:.1f}% corp tax"
                f"{exemption_str}, ${m.median_land_cost_per_acre_usd:,.0f}/acre"
            )
            metrics_subset = {
                "state_corporate_tax_rate_pct": m.state_corporate_tax_rate_pct,
                "data_center_tax_exemption": m.data_center_tax_exemption,
                "permitting_difficulty": m.permitting_difficulty,
                "median_electrician_wage_usd": m.median_electrician_wage_usd,
                "median_land_cost_per_acre_usd": m.median_land_cost_per_acre_usd,
                "tech_workers_per_1000_residents": m.tech_workers_per_1000_residents,
            }
            features.append(self._make_feature(bundle, score, label, metrics_subset))

        return self._make_feature_collection(features, self._score_range(scores))
