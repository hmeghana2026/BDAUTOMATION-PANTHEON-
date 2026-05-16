"""Competitor gap analysis using Google Maps to find nearby businesses."""
import logging
from typing import Optional
from database.models import Lead
from integrations.gmaps_client import GoogleMapsClient

logger = logging.getLogger(__name__)

CAPABILITY_MAP = {
    "online_ordering": ["order online", "order now", "doordash", "grubhub", "ubereats", "toast", "online ordering"],
    "reservation_system": ["opentable", "resy", "reservation", "book a table"],
    "online_booking": ["book", "appointment", "schedule", "calendar", "book now", "book online"],
    "email_marketing": ["mailchimp", "klaviyo", "email list", "newsletter", "subscribe"],
    "loyalty_program": ["loyalty", "rewards", "points program", "loyalty card"],
    "delivery": ["delivery", "doordash", "grubhub", "postmates", "uber eats"],
}

SEVERITY_MAP = {
    0.0: "critical",   # competitor adoption = 0%
    0.4: "high",       # competitor adoption < 40%
    0.6: "medium",     # competitor adoption < 60%
    1.0: "low",        # competitor adoption >= 60%
}


def _infer_capabilities(name: str, website: Optional[str]) -> dict:
    """Infer business capabilities from website URL and business name heuristics."""
    caps = {cap: False for cap in CAPABILITY_MAP}

    # Basic heuristics on the website domain / business name
    text = ((website or "") + " " + (name or "")).lower()

    for cap, keywords in CAPABILITY_MAP.items():
        if any(kw in text for kw in keywords):
            caps[cap] = True

    return caps


def _severity_label(competitor_adoption_rate: float) -> str:
    """Convert a 0-1 competitor adoption rate to a severity string."""
    if competitor_adoption_rate == 0:
        return "critical"
    if competitor_adoption_rate < 0.4:
        return "high"
    if competitor_adoption_rate < 0.6:
        return "medium"
    return "low"


def _generate_talking_points(gaps: list, lead_name: str) -> list:
    """Build outreach talking points from detected capability gaps."""
    points = []
    for gap in gaps:
        cap = gap["capability"].replace("_", " ").title()
        pct = int(gap.get("competitors_with_pct", 0) * 100)
        severity = gap.get("severity", "medium")

        if severity == "critical":
            points.append(
                f"{cap}: none of your competitors offer this yet — early adoption could be a major differentiator for {lead_name}."
            )
        elif severity == "high":
            points.append(
                f"{cap}: only {pct}% of nearby competitors have this — {lead_name} is behind the curve and could close the gap quickly."
            )
        elif severity == "medium":
            points.append(
                f"{cap}: {pct}% of nearby competitors already offer this — now is the time for {lead_name} to catch up."
            )
        else:
            points.append(
                f"{cap}: most local competitors ({pct}%) already have this — {lead_name} risks losing customers without it."
            )

    return points


class CompetitorAnalysisAgent:
    """Finds nearby competitors and identifies capability gaps relative to the target lead."""

    def __init__(self, db=None):
        self._gmaps = None
        self._db = db

    @property
    def gmaps(self) -> GoogleMapsClient:
        if self._gmaps is None:
            self._gmaps = GoogleMapsClient()
        return self._gmaps

    def _get_db(self):
        if self._db is None:
            from database.supabase_client import SupabaseDB
            self._db = SupabaseDB()
        return self._db

    def analyze(self, lead: Lead, radius_miles: float = 2.0, top_n: int = 5) -> dict:
        """
        Find nearby competitors and identify capability gaps.

        Args:
            lead: The target Lead to analyse.
            radius_miles: Search radius for nearby competitors.
            top_n: Maximum number of competitors to return.

        Returns:
            {
              "competitors": [...],
              "capability_gaps": [...],
              "outreach_talking_points": [...],
            }
        """
        # 1. Determine lead's own capabilities (from its website)
        lead_caps = _infer_capabilities(lead.company_name, lead.website)

        # 2. Find nearby businesses of the same vertical
        search_query = f"{lead.vertical} near {lead.geography or lead.company_name}"
        raw_competitors = []
        try:
            raw_competitors = self.gmaps.search_businesses(
                business_type=lead.vertical,
                location=lead.geography or lead.company_name,
                radius_miles=radius_miles,
                max_results=top_n + 1,  # +1 to account for the lead itself
            )
        except Exception as e:
            logger.warning(f"CompetitorAnalysis: Google Maps search failed for {lead.company_name}: {e}")

        # 3. Build competitor profiles, excluding the lead itself
        competitors = []
        for place in raw_competitors:
            biz_name = place.get("business_name", "")
            if biz_name.lower().strip() == lead.company_name.lower().strip():
                continue  # skip the lead itself

            caps = _infer_capabilities(biz_name, place.get("website"))
            competitors.append({
                "name": biz_name,
                "address": place.get("address"),
                "rating": place.get("rating"),
                "website": place.get("website"),
                "phone": place.get("phone"),
                "capabilities": caps,
            })
            if len(competitors) >= top_n:
                break

        # 4. Compare lead capabilities vs competitors to find gaps
        capability_gaps = []
        n = len(competitors)

        for cap in CAPABILITY_MAP:
            lead_has = lead_caps.get(cap, False)
            if lead_has:
                # Lead already has this capability — not a gap
                continue

            if n == 0:
                competitors_with = 0
                adoption_rate = 0.0
            else:
                competitors_with = sum(1 for c in competitors if c["capabilities"].get(cap, False))
                adoption_rate = competitors_with / n

            # Only report as a gap if at least one competitor has it
            if competitors_with > 0 or n == 0:
                capability_gaps.append({
                    "capability": cap,
                    "lead_has": lead_has,
                    "competitors_with": competitors_with,
                    "competitors_with_pct": round(adoption_rate, 2),
                    "total_competitors": n,
                    "severity": _severity_label(adoption_rate),
                })

        # Sort gaps by severity (critical > high > medium > low)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        capability_gaps.sort(key=lambda g: severity_order.get(g["severity"], 99))

        # 5. Generate outreach talking points
        talking_points = _generate_talking_points(capability_gaps, lead.company_name)

        return {
            "competitors": competitors,
            "capability_gaps": capability_gaps,
            "outreach_talking_points": talking_points,
        }
