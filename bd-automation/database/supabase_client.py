import os
import logging
from typing import Optional
from datetime import datetime, timedelta
from supabase import create_client, Client
from .models import Lead, Contact, Email, Meeting, DailyStats, ResearchLog, TaskLog, LeadScore

logger = logging.getLogger(__name__)


class SupabaseDB:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
        self.client: Client = create_client(url, key)

    # ── Leads ──────────────────────────────────────────────────────────────

    def create_lead(self, lead: Lead) -> Lead:
        data = lead.model_dump(exclude={"id", "created_at", "updated_at"})
        result = self.client.table("leads").insert(data).execute()
        return Lead(**result.data[0])

    def get_lead(self, lead_id: str) -> Optional[Lead]:
        result = self.client.table("leads").select("*").eq("id", lead_id).execute()
        if result.data:
            return Lead(**result.data[0])
        return None

    def list_leads(self, status: Optional[str] = None) -> list[Lead]:
        query = self.client.table("leads").select("*").order("created_at", desc=True)
        if status:
            query = query.eq("status", status)
        result = query.execute()
        return [Lead(**row) for row in result.data]

    def update_lead_status(self, lead_id: str, status: str) -> Lead:
        result = (
            self.client.table("leads")
            .update({"status": status})
            .eq("id", lead_id)
            .execute()
        )
        return Lead(**result.data[0])

    def update_lead(self, lead_id: str, updates: dict) -> Lead:
        result = (
            self.client.table("leads")
            .update(updates)
            .eq("id", lead_id)
            .execute()
        )
        return Lead(**result.data[0])

    # ── Contacts ───────────────────────────────────────────────────────────

    def create_contact(self, contact: Contact) -> Contact:
        data = contact.model_dump(exclude={"id", "created_at"})
        result = self.client.table("contacts").insert(data).execute()
        return Contact(**result.data[0])

    def get_contacts_for_lead(self, lead_id: str) -> list[Contact]:
        result = (
            self.client.table("contacts").select("*").eq("lead_id", lead_id).execute()
        )
        return [Contact(**row) for row in result.data]

    def get_contact(self, contact_id: str) -> Optional[Contact]:
        result = (
            self.client.table("contacts").select("*").eq("id", contact_id).execute()
        )
        if result.data:
            return Contact(**result.data[0])
        return None

    # ── Emails ─────────────────────────────────────────────────────────────

    def create_email(self, email: Email) -> Email:
        data = email.model_dump(exclude={"id", "created_at"})
        result = self.client.table("emails").insert(data).execute()
        return Email(**result.data[0])

    def get_emails_for_contact(self, contact_id: str) -> list[Email]:
        result = (
            self.client.table("emails")
            .select("*")
            .eq("contact_id", contact_id)
            .order("created_at")
            .execute()
        )
        return [Email(**row) for row in result.data]

    def update_email_status(self, email_id: str, status: str, sent_at: Optional[datetime] = None) -> Email:
        updates = {"status": status}
        if sent_at:
            updates["sent_at"] = sent_at.isoformat()
        result = (
            self.client.table("emails")
            .update(updates)
            .eq("id", email_id)
            .execute()
        )
        return Email(**result.data[0])

    def mark_reply_received(self, email_id: str) -> Email:
        result = (
            self.client.table("emails")
            .update({"reply_received": True, "status": "replied"})
            .eq("id", email_id)
            .execute()
        )
        return Email(**result.data[0])

    def count_emails_sent_today(self) -> int:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat()
        result = (
            self.client.table("emails")
            .select("id", count="exact")
            .eq("status", "sent")
            .gte("sent_at", today_start)
            .execute()
        )
        return result.count or 0

    def get_pending_followups(self) -> list[dict]:
        """Return emails due for follow-up based on sequence schedule."""
        now = datetime.utcnow()
        result = self.client.table("emails").select(
            "*, contacts(lead_id, name, email)"
        ).eq("status", "sent").eq("reply_received", False).execute()

        due = []
        for row in result.data:
            sent_at = datetime.fromisoformat(row["sent_at"].replace("Z", ""))
            days_since = (now - sent_at).days
            # Sequence: Day 3, 7, 10 follow-ups
            if days_since in (3, 7, 10):
                due.append(row)
        return due

    def get_expired_sequences(self) -> list[dict]:
        """Return leads whose last email is > 14 days old with no reply."""
        cutoff = (datetime.utcnow() - timedelta(days=14)).isoformat()
        result = self.client.table("emails").select(
            "*, contacts(lead_id)"
        ).eq("status", "sent").eq("reply_received", False).lte("sent_at", cutoff).execute()
        return result.data

    # ── Meetings ───────────────────────────────────────────────────────────

    def create_meeting(self, meeting: Meeting) -> Meeting:
        data = meeting.model_dump(exclude={"id", "created_at"})
        result = self.client.table("meetings").insert(data).execute()
        return Meeting(**result.data[0])

    def update_meeting(self, meeting_id: str, updates: dict) -> Meeting:
        result = (
            self.client.table("meetings")
            .update(updates)
            .eq("id", meeting_id)
            .execute()
        )
        return Meeting(**result.data[0])

    def get_meetings(self) -> list[Meeting]:
        result = self.client.table("meetings").select("*").order("created_at", desc=True).execute()
        return [Meeting(**row) for row in result.data]

    # ── Analytics ──────────────────────────────────────────────────────────

    def get_pipeline_counts(self) -> dict:
        result = self.client.table("leads").select("status").execute()
        counts = {"new": 0, "researching": 0, "drafted": 0, "sent": 0, "meeting_set": 0, "dead": 0}
        for row in result.data:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        return counts

    # ── Research Logs ──────────────────────────────────────────────────

    def create_research_log(self, log: ResearchLog) -> ResearchLog:
        data = log.model_dump(exclude={"id", "created_at"})
        if data.get("extracted_data") is not None:
            import json
            data["extracted_data"] = data["extracted_data"]
        result = self.client.table("research_logs").insert(data).execute()
        return ResearchLog(**result.data[0])

    def get_research_logs_for_lead(self, lead_id: str) -> list[ResearchLog]:
        result = (
            self.client.table("research_logs")
            .select("*")
            .eq("lead_id", lead_id)
            .order("created_at", desc=True)
            .execute()
        )
        return [ResearchLog(**row) for row in result.data]

    # ── Lead Scores ────────────────────────────────────────────────────

    def get_lead_score(self, lead_id: str) -> Optional[LeadScore]:
        result = (
            self.client.table("lead_scores").select("*").eq("lead_id", lead_id).execute()
        )
        if result.data:
            return LeadScore(**result.data[0])
        return None

    def upsert_lead_score(self, score: LeadScore) -> LeadScore:
        data = score.model_dump(exclude={"id", "created_at", "last_calculated"})
        result = (
            self.client.table("lead_scores")
            .upsert(data, on_conflict="lead_id")
            .execute()
        )
        return LeadScore(**result.data[0])

    def list_leads_by_priority(self, status: Optional[str] = None) -> list[Lead]:
        """Return leads ordered by priority score descending."""
        query = (
            self.client.table("leads")
            .select("*, lead_scores(priority_score)")
            .order("created_at", desc=True)
        )
        if status:
            query = query.eq("status", status)
        result = query.execute()
        leads = [Lead(**{k: v for k, v in row.items() if k != "lead_scores"}) for row in result.data]
        scores = {
            row["id"]: (row.get("lead_scores") or [{}])[0].get("priority_score", 50)
            if isinstance(row.get("lead_scores"), list)
            else (row.get("lead_scores") or {}).get("priority_score", 50)
            for row in result.data
        }
        return sorted(leads, key=lambda l: scores.get(l.id, 50), reverse=True)

    # ── Task Logs ──────────────────────────────────────────────────────

    def create_task_log(self, log: TaskLog) -> TaskLog:
        data = log.model_dump(exclude={"id", "created_at"})
        for dt_field in ("started_at", "completed_at"):
            if data.get(dt_field) and hasattr(data[dt_field], "isoformat"):
                data[dt_field] = data[dt_field].isoformat()
        result = self.client.table("task_logs").insert(data).execute()
        return TaskLog(**result.data[0])

    def update_task_log(self, task_id: str, updates: dict) -> TaskLog:
        for dt_field in ("started_at", "completed_at"):
            if updates.get(dt_field) and hasattr(updates[dt_field], "isoformat"):
                updates[dt_field] = updates[dt_field].isoformat()
        result = (
            self.client.table("task_logs")
            .update(updates)
            .eq("id", task_id)
            .execute()
        )
        return TaskLog(**result.data[0])

    def get_recent_activity(self, limit: int = 20) -> list[TaskLog]:
        result = (
            self.client.table("task_logs")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [TaskLog(**row) for row in result.data]

    def get_active_tasks(self, hours: int = 1) -> list[TaskLog]:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        result = (
            self.client.table("task_logs")
            .select("*")
            .in_("status", ["pending", "running"])
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .execute()
        )
        return [TaskLog(**row) for row in result.data]

    # ── Analytics ──────────────────────────────────────────────────────

    def get_daily_stats(self) -> DailyStats:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat()
        emails_sent_today = self.count_emails_sent_today()

        replies = (
            self.client.table("emails")
            .select("id", count="exact")
            .eq("reply_received", True)
            .gte("created_at", today_start)
            .execute()
        )
        leads_today = (
            self.client.table("leads")
            .select("id", count="exact")
            .gte("created_at", today_start)
            .execute()
        )
        meetings_today = (
            self.client.table("meetings")
            .select("id", count="exact")
            .gte("created_at", today_start)
            .execute()
        )
        return DailyStats(
            leads_added=leads_today.count or 0,
            emails_sent=emails_sent_today,
            replies_received=replies.count or 0,
            meetings_booked=meetings_today.count or 0,
            emails_remaining_today=max(0, 50 - emails_sent_today),
        )
