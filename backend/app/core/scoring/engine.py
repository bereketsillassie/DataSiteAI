"""
app/core/scoring/engine.py
───────────────────────────
The ScoringEngine orchestrates all 7 category scorers and applies weights.

THIS IS THE ONLY PLACE IN THE CODEBASE WHERE CATEGORY WEIGHTS ARE APPLIED.

BATCH CALL STRATEGY:
  Before running all 7 scorers in parallel, the engine warms 3 shared caches:
    1. osm.get_region_data(bbox)           — 1 Overpass call for ALL OSM features
    2. noaa.get_climate_normals_for_region — 1 NOAA call for climate data
    3. nasa.get_climate_data_for_region    — 1 NASA POWER call for humidity

  When scorers then call get_power_lines(), get_substations(), get_highways(),
  get_fiber_routes(), get_amenities(), get_waterways() etc., they ALL hit
  Redis cache immediately — zero additional Overpass requests.

  Each cell still gets unique per-cell scores because the scoring math uses
  each cell's specific lat/lng to compute distances to the cached features.
  Batch fetching does NOT reduce per-cell score resolution.

Flow:
  1. score_region(bbox) called by analyze endpoint
  2. Shared caches warmed (3 batch calls)
  3. All 7 scorers run in parallel via asyncio.gather
  4. Results merged by grid cell lat/lng
  5. CATEGORY_WEIGHTS applied → composite scores
  6. Sorted highest composite first → returned as ScoreBundles
"""

import asyncio
import logging

from app.core.scoring.weights import CATEGORY_WEIGHTS
from app.models.domain import BoundingBox, CellScore
from app.models.responses import (
    ScoreBundle, CompositeScore, LocationPoint, ScoreMetrics,
    PowerMetrics, WaterMetrics, GeologicalMetrics, ClimateMetrics,
    ConnectivityMetrics, EconomicMetrics, EnvironmentalMetrics,
)

logger = logging.getLogger(__name__)


