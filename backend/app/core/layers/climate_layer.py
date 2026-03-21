"""
app/core/layers/climate_layer.py
──────────────────────────────────
Builds the Climate & Weather GeoJSON layer.
Score source: bundle.scores.get("climate")
Label example: "Climate: High — 1850 CDD, 71% humidity"
"""

from app.core.layers.base import BaseLayerBuilder
from app.models.responses import ScoreBundle


class ClimateLayerBuilder(BaseLayerBuilder):
    layer_id = "climate"
    label = "Climate & Weather Risk"
    description = (
        "Scores each location based on annual cooling degree days, average humidity, "
        "and risk of tornadoes, hurricanes, and hail events."
    )

    def build(self, score_bundles: list[ScoreBundle]) -> dict:
        features = []
        scores = []

        for bundle in score_bundles:
            score = bundle.scores.get("climate", 0.0)
            scores.append(score)
            m = bundle.metrics.climate

            quality = "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"
            label = (
                f"Climate: {quality} — {int(m.annual_cooling_degree_days)} CDD, "
                f"{m.avg_humidity_pct:.0f}% humidity"
            )
            metrics_subset = {
                "avg_annual_temp_c": m.avg_annual_temp_c,
                "avg_summer_temp_c": m.avg_summer_temp_c,
                "avg_humidity_pct": m.avg_humidity_pct,
                "annual_cooling_degree_days": m.annual_cooling_degree_days,
                "tornado_risk_index": m.tornado_risk_index,
                "hurricane_risk_index": m.hurricane_risk_index,
                "hail_risk_index": m.hail_risk_index,
            }
            features.append(self._make_feature(bundle, score, label, metrics_subset))

        return self._make_feature_collection(features, self._score_range(scores))
