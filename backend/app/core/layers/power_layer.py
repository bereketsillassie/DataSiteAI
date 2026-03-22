"""
app/core/layers/power_layer.py
───────────────────────────────
Builds the Power & Energy GeoJSON layer.
Score source: bundle.scores.get("power")
Label example: "Power: High — Substation 2.1km, 8.2¢/kWh"
"""

from app.core.layers.base import BaseLayerBuilder
from app.models.responses import ScoreBundle


class PowerLayerBuilder(BaseLayerBuilder):
    layer_id = "power"
    label = "Power & Energy"
    description = (
        "Scores each location based on proximity to electrical substations and transmission lines, "
        "commercial electricity rates, percentage of renewable energy, and grid reliability."
    )

    def build(self, score_bundles: list[ScoreBundle]) -> dict:
        features = []
        scores = []

        for bundle in score_bundles:
            score = bundle.scores.get("power", 0.0)
            scores.append(score)
            m = bundle.metrics.power

            label = self._make_label(score, m.nearest_substation_km, m.electricity_rate_cents_per_kwh)
            metrics_subset = {
                "nearest_substation_km": m.nearest_substation_km,
                "nearest_transmission_line_km": m.nearest_transmission_line_km,
                "electricity_rate_cents_per_kwh": m.electricity_rate_cents_per_kwh,
                "renewable_energy_pct": m.renewable_energy_pct,
                "grid_reliability_index": m.grid_reliability_index,
                "utility_territory": m.utility_territory,
            }
            features.append(self._make_feature(bundle, score, label, metrics_subset))

        return self._make_feature_collection(features, self._score_range(scores))

    def _make_label(self, score: float, substation_km: float, rate: float) -> str:
        quality = "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"
        return f"Power: {quality} — Substation {substation_km:.1f}km, {rate:.1f}\u00a2/kWh"
