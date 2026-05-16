"""Signal-based lead prioritization with configurable weights per vertical."""
import logging
from typing import Optional
from database.models import Lead

logger = logging.getLogger(__name__)

SIGNAL_TEMPLATES = {
    "restaurant": [
        {
            "id": "recently_opened",
            "name": "Recently Opened (6-18mo)",
            "category": "maturity",
            "default_weight": 8,
            "detection": "business_age",
        },
        {
            "id": "poor_reviews",
            "name": "Poor Reviews (<4.0)",
            "category": "pain_point",
            "default_weight": 6,
            "detection": "rating_check",
            "threshold": 4.0,
        },
        {
            "id": "no_online_ordering",
            "name": "No Online Ordering",
            "category": "tech_gap",
            "default_weight": 9,
            "detection": "tech_scan",
            "keywords": ["order", "doordash", "grubhub", "ubereats", "toast", "online ordering"],
        },
        {
            "id": "no_reservation_system",
            "name": "No Reservation System",
            "category": "tech_gap",
            "default_weight": 7,
            "detection": "tech_scan",
            "keywords": ["opentable", "resy", "reservation", "book a table"],
        },
        {
            "id": "low_social_media",
            "name": "Low Social Presence",
            "category": "tech_gap",
            "default_weight": 4,
            "detection": "social_check",
        },
        {
            "id": "no_email_marketing",
            "name": "No Email Marketing",
            "category": "tech_gap",
            "default_weight": 6,
            "detection": "tech_scan",
            "keywords": ["mailchimp", "klaviyo", "constant contact", "constantcontact"],
        },
        {
            "id": "no_crm",
            "name": "No CRM",
            "category": "tech_gap",
            "default_weight": 8,
            "detection": "tech_scan",
            "keywords": ["hubspot", "salesforce", "zoho crm"],
        },
        {
            "id": "outdated_website",
            "name": "Outdated / No Website",
            "category": "tech_gap",
            "default_weight": 8,
            "detection": "website_age",
        },
    ],
    "vet": [
        {
            "id": "no_online_booking",
            "name": "No Online Booking",
            "category": "tech_gap",
            "default_weight": 9,
            "detection": "tech_scan",
            "keywords": ["book", "appointment", "schedule", "vetstoria", "calendly", "acuity"],
        },
        {
            "id": "wait_time_complaints",
            "name": "Wait Time Complaints in Reviews",
            "category": "pain_point",
            "default_weight": 8,
            "detection": "review_nlp",
            "keywords": ["long wait", "waiting room", "delayed appointment", "wait forever"],
        },
        {
            "id": "no_patient_portal",
            "name": "No Patient / Pet Portal",
            "category": "tech_gap",
            "default_weight": 8,
            "detection": "tech_scan",
            "keywords": ["patient portal", "pet portal", "my account", "client portal"],
        },
        {
            "id": "no_reminder_system",
            "name": "No Automated Reminders",
            "category": "tech_gap",
            "default_weight": 7,
            "detection": "review_nlp",
            "keywords": ["forgot appointment", "no reminder", "no notification", "no call"],
        },
        {
            "id": "multiple_locations",
            "name": "Multiple Locations",
            "category": "growth",
            "default_weight": 8,
            "detection": "location_count",
            "threshold": 2,
        },
        {
            "id": "poor_reviews",
            "name": "Poor Reviews (<4.0)",
            "category": "pain_point",
            "default_weight": 6,
            "detection": "rating_check",
            "threshold": 4.0,
        },
        {
            "id": "no_crm",
            "name": "No Practice Management System",
            "category": "tech_gap",
            "default_weight": 9,
            "detection": "tech_scan",
            "keywords": ["ezyvet", "avimark", "cornerstone", "impromed", "practice management"],
        },
    ],
    "dermatologist": [
        {
            "id": "no_online_booking",
            "name": "No Online Booking",
            "category": "tech_gap",
            "default_weight": 9,
            "detection": "tech_scan",
            "keywords": ["book", "appointment", "schedule", "zocdoc", "calendly", "acuity"],
        },
        {
            "id": "wait_time_complaints",
            "name": "Wait Time Complaints in Reviews",
            "category": "pain_point",
            "default_weight": 8,
            "detection": "review_nlp",
            "keywords": ["long wait", "wait time", "delayed", "waiting"],
        },
        {
            "id": "poor_reviews",
            "name": "Poor Reviews (<4.0)",
            "category": "pain_point",
            "default_weight": 7,
            "detection": "rating_check",
            "threshold": 4.0,
        },
        {
            "id": "no_email_marketing",
            "name": "No Email Marketing / Newsletter",
            "category": "tech_gap",
            "default_weight": 6,
            "detection": "tech_scan",
            "keywords": ["mailchimp", "klaviyo", "constant contact", "newsletter"],
        },
        {
            "id": "outdated_website",
            "name": "Outdated / No Website",
            "category": "tech_gap",
            "default_weight": 8,
            "detection": "website_age",
        },
        {
            "id": "no_patient_portal",
            "name": "No Patient Portal",
            "category": "tech_gap",
            "default_weight": 8,
            "detection": "tech_scan",
            "keywords": ["patient portal", "my chart", "health portal", "client portal"],
        },
    ],
}

QUALIFICATION_THRESHOLDS = {
    "high_priority": 70,
    "medium_priority": 45,
    "low_priority": 20,
}

