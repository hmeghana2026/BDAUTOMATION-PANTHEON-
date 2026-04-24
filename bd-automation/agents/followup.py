import logging
from datetime import datetime, timedelta
from database.models import Lead, Contact, Email
from database.supabase_client import SupabaseDB
from agents.email_drafter import EmailDrafterAgent
from integrations.resend_client import ResendClient

logger = logging.getLogger(__name__)

# Sequence: touch -> days since initial send
SEQUENCE_SCHEDULE = {
    2: 3,   # Day 3: value-add
    3: 7,   # Day 7: breakup email
    4: 10,  # Day 10: final offer
}
DEAD_AFTER_DAYS = 14


class FollowUpAgent:
    def __init__(self):
        self.db = SupabaseDB()
        self.drafter = EmailDrafterAgent()
        self.sender = ResendClient()

    def run_daily_followups(self) -> dict:
        """Called by Celery beat daily. Returns summary stats."""
        stats = {"sent": 0, "skipped": 0, "errors": 0, "dead_marked": 0}

        # Mark expired sequences as dead
        expired = self.db.get_expired_sequences()
        for row in expired:
            lead_id = row.get("contacts", {}).get("lead_id")
            if lead_id:
                try:
                    self.db.update_lead_status(lead_id, "dead")
                    stats["dead_marked"] += 1
                    logger.info(f"Marked lead {lead_id} as dead (no reply after {DEAD_AFTER_DAYS} days)")
                except Exception as e:
                    logger.error(f"Failed to mark lead {lead_id} dead: {e}")

        # Process due follow-ups
        due = self.db.get_pending_followups()
        emails_sent_today = self.db.count_emails_sent_today()
        daily_budget = 50

        for row in due:
            if emails_sent_today >= daily_budget:
                logger.warning("Daily email limit reached — stopping follow-ups")
                break

            try:
                result = self._process_followup(row)
                if result:
                    stats["sent"] += 1
                    emails_sent_today += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                logger.error(f"Follow-up error for email {row.get('id')}: {e}")
                stats["errors"] += 1

        logger.info(f"Follow-up run complete: {stats}")
        return stats

    def _process_followup(self, sent_email_row: dict) -> bool:
        sent_at = datetime.fromisoformat(sent_email_row["sent_at"].replace("Z", ""))
        days_since = (datetime.utcnow() - sent_at).days
        touch_number = self._get_touch_number(days_since)

        if touch_number is None:
            return False

        contact_id = sent_email_row["contact_id"]
        contact = self.db.get_contact(contact_id)
        if not contact or not contact.email:
            return False

        lead = self.db.get_lead(contact.lead_id)
        if not lead or lead.status == "dead" or lead.status == "meeting_set":
            return False

        # Build a minimal research result from available data
        from database.models import ResearchResult
        research = ResearchResult(
            company_name=lead.company_name,
            vertical=lead.vertical,
            insights=f"Following up on previous outreach to {lead.company_name}",
        )

        draft = self.drafter.draft_email(lead, contact, research, touch_number=touch_number)

        result = self.sender.send_email(
            to=contact.email,
            subject=draft.subject,
            body=draft.body,
        )

        if result["success"]:
            # Persist the follow-up email
            draft.status = "sent"
            email_record = self.db.create_email(draft)
            self.db.update_email_status(email_record.id, "sent", sent_at=datetime.utcnow())
            logger.info(f"Follow-up touch {touch_number} sent to {contact.email}")
            return True

        logger.warning(f"Follow-up send failed: {result.get('error')}")
        return False

    def _get_touch_number(self, days_since: int) -> int | None:
        for touch, day in SEQUENCE_SCHEDULE.items():
            if days_since == day:
                return touch
        return None

    def send_initial_sequence(self, lead: Lead, contact: Contact, email: Email) -> bool:
        """Trigger the full sequence for a new send by recording touch 1."""
        if not contact.email:
            logger.warning(f"No email for contact {contact.name} — skipping")
            return False

        result = self.sender.send_email(
            to=contact.email,
            subject=email.subject,
            body=email.body,
        )

        if result["success"]:
            self.db.update_email_status(email.id, "sent", sent_at=datetime.utcnow())
            self.db.update_lead_status(lead.id, "sent")
            logger.info(f"Initial email sent to {contact.email} for {lead.company_name}")
            return True

        logger.error(f"Failed to send initial email to {contact.email}: {result.get('error')}")
        return False