class ScoringEngine:
    """
    Orchestrates all 7 scorers and produces ScoreBundles.
    Inject all 7 scorers via __init__ for testability.
    """

    def __init__(
        self,
        power_scorer,
        water_scorer,
        geological_scorer,
        climate_scorer,
        connectivity_scorer,
        economic_scorer,
        environmental_scorer,
        db_session=None,
        settings=None,
    ):
        self.scorers = {
            "power":         power_scorer,
            "water":         water_scorer,
            "geological":    geological_scorer,
            "climate":       climate_scorer,
            "connectivity":  connectivity_scorer,
            "economic":      economic_scorer,
            "environmental": environmental_scorer,
        }
        self.db_session = db_session
        self.settings = settings

    async def score_region(
        self,
        bbox: BoundingBox,
        grid_resolution_km: float = 5.0,
    ) -> list[ScoreBundle]:
        """
        Run all 7 scorers in parallel and return per-cell ScoreBundles.

        IMPORTANT: Each cell receives a unique score. Batch pre-fetching means
        we get all the underlying data in a few API calls, then the per-cell
        math loop uses each cell's specific coordinates to compute distances
        to those features. The map overlay shows real per-cell variation.

        Args:
            bbox: The geographic region to score
            grid_resolution_km: Grid cell size in km (default 5km)

        Returns:
            List of ScoreBundle objects, sorted composite score descending.
        """
        logger.info(
            f"Scoring bbox ({bbox.min_lat},{bbox.min_lng}) → "
            f"({bbox.max_lat},{bbox.max_lng}) at {grid_resolution_km}km resolution"
        )

        # ── Step 1: Warm shared caches BEFORE scorers run ─────────────────────
        # This converts ~99 per-cell API calls into ~3-5 region-level calls.
        # Scorers hitting the same data sources will find cache hits immediately.
        await self._warm_caches(bbox)

        # ── Step 2: Run all 7 scorers in parallel ─────────────────────────────
        tasks = {
            category: asyncio.create_task(scorer.score(bbox))
            for category, scorer in self.scorers.items()
        }

        results: dict[str, list[CellScore]] = {}
        for category, task in tasks.items():
            try:
                results[category] = await task
                logger.info(f"Scorer '{category}' returned {len(results[category])} cells")
            except Exception as e:
                logger.error(f"Scorer '{category}' failed entirely: {e}. Using empty results.")
                results[category] = []

        # ── Step 3: Merge by (lat, lng) and build ScoreBundles ────────────────
        merged  = self._merge_cell_scores(results)
        bundles = [b for b in (self._build_score_bundle(d) for d in merged.values()) if b]
        bundles.sort(key=lambda b: b.composite_score.composite, reverse=True)

        logger.info(
            f"Scoring complete: {len(bundles)} cells scored. "
            f"Top composite: {bundles[0].composite_score.composite if bundles else 'N/A'}"
        )
        return bundles

    async def _warm_caches(self, bbox: BoundingBox) -> None:
        """
        Pre-fetch all shared region-level data before scorers run in parallel.

        WHY: Scorers run concurrently. Without pre-warming, multiple scorers
        would each try to fetch OSM data simultaneously — all missing the cache,
        all hitting Overpass at once, all getting 429s.

        With pre-warming: one call populates the cache, all concurrent scorers
        find a hit. Zero race conditions, zero 429s.

        Data fetched here is reused by:
          OSM region data  → power, water, connectivity, environmental scorers
          NOAA normals     → climate scorer
          NASA POWER       → climate scorer
        """
        from app.integrations.osm import OSMClient
        from app.integrations.noaa import NOAAClient
        from app.integrations.nasa_power import NASAPowerClient

        osm  = OSMClient(db_session=self.db_session, settings=self.settings)
        noaa = NOAAClient(db_session=self.db_session, settings=self.settings)
        nasa = NASAPowerClient(db_session=self.db_session, settings=self.settings)

        # Run the 3 batch pre-fetches concurrently
        results = await asyncio.gather(
            osm.get_region_data(bbox),
            noaa.get_climate_normals_for_region(bbox),
            nasa.get_climate_data_for_region(bbox),
            return_exceptions=True,
        )

        names = ["OSM region data", "NOAA climate normals", "NASA POWER climate"]
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                logger.warning(f"Cache warm failed for {name}: {result} — scorers will retry individually")
            else:
                logger.info(f"Cache warmed: {name}")

    def _merge_cell_scores(
        self,
        results: dict[str, list[CellScore]],
    ) -> dict[tuple, dict]:
        """Merge CellScore lists from all 7 scorers into a dict keyed by (lat, lng)."""
        merged: dict[tuple, dict] = {}

        for category, cell_scores in results.items():
            for cell in cell_scores:
                key = (round(cell.lat, 5), round(cell.lng, 5))
                if key not in merged:
                    merged[key] = {
                        "lat":          cell.lat,
                        "lng":          cell.lng,
                        "cell_polygon": None,
                        "raw_scores":   {},
                        "sub_scores":   {},
                        "metrics":      {},
                        "errors":       {},
                    }

                if cell.error:
                    merged[key]["errors"][category] = cell.error
                else:
                    merged[key]["raw_scores"].update(cell.raw_scores)
                    merged[key]["sub_scores"].update(cell.sub_scores)
                    merged[key]["metrics"].update(cell.metrics)

                if (hasattr(cell, "cell_polygon") and cell.cell_polygon
                        and merged[key]["cell_polygon"] is None):
                    merged[key]["cell_polygon"] = cell.cell_polygon

        return merged

    def _build_score_bundle(self, cell_data: dict) -> ScoreBundle | None:
        """Build a ScoreBundle from merged cell data. Returns None if no scores."""
        raw_scores = cell_data.get("raw_scores", {})
        if not raw_scores:
            return None

        composite    = self._apply_weights(raw_scores, CATEGORY_WEIGHTS)
        metrics      = self._build_metrics(cell_data.get("metrics", {}))
        cell_polygon = cell_data.get("cell_polygon") or self._default_polygon(
            cell_data["lat"], cell_data["lng"]
        )

        return ScoreBundle(
            location=LocationPoint(
                lat=cell_data["lat"],
                lng=cell_data["lng"],
                cell_polygon=cell_polygon,
            ),
            composite_score=composite,
            scores=raw_scores,
            metrics=metrics,
        )

    def _default_polygon(self, lat: float, lng: float) -> dict:
        """Generate a default ~5km grid cell polygon when none was provided."""
        half = 0.023  # ~2.5km in degrees at mid-latitudes
        return {
            "type": "Polygon",
            "coordinates": [[
                [lng - half, lat - half],
                [lng + half, lat - half],
                [lng + half, lat + half],
                [lng - half, lat + half],
                [lng - half, lat - half],
            ]],
        }

    def _apply_weights(
        self,
        raw_scores: dict[str, float],
        weights: dict[str, float],
    ) -> CompositeScore:
        """
        Apply CATEGORY_WEIGHTS to raw category scores.

        Only categories present in raw_scores with weight > 0 are included.
        Weights are normalized so they don't need to sum to 1.0 in weights.py.
        """
        active = {
            cat: w for cat, w in weights.items()
            if cat in raw_scores and w > 0
        }
        if not active:
            return CompositeScore(composite=0.0, weighted_contributions={}, weights_used={})

        total      = sum(active.values())
        normalized = {cat: w / total for cat, w in active.items()}
        contributions = {
            cat: round(raw_scores.get(cat, 0.0) * nw, 6)
            for cat, nw in normalized.items()
        }
        composite = round(sum(contributions.values()), 4)

        return CompositeScore(
            composite=max(0.0, min(1.0, composite)),
            weighted_contributions=contributions,
            weights_used={cat: round(w, 6) for cat, w in normalized.items()},
        )

    def _build_metrics(self, raw: dict) -> ScoreMetrics:
        """Construct ScoreMetrics from the raw metrics dict with safe defaults."""
        g = raw.get

        return ScoreMetrics(
            power=PowerMetrics(
                nearest_transmission_line_km=g("nearest_transmission_line_km", 5.0),
                nearest_substation_km=g("nearest_substation_km", 5.0),
                electricity_rate_cents_per_kwh=g("electricity_rate_cents_per_kwh", 10.0),
                renewable_energy_pct=g("renewable_energy_pct", 15.0),
                grid_reliability_index=g("grid_reliability_index", 70.0),
                utility_territory=g("utility_territory", "Unknown"),
            ),
            water=WaterMetrics(
                fema_flood_zone=g("fema_flood_zone", "X"),
                flood_risk_pct=g("flood_risk_pct", 0.0),
                nearest_water_body_km=g("nearest_water_body_km", 3.0),
                groundwater_availability=g("groundwater_availability", "moderate"),
                drought_risk_level=g("drought_risk_level", "None"),
            ),
            geological=GeologicalMetrics(
                seismic_hazard_pga=g("seismic_hazard_pga", 0.08),
                slope_degrees=g("slope_degrees", 2.0),
                elevation_m=g("elevation_m", 100.0),
                soil_bearing_capacity=g("soil_bearing_capacity", "moderate"),
                nearest_wetland_km=g("nearest_wetland_km", 3.0),
                nearest_superfund_km=g("nearest_superfund_km", 10.0),
            ),
            climate=ClimateMetrics(
                avg_annual_temp_c=g("avg_annual_temp_c", 15.0),
                avg_summer_temp_c=g("avg_summer_temp_c", 26.0),
                avg_humidity_pct=g("avg_humidity_pct", 70.0),
                annual_cooling_degree_days=g("annual_cooling_degree_days", 1500.0),
                tornado_risk_index=g("tornado_risk_index", 16.0),
                hurricane_risk_index=g("hurricane_risk_index", 30.0),
                hail_risk_index=g("hail_risk_index", 12.0),
            ),
            connectivity=ConnectivityMetrics(
                fiber_routes_within_5km=g("fiber_routes_within_5km", 2),
                nearest_ix_point_km=g("nearest_ix_point_km", 80.0),
                nearest_highway_km=g("nearest_highway_km", 3.0),
                nearest_airport_km=g("nearest_airport_km", 25.0),
            ),
            economic=EconomicMetrics(
                state_corporate_tax_rate_pct=g("state_corporate_tax_rate_pct", 5.0),
                data_center_tax_exemption=g("data_center_tax_exemption", False),
                permitting_difficulty=g("permitting_difficulty", "moderate"),
                median_electrician_wage_usd=g("median_electrician_wage_usd", 56000.0),
                median_land_cost_per_acre_usd=g("median_land_cost_per_acre_usd", 10000.0),
                tech_workers_per_1000_residents=g("tech_workers_per_1000_residents", 7.0),
            ),
            environmental=EnvironmentalMetrics(
                population_within_5km=g("population_within_5km", 5000),
                nearest_school_km=g("nearest_school_km", 2.0),
                nearest_hospital_km=g("nearest_hospital_km", 5.0),
                air_quality_index=g("air_quality_index", 45.0),
                protected_land_within_1km=g("protected_land_within_1km", False),
                land_cover_type=g("land_cover_type", "Cultivated Crops"),
            ),
        )