QUALIFICATION_LABELS = [
    ("high_priority", 70),
    ("medium_priority", 45),
    ("low_priority", 20),
    ("not_qualified", 0),
]


class SignalScorer:
    """Score a lead 0-100 based on configurable buying signals detected from tier results."""

    def score(
        self,
        lead: Lead,
        tier_results: dict,
        signal_weights: Optional[dict] = None,
        vertical: Optional[str] = None,
    ) -> dict:
        """
        Args:
            lead: Lead object
            tier_results: Output dict from TieredResearchService.run()
            signal_weights: Optional {signal_id: weight} overrides
            vertical: Override vertical (defaults to lead.vertical)

        Returns dict with priority_score, qualification, signals_detected, etc.
        """
        v = (vertical or lead.vertical or "restaurant").lower()
        # Normalize verticals
        if v in ("vet", "veterinarian", "veterinarians"):
            v = "vet"
        elif v in ("dermatologist", "dermatologists"):
            v = "dermatologist"
        else:
            v = "restaurant"

        signals = SIGNAL_TEMPLATES.get(v, SIGNAL_TEMPLATES["restaurant"])
        weights = signal_weights or {}

        detected = self._detect_signals(lead, tier_results, signals, weights)

        total_possible = sum(
            weights.get(s["id"], s["default_weight"]) for s in signals
        )
        total_earned = sum(d["points_earned"] for d in detected)

        raw_score = (total_earned / total_possible * 100) if total_possible > 0 else 0
        priority_score = min(int(raw_score), 100)

        qualification = "not_qualified"
        for label, threshold in QUALIFICATION_LABELS:
            if priority_score >= threshold:
                qualification = label
                break

        recommendation = self._recommendation(qualification, detected, v)

        return {
            "priority_score": priority_score,
            "qualification": qualification,
            "signals_detected": detected,
            "total_possible_points": total_possible,
            "total_earned_points": total_earned,
            "recommendation": recommendation,
        }

    def _detect_signals(
        self, lead: Lead, tier_results: dict, signals: list, weights: dict
    ) -> list:
        detected = []

        # Pull useful data from tier results once
        tier1 = tier_results.get("tier_1", {}).get("data", {})
        tier2 = tier_results.get("tier_2", {}).get("data", {})
        tier3 = tier_results.get("tier_3", {}).get("data", {})

        google_rating = tier1.get("google_rating")
        yelp_rating = tier1.get("yelp_rating")
        yelp_reviews = tier1.get("yelp_reviews", [])
        review_texts = " ".join(r.get("text", "") for r in yelp_reviews).lower()

        online_presence = tier2.get("online_presence", {})
        website_content = tier2.get("website_content", "").lower()
        social_links = tier2.get("social_media", [])

        tech_stack = tier3.get("tech_stack", {})
        tech_content = website_content  # same scraped content used for tech detection

        for sig in signals:
            sig_id = sig["id"]
            weight = weights.get(sig_id, sig["default_weight"])
            detection = sig.get("detection", "")
            is_detected = False
            value = None

            try:
                if detection == "rating_check":
                    threshold = sig.get("threshold", 4.0)
                    rating = google_rating or yelp_rating
                    if rating is not None:
                        is_detected = float(rating) < float(threshold)
                        value = rating

                elif detection == "tech_scan":
                    keywords = sig.get("keywords", [])
                    # First check tier2 website content, then tier3 tech_stack
                    found_in_content = any(kw in tech_content for kw in keywords)
                    found_in_tech = any(
                        any(kw in name for kw in keywords)
                        for category in tech_stack.values()
                        for name, present in category.items()
                        if present
                    ) if isinstance(tech_stack, dict) else False
                    # Signal fires when the capability is ABSENT
                    is_detected = not (found_in_content or found_in_tech)

                elif detection == "review_nlp":
                    keywords = sig.get("keywords", [])
                    is_detected = any(kw in review_texts for kw in keywords)

                elif detection == "social_check":
                    is_detected = len(social_links) == 0

                elif detection == "website_age":
                    # Fire if no website at all
                    is_detected = not bool(lead.website)

                elif detection == "location_count":
                    # Can't determine multi-location from current data; default off
                    is_detected = False

                elif detection == "business_age":
                    # Can't determine age from current data; default off
                    is_detected = False

            except Exception as e:
                logger.warning(f"Signal detection failed for {sig_id}: {e}")

            detected.append({
                "signal_id": sig_id,
                "name": sig["name"],
                "category": sig.get("category", ""),
                "detected": is_detected,
                "value": value,
                "weight": weight,
                "points_earned": weight if is_detected else 0,
            })

        return detected

    def _recommendation(self, qualification: str, signals: list, vertical: str) -> str:
        detected_names = [s["name"] for s in signals if s["detected"]]
        top = detected_names[:3]

        if qualification == "high_priority":
            return (
                f"High-priority {vertical} lead. Key gaps: {', '.join(top)}. "
                "Reach out immediately with a targeted pitch."
            )
        elif qualification == "medium_priority":
            return (
                f"Medium-priority {vertical} lead. Some gaps detected: {', '.join(top)}. "
                "Worth pursuing with a personalized approach."
            )
        elif qualification == "low_priority":
            return (
                f"Low-priority {vertical} lead. Few signals detected. "
                "Consider revisiting after higher-priority leads."
            )
        else:
            return (
                f"Not yet qualified. Insufficient signal data for {vertical}. "
                "Run additional research tiers for a better assessment."
            )
