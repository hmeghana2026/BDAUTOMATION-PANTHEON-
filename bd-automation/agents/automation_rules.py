"""Automation rules engine — priority scoring, skip/send gates, adaptive scheduling."""
import logging
from datetime import datetime
from database.models import Lead

logger = logging.getLogger(__name__)

VERTICAL_WEIGHTS = {
    "vet": 10,
    "dermatologist": 8,
    "restaurant": 5,
}

BOOKING_KEYWORDS = ["appointment", "booking", "schedule", "reserve", "contact", "book"]

# Per-vertical follow-up day schedule: {touch_number: day}
VERTICAL_FOLLOWUP_DAYS = {
    "vet":           {2: 3,  3: 7,  4: 14},
    "dermatologist": {2: 4,  3: 9,  4: 16},
    "restaurant":    {2: 2,  3: 5,  4: 10},
}


class AutomationRules:
    def __init__(self, db=None):
        self._db = db

    def _get_db(self):
        if self._db is None:
            from database.supabase_client import SupabaseDB
            self._db = SupabaseDB()
        return self._db

    # ── Priority scoring ───────────────────────────────────────────────

    def calculate_priority_score(self, lead: Lead) -> int:
        """Score a lead 0-100 based on available signals."""
        score = 0

        # Website quality (0-20)
        if lead.website:
            score += 10
            if any(k in lead.website.lower() for k in BOOKING_KEYWORDS):
                score += 10

        # Geography specificity (0-10)
        if lead.geography:
            parts = [p.strip() for p in lead.geography.split(",")]
            score += 10 if len(parts) >= 2 else 5

        # Vertical weight (0-10)
        score += VERTICAL_WEIGHTS.get(lead.vertical, 5)

        # Contact quality (0-15) — needs DB
        try:
            contacts = self._get_db().get_contacts_for_lead(lead.id)
            if contacts:
                c = contacts[0]
                if c.email:
                    score += 8
                if c.phone:
                    score += 4
                if c.role:
                    score += 3
        except Exception:
            pass

        # Research quality (0-30) — needs DB
        try:
            logs = self._get_db().get_research_logs_for_lead(lead.id)
            if logs:
                log = logs[0]
                if log.email_verification_status == "verified":
                    score += 15
                if log.insights and len(log.insights) > 100:
                    score += 10
                if log.hunter_confidence and log.hunter_confidence >= 90:
                    score += 5
        except Exception:
            pass

        return min(score, 100)

    def calculate_score_components(self, lead: Lead) -> dict:
        """Return individual subscore components for display."""
        website_q = 0
        if lead.website:
            website_q = 10
            if any(k in lead.website.lower() for k in BOOKING_KEYWORDS):
                website_q = 20

        geo_q = 0
        if lead.geography:
            parts = [p.strip() for p in lead.geography.split(",")]
            geo_q = 10 if len(parts) >= 2 else 5

        vertical_q = VERTICAL_WEIGHTS.get(lead.vertical, 5)

        contact_q = 0
        try:
            contacts = self._get_db().get_contacts_for_lead(lead.id)
            if contacts:
                c = contacts[0]
                if c.email:
                    contact_q += 8
                if c.phone:
                    contact_q += 4
                if c.role:
                    contact_q += 3
        except Exception:
            pass

        research_q = 0
        try:
            logs = self._get_db().get_research_logs_for_lead(lead.id)
            if logs:
                log = logs[0]
                if log.email_verification_status == "verified":
                    research_q += 15
                if log.insights and len(log.insights) > 100:
                    research_q += 10
                if log.hunter_confidence and log.hunter_confidence >= 90:
                    research_q += 5
        except Exception:
            pass

        return {
            "website": website_q,
            "geography": geo_q,
            "vertical": vertical_q,
            "contact": contact_q,
            "research": research_q,
            "total": min(website_q + geo_q + vertical_q + contact_q + research_q, 100),
        }

    # ── Skip gate ─────────────────────────────────────────────────────

    def should_skip_lead(self, lead: Lead) -> tuple[bool, str]:
        """Return (True, reason) if this lead should be skipped for research."""
        if not lead.website:
            return True, "No website — cannot research"

        try:
            logs = self._get_db().get_research_logs_for_lead(lead.id)
            if logs and logs[0].created_at:
                days_ago = (datetime.utcnow() - logs[0].created_at.replace(tzinfo=None)).days
                if days_ago < 7:
                    return True, f"Researched {days_ago} days ago"
        except Exception:
            pass

        return False, ""

    # ── Auto-send gate ────────────────────────────────────────────────

    def should_auto_send(self, lead: Lead) -> tuple[bool, str]:
        """Return (True, reason) if this lead passes quality gates for sending."""
        try:
            db = self._get_db()

            score_obj = db.get_lead_score(lead.id)
            if score_obj and score_obj.priority_score < 60:
                return False, f"Priority score too low ({score_obj.priority_score}/100)"

            contacts = db.get_contacts_for_lead(lead.id)
            if not contacts:
                return False, "No contacts found"

            if not any(c.email for c in contacts):
                return False, "No email address found"

            logs = db.get_research_logs_for_lead(lead.id)
            if logs and logs[0].email_verification_status == "not_found":
                return False, "Email verification failed"

        except Exception as e:
            logger.warning(f"Auto-send check error for {lead.company_name}: {e}")

        return True, "Passes all quality gates"

    # ── Adaptive follow-up scheduling ─────────────────────────────────

    def get_adaptive_followup_day(self, lead: Lead, touch_number: int) -> int:
        """Return the day offset for a given follow-up touch number."""
        schedule = VERTICAL_FOLLOWUP_DAYS.get(lead.vertical, {2: 3, 3: 7, 4: 14})
        return schedule.get(touch_number, touch_number * 3)

    # ── Lead prioritization ───────────────────────────────────────────

    def prioritize_leads(self, leads: list[Lead]) -> list[tuple[Lead, int]]:
        """Return leads sorted by priority score descending."""
        scored = [(lead, self.calculate_priority_score(lead)) for lead in leads]
        return sorted(scored, key=lambda x: x[1], reverse=True)
