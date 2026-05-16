"""Review mining agent for detecting pain points and generating outreach intelligence."""
import json
import logging
import re
from typing import Optional
from database.models import Lead
from integrations import LLMRouter

logger = logging.getLogger(__name__)

PAIN_POINT_CATEGORIES = {
    "wait_times": {
        "keywords": [
            "long wait", "waited", "slow service", "took forever",
            "hours", "wait time", "waiting too long", "slow",
        ],
        "maps_to_solution": "Queue management / appointment scheduling automation",
    },
    "booking_difficulty": {
        "keywords": [
            "hard to book", "couldn't reach", "no online booking", "phone tag",
            "couldn't schedule", "difficult to book", "no way to book",
        ],
        "maps_to_solution": "Online booking system",
    },
    "poor_communication": {
        "keywords": [
            "didn't call back", "no response", "ignored", "poor communication",
            "never heard back", "no follow up", "no follow-up", "unreachable",
        ],
        "maps_to_solution": "Automated follow-up / CRM",
    },
    "pricing_concerns": {
        "keywords": [
            "too expensive", "overpriced", "not worth", "hidden fees",
            "price", "expensive", "costly", "rip off",
        ],
        "maps_to_solution": "Transparent pricing page / value communication",
    },
    "outdated_experience": {
        "keywords": [
            "outdated", "old fashioned", "no app", "no website", "cash only",
            "old school", "not modern", "no digital", "no technology",
        ],
        "maps_to_solution": "Digital modernization",
    },
    "staff_issues": {
        "keywords": [
            "rude staff", "unprofessional", "not trained", "attitude",
            "rude", "disrespectful", "impolite", "untrained",
        ],
        "maps_to_solution": "Staff management tooling",
    },
}

OUTREACH_INTEL_SYSTEM = """You are an expert B2B sales copywriter helping craft personalised outreach.
Return ONLY valid JSON — no markdown, no explanation."""

OUTREACH_INTEL_PROMPT = """A {vertical} business called "{lead_name}" has the following customer pain points detected from reviews:

{pain_points_summary}

Generate outreach intelligence to help a salesperson open a conversation about solving these problems.

Return JSON with exactly these keys:
{{
  "best_opening_line": "A single compelling opening sentence that references a specific pain point",
  "urgency_angle": "1-2 sentences explaining why they should act now",
  "proof_points": ["Proof point 1", "Proof point 2", "Proof point 3"]
}}"""


def _severity(mention_count: int, total_reviews: int) -> str:
    """Classify severity based on percentage of reviews mentioning the pain point."""
    if total_reviews == 0:
        return "low"
    pct = mention_count / total_reviews
    if pct >= 0.20:
        return "high"
    if pct >= 0.10:
        return "medium"
    return "low"


