"""Celery background tasks for BD Automation Platform."""
import os
import logging
from datetime import datetime
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery("bd_automation", broker=REDIS_URL, backend=REDIS_URL)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_max_tasks_per_child=50,  # Prevent memory leaks
    task_acks_late=True,
)

# ── Celery Beat schedule ─────────────────────────────────────────────────────

app.conf.beat_schedule = {
    # Research new leads every 30 minutes
    "research-new-leads": {
        "task": "tasks.research_new_leads",
        "schedule": crontab(minute="*/30"),
    },
    # Draft emails for researched leads every hour
    "draft-emails-for-researched-leads": {
        "task": "tasks.draft_emails_for_researched_leads",
        "schedule": crontab(minute=15),
    },
    # Auto-send drafted emails at 9 AM UTC daily
    "auto-send-drafted-emails": {
        "task": "tasks.auto_send_drafted_emails",
        "schedule": crontab(hour=9, minute=0),
    },
    # Run follow-up sequences at 10 AM UTC daily
    "run-followup-sequences": {
        "task": "tasks.run_followup_sequences",
        "schedule": crontab(hour=10, minute=0),
    },
    # Clean up expired sequences at midnight
    "cleanup-expired-sequences": {
        "task": "tasks.cleanup_expired_sequences",
        "schedule": crontab(hour=0, minute=0),
    },
}


# ── Task implementations ─────────────────────────────────────────────────────

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def research_new_leads(self):
    """Research all leads in 'new' status, skipping recently-researched and prioritising by score."""
    try:
        from database.supabase_client import SupabaseDB
        from agents.lead_research import LeadResearchAgent
        from agents.automation_rules import AutomationRules
        from database.models import Contact, TaskLog

        database = SupabaseDB()
        agent = LeadResearchAgent(db=database)
        rules = AutomationRules(db=database)

        new_leads = database.list_leads(status="new")
        logger.info(f"Researching {len(new_leads)} new leads")

        # Prioritize: higher-scored leads first
        prioritized = rules.prioritize_leads(new_leads)
        results = {"processed": 0, "failed": 0, "skipped": 0, "contacts_created": 0}

        for lead, score in prioritized:
            # Skip gate
            should_skip, skip_reason = rules.should_skip_lead(lead)
            if should_skip:
                logger.info(f"Skipping {lead.company_name}: {skip_reason}")
                results["skipped"] += 1
                continue

            task_log = database.create_task_log(TaskLog(
                lead_id=lead.id,
                task_type="research",
                status="running",
                message=f"Researching {lead.company_name} (score: {score})",
                started_at=datetime.utcnow(),
                progress_pct=0,
            ))

            try:
                database.update_lead_status(lead.id, "researching")
                database.update_task_log(task_log.id, {"progress_pct": 30})

                research = agent.research_lead(lead)

                database.update_task_log(task_log.id, {"progress_pct": 70})

                if research.owner_name or research.email:
                    contact = Contact(
                        lead_id=lead.id,
                        name=research.owner_name or lead.company_name,
                        role=research.owner_role or "Owner",
                        email=research.email,
                        phone=research.phone,
                    )
                    database.create_contact(contact)
                    results["contacts_created"] += 1

                database.update_task_log(task_log.id, {
                    "status": "completed",
                    "progress_pct": 100,
                    "message": f"Research complete for {lead.company_name}",
                    "completed_at": datetime.utcnow(),
                })
                results["processed"] += 1
                logger.info(f"Researched: {lead.company_name}")

            except Exception as e:
                logger.error(f"Failed to research {lead.company_name}: {e}")
                database.update_task_log(task_log.id, {
                    "status": "failed",
                    "error_details": str(e),
                    "completed_at": datetime.utcnow(),
                })
                results["failed"] += 1
                database.update_lead_status(lead.id, "new")

        return results

    except Exception as exc:
        logger.error(f"research_new_leads task failed: {exc}")
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=3, default_retry_delay=120)
def draft_emails_for_researched_leads(self):
    """Draft emails for all leads in 'researching' status that have contacts."""
    try:
        from database.supabase_client import SupabaseDB
        from agents.email_drafter import EmailDrafterAgent
        from database.models import ResearchResult

        database = SupabaseDB()
        agent = EmailDrafterAgent()

        researched_leads = database.list_leads(status="researching")
        results = {"drafted": 0, "skipped": 0, "failed": 0}

        for lead in researched_leads:
            try:
                contacts = database.get_contacts_for_lead(lead.id)
                if not contacts:
                    results["skipped"] += 1
                    continue

                # Use first contact with email
                contact = next((c for c in contacts if c.email), None)
                if not contact:
                    results["skipped"] += 1
                    continue

                research = ResearchResult(
                    company_name=lead.company_name,
                    vertical=lead.vertical,
                    insights=f"Local {lead.vertical} business in {lead.geography or 'the area'}",
                )

                draft = agent.draft_email(lead, contact, research, touch_number=1)
                database.create_email(draft)
                database.update_lead_status(lead.id, "drafted")
                results["drafted"] += 1
                logger.info(f"Drafted email for {lead.company_name}")

            except Exception as e:
                logger.error(f"Draft failed for {lead.company_name}: {e}")
                results["failed"] += 1

        return results

    except Exception as exc:
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=2)
def auto_send_drafted_emails(self):
    """Auto-send drafted emails, applying quality gates via AutomationRules."""
    try:
        from database.supabase_client import SupabaseDB
        from agents.followup import FollowUpAgent
        from agents.automation_rules import AutomationRules
        from database.models import TaskLog

        database = SupabaseDB()
        agent = FollowUpAgent()
        rules = AutomationRules(db=database)

        daily_sent = database.count_emails_sent_today()
        budget = 50 - daily_sent

        if budget <= 0:
            logger.info("Daily email budget exhausted — skipping auto-send")
            return {"sent": 0, "reason": "budget_exhausted"}

        drafted_leads = database.list_leads(status="drafted")
        results = {"sent": 0, "failed": 0, "skipped": 0, "blocked_by_rules": 0}

        for lead in drafted_leads:
            if results["sent"] >= budget:
                break

            # Quality gate
            should_send, reason = rules.should_auto_send(lead)
            if not should_send:
                logger.info(f"Blocking auto-send for {lead.company_name}: {reason}")
                results["blocked_by_rules"] += 1
                continue

            task_log = database.create_task_log(TaskLog(
                lead_id=lead.id,
                task_type="send",
                status="running",
                message=f"Sending email for {lead.company_name}",
                started_at=datetime.utcnow(),
                progress_pct=0,
            ))

            try:
                contacts = database.get_contacts_for_lead(lead.id)
                contact = next((c for c in contacts if c.email), None)
                if not contact:
                    database.update_task_log(task_log.id, {
                        "status": "failed",
                        "error_details": "No contact with email",
                        "completed_at": datetime.utcnow(),
                    })
                    results["skipped"] += 1
                    continue

                emails = database.get_emails_for_contact(contact.id)
                draft = next((e for e in emails if e.status == "draft"), None)
                if not draft:
                    database.update_task_log(task_log.id, {
                        "status": "failed",
                        "error_details": "No draft email found",
                        "completed_at": datetime.utcnow(),
                    })
                    results["skipped"] += 1
                    continue

                success = agent.send_initial_sequence(lead, contact, draft)
                if success:
                    database.update_task_log(task_log.id, {
                        "status": "completed",
                        "progress_pct": 100,
                        "message": f"Email sent to {contact.email}",
                        "completed_at": datetime.utcnow(),
                    })
                    results["sent"] += 1
                else:
                    database.update_task_log(task_log.id, {
                        "status": "failed",
                        "error_details": "Send returned False",
                        "completed_at": datetime.utcnow(),
                    })
                    results["failed"] += 1

            except Exception as e:
                logger.error(f"Auto-send failed for {lead.company_name}: {e}")
                database.update_task_log(task_log.id, {
                    "status": "failed",
                    "error_details": str(e),
                    "completed_at": datetime.utcnow(),
                })
                results["failed"] += 1

        logger.info(f"Auto-send complete: {results}")
        return results

    except Exception as exc:
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=3, default_retry_delay=300)
def run_followup_sequences(self):
    """Run daily follow-up sequence for all active leads."""
    try:
        from agents.followup import FollowUpAgent
        agent = FollowUpAgent()
        return agent.run_daily_followups()
    except Exception as exc:
        raise self.retry(exc=exc)