def create_scoring_engine(db_session=None, settings=None) -> ScoringEngine:
    """
    Factory that creates a fully-wired ScoringEngine with all 7 scorers.
    Called by the analyze endpoint. Passes db_session to all integration clients
    so they can use the PostgreSQL cache table.
    """
    from app.core.scoring.power import PowerScorer
    from app.core.scoring.water import WaterScorer
    from app.core.scoring.geological import GeologicalScorer
    from app.core.scoring.climate import ClimateScorer
    from app.core.scoring.connectivity import ConnectivityScorer
    from app.core.scoring.economic import EconomicScorer
    from app.core.scoring.environmental import EnvironmentalScorer

    return ScoringEngine(
        power_scorer=PowerScorer(db_session=db_session, settings=settings),
        water_scorer=WaterScorer(db_session=db_session, settings=settings),
        geological_scorer=GeologicalScorer(db_session=db_session, settings=settings),
        climate_scorer=ClimateScorer(db_session=db_session, settings=settings),
        connectivity_scorer=ConnectivityScorer(db_session=db_session, settings=settings),
        economic_scorer=EconomicScorer(db_session=db_session, settings=settings),
        environmental_scorer=EnvironmentalScorer(db_session=db_session, settings=settings),
        db_session=db_session,
        settings=settings,
    )