class PainPointMiner:
    """Mines customer reviews for pain points and generates targeted outreach intelligence."""

    def __init__(self):
        self.llm = LLMRouter()

    def mine(self, lead: Lead, reviews: list, min_mentions: int = 2) -> dict:
        """
        Analyse reviews to detect pain points.

        Args:
            lead: Lead object with company_name and vertical fields.
            reviews: List of review dicts with "text", "rating", "date" keys.
            min_mentions: Minimum keyword hits required to report a pain point.

        Returns:
            {
              "pain_points": [...],
              "solution_mapping": [...],
              "outreach_intelligence": {
                  "best_opening_line": str,
                  "urgency_angle": str,
                  "proof_points": [...],
              },
              "total_reviews_analyzed": int,
            }
        """
        total = len(reviews)

        # 1. Keyword scan each review for each pain point category
        category_hits = {cat: {"count": 0, "quotes": []} for cat in PAIN_POINT_CATEGORIES}

        for review in reviews:
            text = (review.get("text") or "").lower()
            if not text:
                continue

            for cat, cfg in PAIN_POINT_CATEGORIES.items():
                matched = any(kw in text for kw in cfg["keywords"])
                if matched:
                    category_hits[cat]["count"] += 1
                    # Keep up to 3 example quotes
                    raw_text = review.get("text", "").strip()
                    if len(category_hits[cat]["quotes"]) < 3:
                        # Truncate long reviews to a representative snippet
                        snippet = raw_text[:200] + ("..." if len(raw_text) > 200 else "")
                        category_hits[cat]["quotes"].append(snippet)

        # 2. Build pain_points list (only those meeting min_mentions threshold)
        pain_points = []
        for cat, hits in category_hits.items():
            count = hits["count"]
            if count < min_mentions:
                continue

            sev = _severity(count, total)
            pain_points.append({
                "category": cat,
                "name": cat.replace("_", " ").title(),
                "mention_count": count,
                "severity": sev,
                "example_quotes": hits["quotes"],
            })

        # Sort by severity then count
        sev_order = {"high": 0, "medium": 1, "low": 2}
        pain_points.sort(key=lambda p: (sev_order.get(p["severity"], 99), -p["mention_count"]))

        # 3. Build solution_mapping
        solution_mapping = []
        for pp in pain_points:
            cat_cfg = PAIN_POINT_CATEGORIES.get(pp["category"], {})
            solution_mapping.append({
                "pain_point": pp["name"],
                "solution": cat_cfg.get("maps_to_solution", ""),
                "severity": pp["severity"],
                "mention_count": pp["mention_count"],
            })

        # 4. Use LLM to generate outreach intelligence from top pain points
        outreach_intelligence = {}
        if pain_points:
            try:
                outreach_intelligence = self._generate_outreach_intel(
                    lead.company_name,
                    lead.vertical,
                    pain_points[:3],
                )
            except Exception as e:
                logger.warning(f"PainPointMiner: LLM outreach intel failed for {lead.company_name}: {e}")
                outreach_intelligence = self._fallback_outreach_intel(lead.company_name, pain_points)
        else:
            outreach_intelligence = {
                "best_opening_line": f"I noticed {lead.company_name} has been serving customers in the {lead.vertical} space.",
                "urgency_angle": "Proactive outreach before issues surface can keep customer satisfaction high.",
                "proof_points": [],
            }

        return {
            "pain_points": pain_points,
            "solution_mapping": solution_mapping,
            "outreach_intelligence": outreach_intelligence,
            "total_reviews_analyzed": total,
        }

    def _generate_outreach_intel(
        self,
        lead_name: str,
        vertical: str,
        top_pain_points: list,
    ) -> dict:
        """Use LLM to generate specific outreach angles from detected pain points."""
        pain_points_summary = "\n".join(
            f"- {pp['name']} ({pp['mention_count']} mentions, severity: {pp['severity']}): "
            f"e.g. \"{pp['example_quotes'][0]}\"" if pp["example_quotes"] else f"- {pp['name']} ({pp['mention_count']} mentions)"
            for pp in top_pain_points
        )

        prompt = OUTREACH_INTEL_PROMPT.format(
            vertical=vertical,
            lead_name=lead_name,
            pain_points_summary=pain_points_summary,
        )

        try:
            raw = self.llm.complete(
                prompt,
                system=OUTREACH_INTEL_SYSTEM,
                max_tokens=400,
                temperature=0.4,
            )
            raw = re.sub(r"```json|```", "", raw).strip()
            data = json.loads(raw)
            return {
                "best_opening_line": data.get("best_opening_line", ""),
                "urgency_angle": data.get("urgency_angle", ""),
                "proof_points": data.get("proof_points", []),
            }
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"LLM outreach intel parse failed for {lead_name}: {e}")
            return self._fallback_outreach_intel(lead_name, top_pain_points)

    def _fallback_outreach_intel(self, lead_name: str, pain_points: list) -> dict:
        """Generate a basic outreach intel dict without LLM when it fails."""
        if not pain_points:
            return {
                "best_opening_line": f"I came across {lead_name} and wanted to connect.",
                "urgency_angle": "Our platform helps businesses like yours improve the customer experience.",
                "proof_points": [],
            }

        top = pain_points[0]
        top_name = top["name"].lower()

        return {
            "best_opening_line": (
                f"I noticed several customers mentioning {top_name} issues for {lead_name} "
                "— something our platform addresses directly."
            ),
            "urgency_angle": (
                f"With {top['mention_count']} review mentions around {top_name}, "
                "resolving this quickly can protect your reputation and revenue."
            ),
            "proof_points": [
                f"Businesses that address {top_name} see improved review scores within 60 days.",
                "Our solution integrates in under a week with no disruption to daily operations.",
                "We work specifically with businesses in the local services space.",
            ],
        }