@app.task
def cleanup_expired_sequences():
    """Mark leads with no reply after 14 days as dead."""
    try:
        from database.supabase_client import SupabaseDB
        database = SupabaseDB()
        expired = database.get_expired_sequences()
        dead_count = 0
        for row in expired:
            lead_id = row.get("contacts", {}).get("lead_id")
            if lead_id:
                database.update_lead_status(lead_id, "dead")
                dead_count += 1
        logger.info(f"Cleanup: marked {dead_count} leads as dead")
        return {"dead_marked": dead_count}
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {"error": str(e)}


@app.task(bind=True, max_retries=2)
def process_single_lead(self, lead_id: str):
    """Full pipeline for a single lead: research → draft → send."""
    try:
        from database.supabase_client import SupabaseDB
        from agents.lead_research import LeadResearchAgent
        from agents.email_drafter import EmailDrafterAgent
        from agents.followup import FollowUpAgent
        from database.models import Contact

        database = SupabaseDB()
        lead = database.get_lead(lead_id)
        if not lead:
            return {"error": f"Lead {lead_id} not found"}

        # Research
        research_agent = LeadResearchAgent()
        database.update_lead_status(lead.id, "researching")
        research = research_agent.research_lead(lead)

        contact = None
        if research.owner_name or research.email:
            contact = database.create_contact(
                Contact(
                    lead_id=lead.id,
                    name=research.owner_name or lead.company_name,
                    role=research.owner_role or "Owner",
                    email=research.email,
                    phone=research.phone,
                )
            )

        if not contact or not contact.email:
            logger.warning(f"No verified email found for {lead.company_name}")
            return {"status": "researched_no_email"}

        # Draft
        drafter = EmailDrafterAgent()
        draft = drafter.draft_email(lead, contact, research, touch_number=1)
        email_record = database.create_email(draft)
        database.update_lead_status(lead.id, "drafted")

        # Send
        daily_sent = database.count_emails_sent_today()
        if daily_sent >= 50:
            logger.info(f"Daily limit reached — {lead.company_name} drafted but not sent")
            return {"status": "drafted_pending_send"}

        followup = FollowUpAgent()
        success = followup.send_initial_sequence(lead, contact, email_record)
        return {"status": "sent" if success else "send_failed"}

    except Exception as exc:
        logger.error(f"process_single_lead failed for {lead_id}: {exc}")
        raise self.retry(exc=exc)
