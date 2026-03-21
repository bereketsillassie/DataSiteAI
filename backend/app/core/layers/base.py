"""
app/core/layers/base.py
────────────────────────
Abstract base class for all GeoJSON layer builders.

Each layer builder converts ScoreBundle objects into a GeoJSON FeatureCollection
that the frontend can display as a map overlay.

Color scale:
  0.0 (worst)  → #E74C3C (red)
  0.5 (medium) → #F39C12 (orange-yellow)
  1.0 (best)   → #2ECC71 (green)
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any
from app.models.responses import ScoreBundle


class BaseLayerBuilder(ABC):
    """
    Abstract base for all 8 layer builders (7 category layers + 1 optimal).

    Subclasses must set:
      layer_id:    str  — matches category key ("power", "water", etc.) or "optimal"
      label:       str  — human-readable name ("Power & Energy", "Optimal Score")
      description: str  — 1-2 sentence description for the frontend legend

    Subclasses must implement:
      build(score_bundles) → GeoJSON FeatureCollection dict
    """

    layer_id: str
    label: str
    description: str

    @abstractmethod
    def build(self, score_bundles: list[ScoreBundle]) -> dict:
        """
        Convert a list of ScoreBundles into a GeoJSON FeatureCollection.

        Must return a dict with this exact structure:
        {
          "type": "FeatureCollection",
          "metadata": {
            "layer_id": str,
            "label": str,
            "score_range": [min_score, max_score],
            "generated_at": ISO8601 string
          },
          "features": [
            {
              "type": "Feature",
              "geometry": { GeoJSON Polygon — the grid cell boundary },
              "properties": {
                "layer_id": str,
                "score": float (0.0–1.0),
                "label": str (human-readable e.g. "Power: High — Substation 1.8km"),
                "color_hex": str (from _score_to_color),
                "metrics": { relevant subset of ScoreMetrics }
              }
            }
          ]
        }
        """
        ...

    def _score_to_color(self, score: float) -> str:
        """
        Map a 0.0–1.0 score to a red-yellow-green hex color.

        Color stops:
          0.0 → #E74C3C  (red — worst)
          0.5 → #F39C12  (orange — medium)
          1.0 → #2ECC71  (green — best)

        Interpolates smoothly between stops.
        """
        score = max(0.0, min(1.0, score))

        if score <= 0.5:
            # Interpolate red (#E74C3C) to orange (#F39C12)
            t = score * 2  # 0.0 at score=0, 1.0 at score=0.5
            r = int(0xE7 + t * (0xF3 - 0xE7))
            g = int(0x4C + t * (0x9C - 0x4C))
            b = int(0x3C + t * (0x12 - 0x3C))
        else:
            # Interpolate orange (#F39C12) to green (#2ECC71)
            t = (score - 0.5) * 2  # 0.0 at score=0.5, 1.0 at score=1.0
            r = int(0xF3 + t * (0x2E - 0xF3))
            g = int(0x9C + t * (0xCC - 0x9C))
            b = int(0x12 + t * (0x71 - 0x12))

        return f"#{r:02X}{g:02X}{b:02X}"

    def _make_feature(
        self,
        bundle: ScoreBundle,
        score: float,
        label: str,
        metrics_subset: dict[str, Any],
    ) -> dict:
        """
        Build a single GeoJSON Feature from a ScoreBundle.
        Used by all layer builders to ensure consistent structure.
        """
        return {
            "type": "Feature",
            "geometry": bundle.location.cell_polygon,
            "properties": {
                "layer_id": self.layer_id,
                "score": round(score, 4),
                "label": label,
                "color_hex": self._score_to_color(score),
                "metrics": metrics_subset,
                "lat": bundle.location.lat,
                "lng": bundle.location.lng,
            },
        }

    def _make_feature_collection(self, features: list[dict], score_range: list[float]) -> dict:
        """Wrap features in a GeoJSON FeatureCollection with required metadata."""
        return {
            "type": "FeatureCollection",
            "metadata": {
                "layer_id": self.layer_id,
                "label": self.label,
                "score_range": score_range,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "features": features,
        }

    def _score_range(self, scores: list[float]) -> list[float]:
        """Return [min, max] for the given score list, or [0.0, 1.0] if empty."""
        if not scores:
            return [0.0, 1.0]
        return [round(min(scores), 4), round(max(scores), 4)]
