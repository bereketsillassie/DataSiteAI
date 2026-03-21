"""
app/core/scoring/economic.py
─────────────────────────────
Economic scorer.

Formulas (from CLAUDE.md):
  tax_environment:  1.0 - clamp(state_corp_tax_rate / 12.0)
                    + 0.2 bonus if state has DC-specific tax exemption
  land_cost:        1.0 - clamp(price_per_acre_usd / 50000)
  labor_market:     clamp(tech_workers_per_1000_residents / 20.0)
  permitting:       easy→1.0, moderate→0.6, difficult→0.2

Data sources: EIA (electricity rates), US Census Bureau (labor market),
              curated static tables for state tax rates and permitting difficulty.

NOTE: This scorer reads ECONOMIC_SUB_WEIGHTS from weights.py to roll up its own
sub-metrics. It NEVER reads CATEGORY_WEIGHTS — that is the engine's job only.
"""

import logging

from app.core.scoring.base import BaseScorer
from app.core.scoring.weights import ECONOMIC_SUB_WEIGHTS
from app.core.grid import generate_grid
from app.models.domain import BoundingBox, CellScore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# States with data center-specific tax incentive programs
# (sales tax exemptions on equipment, property tax abatements, special rates)
# Source: Data Center Incentives Database 2024 / State economic development agencies
# ---------------------------------------------------------------------------
DC_TAX_EXEMPTION_STATES: set[str] = {
    "NC",   # Sales tax exemption on electricity used in data centers
    "VA",   # Data center sales and use tax exemption (most generous in US)
    "TX",   # No state income tax; sales tax exemption on qualifying equipment
    "GA",   # Sales tax exemption on servers, networking equipment
    "TN",   # No state income tax on wages; equipment exemptions
    "CO",   # Enterprise zone incentives and sales tax exemptions
    "AZ",   # Transaction privilege tax exemption for data centers
    "NV",   # No corporate income tax; abatements on personal property
    "WY",   # No corporate or personal income tax
    "UT",   # Sales tax exemptions; opportunity zones
    "OH",   # Data center tax incentive program
    "IN",   # Sales tax exemption on equipment
    "IA",   # Property tax exemption and sales tax refunds
    "KS",   # Sales tax exemption with qualifying investment
    "NE",   # ImagiNE Act — property tax exemption, sales tax refunds
    "ID",   # Sales tax exemption on server equipment
    "OR",   # No sales tax; low corporate tax; property tax exemptions
    "WA",   # Sales and use tax exemptions in designated areas
    "SC",   # Sales tax exemption on servers; job tax credits
    "MS",   # Sales tax exemption; property tax abatements
}

# ---------------------------------------------------------------------------
# State corporate income tax rates (%, 2024 figures)
# Source: Tax Foundation 2024 State Business Tax Climate Index
# ---------------------------------------------------------------------------
STATE_CORP_TAX_RATES: dict[str, float] = {
    "NC": 2.5,   "VA": 6.0,   "TX": 0.0,   "GA": 5.75,  "TN": 6.5,
    "CO": 4.4,   "AZ": 4.9,   "WA": 0.0,   "OR": 7.6,   "ID": 5.8,
    "NV": 0.0,   "UT": 4.65,  "WY": 0.0,   "MT": 6.75,  "ND": 4.31,
    "SD": 0.0,   "NE": 5.84,  "KS": 4.0,   "OK": 4.0,   "AR": 4.3,
    "LA": 7.5,   "MS": 4.0,   "AL": 6.5,   "FL": 5.5,   "OH": 0.0,
    "IN": 4.9,   "IL": 9.5,   "MI": 6.0,   "WI": 7.9,   "MN": 9.8,
    "IA": 8.4,   "MO": 4.0,   "KY": 5.0,   "WV": 6.5,   "PA": 8.99,
    "NY": 7.25,  "NJ": 9.0,   "CT": 7.5,   "MA": 8.0,   "RI": 7.0,
    "NH": 7.5,   "VT": 6.0,   "ME": 8.93,  "MD": 8.25,  "DE": 8.7,
    "SC": 5.0,   "DC": 8.25,  "HI": 6.4,   "AK": 9.4,   "NM": 5.9,
    "CA": 8.84,
}

