"""
app/core/scoring/base.py
─────────────────────────
Abstract base class for all category scorers.

RULES FOR SCORER IMPLEMENTATIONS:
  1. Scorers return raw 0.0–1.0 scores ONLY — no weight application here
  2. Scorers NEVER import from weights.py — that's engine.py's job
     (Exception: scorers DO read their own {CATEGORY}_SUB_WEIGHTS to roll
      up sub-metrics into the category score. Only CATEGORY_WEIGHTS is off-limits.)
  3. All exceptions from integrations must be caught here, never propagated
  4. If a scorer fails for a cell, return a CellScore with error= set and
     raw_scores[category_id] omitted — the engine will skip that category
     for that cell when computing the composite score
"""

from abc import ABC, abstractmethod
from app.models.domain import BoundingBox, CellScore


class BaseScorer(ABC):
    """
    Abstract base class for all 7 scoring categories.

    Each scorer:
    - Receives integration clients in __init__
    - Implements score(bbox) to return one CellScore per grid cell
    - Uses _clamp() and _linear_scale() for consistent score computation
    - Catches all integration errors and returns a CellScore with error= set
    """

    category_id: str  # Must match a key in CATEGORY_WEIGHTS — set in each subclass

    @abstractmethod
    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """
        Score all candidate grid cells within the bounding box.

        Returns one CellScore per grid cell. The CellScore must have:
          - lat, lng matching the grid cell center
          - raw_scores[self.category_id] = float (0.0–1.0) — the category score
          - sub_scores = dict of sub-metric name → float for this scorer's metrics
          - metrics = dict of raw data values (pre-scoring numbers)
          - error = None on success, or a string message if something failed
        """
        ...

    def _clamp(self, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """
        Clamps a value to the [min_val, max_val] range.
        Used after linear scaling to ensure scores never exceed 0.0–1.0.

        Examples:
          _clamp(1.5)  → 1.0
          _clamp(-0.3) → 0.0
          _clamp(0.7)  → 0.7
        """
        return max(min_val, min(max_val, value))

    def _linear_scale(self, value: float, worst: float, best: float) -> float:
        """
        Linearly scales a raw value to 0.0–1.0.
        worst maps to 0.0 (lowest possible score).
        best  maps to 1.0 (highest possible score).

        Examples:
          _linear_scale(10.0, worst=20.0, best=5.0)  → 0.667  (10¢ closer to 5¢ best)
          _linear_scale(0.0,  worst=15.0, best=0.0)  → 1.0    (flat land = best)
          _linear_scale(15.0, worst=15.0, best=0.0)  → 0.0    (too steep = worst)
        """
        if best == worst:
            return 0.5  # Avoid division by zero when there's no range
        score = (value - worst) / (best - worst)
        return self._clamp(score)

    def _weighted_sum(self, scores: dict[str, float], weights: dict[str, float]) -> float:
        """
        Compute a weighted sum of sub-metric scores.
        weights should sum to 1.0 (sub-weights from weights.py).

        Returns the combined score (0.0–1.0).
        If weights don't sum to 1.0, they are normalized automatically.
        """
        total = sum(weights.values())
        if total == 0:
            return 0.0
        result = 0.0
        for key, weight in weights.items():
            result += scores.get(key, 0.0) * (weight / total)
        return self._clamp(result)
