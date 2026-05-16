"""Orchestrates the full research pipeline for a lead."""
import logging
from typing import Optional
from database.models import Lead

logger = logging.getLogger(__name__)


class ResearchOrchestrator:
    """
    Runs tiered enrichment → signal scoring → optional competitor analysis
    and pain point mining in a single call, persisting all results.
    """

    def __init__(self, db=None):
        self._db = db

    def _get_db(self):
        if self._db is None:
            from database.supabase_client import SupabaseDB
            self._db = SupabaseDB()
        return self._db

    def run(
        self,
        lead: Lead,
        tiers: Optional[list] = None,
        run_signals: bool = True,
        run_competitor: bool = False,
        run_pain_points: bool = False,
        competitor_radius_miles: float = 2.0,
        competitor_top_n: int = 5,
        pain_point_min_mentions: int = 2,
    ) -> dict:
        """
        Run the full research pipeline.

        Args:
            lead: The Lead to research.
            tiers: Which tiers to run (default [1, 2]).
            run_signals: Whether to score signals after tiered research.
            run_competitor: Whether to run competitor gap analysis.
            run_pain_points: Whether to mine Yelp reviews for pain points.
            competitor_radius_miles: Search radius for competitor lookup.
            competitor_top_n: Max competitors to analyse.
            pain_point_min_mentions: Min keyword hits to surface a pain point.

        Returns:
            dict with keys: tier_results, signal_score (optional),
            competitor_analysis (optional), pain_point_analysis (optional).
        """
        if tiers is None:
            tiers = [1, 2]

        output = {}

        # ── Step 1: Tiered enrichment ─────────────────────────────────────
        try:
            from agents.lead_research import TieredResearchService
            svc = TieredResearchService(db=self._db)
            tier_results = svc.run(lead, tiers=tiers)
            output["tier_results"] = tier_results
            logger.info(f"[Orchestrator] Tiers {tiers} complete for {lead.company_name}")

            # Persist tiered results
            if lead.id:
                try:
                    self._get_db().save_tiered_research(lead.id, tiers, tier_results)
                except Exception as e:
                    logger.warning(f"[Orchestrator] Could not persist tiered results: {e}")
        except Exception as e:
            logger.error(f"[Orchestrator] Tiered research failed for {lead.company_name}: {e}")
            tier_results = {}
            output["tier_results"] = {}

        # ── Step 2: Signal scoring ────────────────────────────────────────
        if run_signals:
            try:
                from agents.signal_scorer import SignalScorer
                signal_result = SignalScorer().score(lead, tier_results)
                output["signal_score"] = signal_result
                logger.info(
                    f"[Orchestrator] Signal score: {signal_result['priority_score']} "
                    f"({signal_result['qualification']}) for {lead.company_name}"
                )

                # Persist signal score
                if lead.id:
                    try:
                        self._get_db().save_signal_score(lead.id, signal_result)
                    except Exception as e:
                        logger.warning(f"[Orchestrator] Could not persist signal score: {e}")
            except Exception as e:
                logger.error(f"[Orchestrator] Signal scoring failed for {lead.company_name}: {e}")
                output["signal_score"] = None

        # ── Step 3: Competitor analysis ───────────────────────────────────
        if run_competitor:
            try:
                from agents.competitor_analysis import CompetitorAnalysisAgent
                comp_result = CompetitorAnalysisAgent().analyze(
                    lead,
                    radius_miles=competitor_radius_miles,
                    top_n=competitor_top_n,
                )
                output["competitor_analysis"] = comp_result
                logger.info(
                    f"[Orchestrator] Found {len(comp_result.get('competitors', []))} competitors "
                    f"and {len(comp_result.get('capability_gaps', []))} gaps for {lead.company_name}"
                )

                # Persist
                if lead.id:
                    try:
                        self._get_db().save_competitor_analysis(lead.id, comp_result)
                    except Exception as e:
                        logger.warning(f"[Orchestrator] Could not persist competitor analysis: {e}")
            except Exception as e:
                logger.error(f"[Orchestrator] Competitor analysis failed for {lead.company_name}: {e}")
                output["competitor_analysis"] = None

        # ── Step 4: Pain point mining ─────────────────────────────────────
        if run_pain_points:
            try:
                from agents.pain_point_miner import PainPointMiner
                # Use Yelp reviews fetched in Tier 1
                yelp_reviews = (
                    tier_results.get("tier_1", {})
                    .get("data", {})
                    .get("yelp_reviews", [])
                )

                if yelp_reviews:
                    pain_result = PainPointMiner().mine(
                        lead,
                        yelp_reviews,
                        min_mentions=pain_point_min_mentions,
                    )
                    output["pain_point_analysis"] = pain_result
                    logger.info(
                        f"[Orchestrator] Detected {len(pain_result.get('pain_points', []))} pain points "
                        f"from {pain_result.get('total_reviews_analyzed', 0)} reviews for {lead.company_name}"
                    )

                    # Persist
                    if lead.id:
                        try:
                            self._get_db().save_pain_point_analysis(lead.id, pain_result)
                        except Exception as e:
                            logger.warning(f"[Orchestrator] Could not persist pain point analysis: {e}")
                else:
                    logger.info(
                        f"[Orchestrator] No Yelp reviews available for pain point mining of {lead.company_name}. "
                        "Run Tier 1 first to fetch reviews."
                    )
                    output["pain_point_analysis"] = None
            except Exception as e:
                logger.error(f"[Orchestrator] Pain point mining failed for {lead.company_name}: {e}")
                output["pain_point_analysis"] = None

        return output