# ---------------------------------------------------------------------------
# Data center permitting difficulty by state
# Factors: local zoning laws, environmental review requirements, grid
# interconnect approval process, community opposition patterns
# Source: Data Center Dynamics permitting index 2024 (curated assessment)
# ---------------------------------------------------------------------------
STATE_PERMITTING: dict[str, str] = {
    "NC": "easy",      "VA": "easy",      "TX": "easy",      "GA": "moderate",
    "TN": "easy",      "CO": "moderate",  "AZ": "easy",      "WA": "moderate",
    "OR": "difficult", "ID": "easy",      "NV": "easy",      "UT": "easy",
    "WY": "easy",      "MT": "easy",      "ND": "easy",      "SD": "easy",
    "NE": "easy",      "KS": "easy",      "OK": "easy",      "AR": "easy",
    "LA": "moderate",  "MS": "easy",      "AL": "moderate",  "FL": "moderate",
    "OH": "easy",      "IN": "easy",      "IL": "moderate",  "MI": "moderate",
    "WI": "moderate",  "MN": "moderate",  "IA": "easy",      "MO": "easy",
    "KY": "easy",      "WV": "moderate",  "PA": "difficult", "NY": "difficult",
    "NJ": "difficult", "CT": "difficult", "MA": "difficult", "RI": "difficult",
    "NH": "moderate",  "VT": "moderate",  "ME": "moderate",  "MD": "moderate",
    "DE": "moderate",  "SC": "easy",      "DC": "difficult", "HI": "difficult",
    "AK": "moderate",  "NM": "easy",      "CA": "difficult",
}

# Permitting difficulty → raw score
PERMITTING_SCORES: dict[str, float] = {
    "easy":     1.0,
    "moderate": 0.6,
    "difficult": 0.2,
}

# ---------------------------------------------------------------------------
# Rough median land cost per acre by state (USD, 2024 estimates)
# Source: USDA Land Values Survey + Zillow Research + CBRE market reports
# ---------------------------------------------------------------------------
LAND_COST_PER_ACRE: dict[str, int] = {
    "NC": 8500,    "VA": 12000,   "TX": 5200,    "GA": 7800,    "TN": 6500,
    "CO": 9500,    "AZ": 6200,    "WA": 14000,   "OR": 11000,   "ID": 5500,
    "NV": 4200,    "UT": 7200,    "WY": 1800,    "MT": 1200,    "ND": 2200,
    "SD": 1800,    "NE": 3800,    "KS": 3200,    "OK": 3500,    "AR": 3200,
    "LA": 5000,    "MS": 3500,    "AL": 4800,    "FL": 18000,   "OH": 8500,
    "IN": 7200,    "IL": 9800,    "MI": 8200,    "WI": 7500,    "MN": 6800,
    "IA": 6200,    "MO": 5500,    "KY": 5800,    "WV": 3800,    "PA": 11000,
    "NY": 25000,   "NJ": 42000,   "CT": 35000,   "MA": 38000,   "RI": 32000,
    "NH": 18000,   "VT": 15000,   "ME": 8500,    "MD": 28000,   "DE": 22000,
    "SC": 6800,    "DC": 500000,  "HI": 85000,   "AK": 2200,    "NM": 3800,
    "CA": 38000,
}


class EconomicScorer(BaseScorer):
    """Scores locations on tax environment, land cost, labor market, and permitting."""

    category_id = "economic"

    def __init__(self, redis_client=None, settings=None):
        from app.integrations.census import CensusClient
        from app.config import settings as default_settings

        self.settings = settings or default_settings
        self.census = CensusClient(redis_client=redis_client, settings=self.settings)

    async def score(self, bbox: BoundingBox) -> list[CellScore]:
        """Score all grid cells in the bbox for economic factors."""
        grid_res = getattr(self.settings, 'GRID_RESOLUTION_DEFAULT_KM', 5.0)
        grid = generate_grid(bbox, cell_size_km=grid_res)

        # Determine state from bbox center (simplified)
        center_lat, center_lng = bbox.center()
        state = self._lat_lng_to_state(center_lat, center_lng)

        # Fetch labor market data from Census Bureau
        try:
            labor_data = await self.census.get_labor_data(state)
        except Exception as e:
            logger.error(f"EconomicScorer: Census labor fetch failed: {e}")
            # Conservative defaults
            labor_data = {
                "tech_workers_per_1000": 8.2,
                "median_electrician_wage_usd": 56000.0,
            }

        # Look up state-level economic data from static tables
        corp_tax = STATE_CORP_TAX_RATES.get(state, 6.0)
        has_exemption = state in DC_TAX_EXEMPTION_STATES
        permitting = STATE_PERMITTING.get(state, "moderate")
        land_cost = LAND_COST_PER_ACRE.get(state, 10000)

        results = []
        for cell in grid:
            try:
                cs = self._score_cell(cell, corp_tax, has_exemption, permitting, land_cost, labor_data)
                results.append(cs)
            except Exception as e:
                logger.warning(f"EconomicScorer: cell ({cell.lat},{cell.lng}) failed: {e}")
                results.append(CellScore(lat=cell.lat, lng=cell.lng, error=str(e)))

        return results

    def _score_cell(
        self, cell, corp_tax: float, has_exemption: bool,
        permitting: str, land_cost: int, labor_data: dict
    ) -> CellScore:
        """Score a single grid cell for economic factors."""

        # tax_environment: 1.0 - clamp(state_corp_tax_rate / 12.0)
        # 0% tax = best, 12%+ = worst; +0.2 bonus for DC-specific tax exemptions
        tax_score = 1.0 - self._clamp(corp_tax / 12.0)
        if has_exemption:
            tax_score = min(1.0, tax_score + 0.2)

        # land_cost: 1.0 - clamp(price_per_acre_usd / 50000)
        # $0/acre = best, $50,000+/acre = worst
        land_score = 1.0 - self._clamp(land_cost / 50000.0)

        # labor_market: clamp(tech_workers_per_1000_residents / 20.0)
        # 0 = no tech workforce, 20+ per 1000 = excellent tech labor pool
        tech_per_1000 = labor_data.get("tech_workers_per_1000", 7.0)
        labor_score = self._clamp(tech_per_1000 / 20.0)

        # permitting: easy→1.0, moderate→0.6, difficult→0.2
        permitting_score = PERMITTING_SCORES.get(permitting, 0.6)

        sub_scores = {
            "tax_environment": round(tax_score, 4),
            "land_cost":       round(land_score, 4),
            "labor_market":    round(labor_score, 4),
            "permitting":      round(permitting_score, 4),
        }

        # Roll up sub-metrics using ECONOMIC_SUB_WEIGHTS
        category_score = self._weighted_sum(sub_scores, ECONOMIC_SUB_WEIGHTS)

        metrics = {
            "state_corporate_tax_rate_pct":   corp_tax,
            "data_center_tax_exemption":       has_exemption,
            "permitting_difficulty":           permitting,
            "median_electrician_wage_usd":     float(labor_data.get("median_electrician_wage_usd", 56000.0)),
            "median_land_cost_per_acre_usd":   float(land_cost),
            "tech_workers_per_1000_residents": float(tech_per_1000),
        }

        return CellScore(
            lat=cell.lat,
            lng=cell.lng,
            raw_scores={self.category_id: round(category_score, 4)},
            sub_scores=sub_scores,
            metrics=metrics,
        )

    def _lat_lng_to_state(self, lat: float, lng: float) -> str:
        """
        Very rough state determination from lat/lng for state-level lookups.
        In production, this would use a proper point-in-polygon check against
        state boundary GeoJSON.
        """
        if 33.8 <= lat <= 36.6 and -84.3 <= lng <= -75.5:
            return "NC"
        if 37.0 <= lat <= 39.5 and -83.7 <= lng <= -75.2:
            return "VA"
        if 25.8 <= lat <= 36.5 and -106.7 <= lng <= -93.5:
            return "TX"
        if 30.4 <= lat <= 35.0 and -85.6 <= lng <= -80.8:
            return "GA"
        if 34.9 <= lat <= 36.7 and -90.3 <= lng <= -81.6:
            return "TN"
        if 36.9 <= lat <= 41.0 and -109.1 <= lng <= -102.0:
            return "CO"
        if 31.3 <= lat <= 37.0 and -114.8 <= lng <= -109.0:
            return "AZ"
        if 32.5 <= lat <= 42.0 and -124.5 <= lng <= -114.0:
            return "CA"
        if 45.5 <= lat <= 49.0 and -124.8 <= lng <= -116.9:
            return "WA"
        if 37.0 <= lat <= 42.0 and -124.6 <= lng <= -116.5:
            return "OR"
        return "NC"  # Default fallback
