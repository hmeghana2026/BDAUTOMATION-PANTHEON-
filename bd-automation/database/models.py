from pydantic import BaseModel, field_validator
from typing import Optional, Literal
from datetime import datetime
import uuid


class Lead(BaseModel):
    id: Optional[str] = None
    company_name: str
    vertical: Literal["restaurant", "vet", "dermatologist"]
    geography: Optional[str] = None
    website: Optional[str] = None
    status: Literal["new", "researching", "drafted", "sent", "meeting_set", "dead"] = "new"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("website", mode="before")
    @classmethod
    def normalize_website(cls, v):
        if v and not v.startswith(("http://", "https://")):
            return f"https://{v}"
        return v


class Contact(BaseModel):
    id: Optional[str] = None
    lead_id: str
    name: str
    role: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    created_at: Optional[datetime] = None


class Email(BaseModel):
    id: Optional[str] = None
    contact_id: str
    subject: Optional[str] = None
    body: Optional[str] = None
    status: Literal["draft", "approved", "sent", "bounced", "replied"] = "draft"
    sent_at: Optional[datetime] = None
    reply_received: bool = False
    created_at: Optional[datetime] = None


class Meeting(BaseModel):
    id: Optional[str] = None
    contact_id: str
    scheduled_at: Optional[datetime] = None
    transcript: Optional[str] = None
    prd_generated: Optional[str] = None
    prototype_url: Optional[str] = None
    created_at: Optional[datetime] = None


class LeadWithContacts(BaseModel):
    lead: Lead
    contacts: list[Contact] = []
    emails: list[Email] = []


class ResearchResult(BaseModel):
    company_name: str
    website: Optional[str] = None
    description: Optional[str] = None
    owner_name: Optional[str] = None
    owner_role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    insights: Optional[str] = None
    vertical: str


class DailyStats(BaseModel):
    leads_added: int = 0
    emails_sent: int = 0
    replies_received: int = 0
    meetings_booked: int = 0
    emails_remaining_today: int = 50


class ResearchLog(BaseModel):
    id: Optional[str] = None
    lead_id: str
    scraped_content: Optional[str] = None
    extracted_data: Optional[dict] = None
    insights: Optional[str] = None
    email_verification_status: Optional[Literal["not_found", "verified", "unverified", "skipped"]] = None
    hunter_confidence: Optional[int] = None
    scrape_duration_ms: Optional[int] = None
    created_at: Optional[datetime] = None


class TaskLog(BaseModel):
    id: Optional[str] = None
    lead_id: Optional[str] = None
    task_type: Literal["research", "draft", "send", "followup", "cleanup"]
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    progress_pct: int = 0
    message: Optional[str] = None
    error_details: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class LeadScore(BaseModel):
    id: Optional[str] = None
    lead_id: str
    priority_score: int = 50
    website_quality_score: int = 0
    contact_quality_score: int = 0
    research_quality_score: int = 0
    last_calculated: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ── V2 Models ──────────────────────────────────────────────────────────────────

class DiscoveryCampaign(BaseModel):
    id: Optional[str] = None
    business_type: str
    geographic_center: str
    radius_miles: Optional[float] = 10.0
    max_results: int = 50
    status: Literal["discovering", "pending_approval", "approved", "rejected"] = "discovering"
    discovered_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DiscoveredBusiness(BaseModel):
    id: Optional[str] = None
    campaign_id: str
    business_name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    rating: Optional[float] = None
    distance_miles: Optional[float] = None
    channel: Optional[Literal["email", "sms", "both", "none"]] = "none"
    approved: bool = False
    created_at: Optional[datetime] = None


class SMSMessage(BaseModel):
    id: Optional[str] = None
    contact_id: str
    phone_number: str
    message_body: Optional[str] = None
    status: Literal["draft", "approved", "sent", "delivered", "failed", "replied"] = "draft"
    sent_at: Optional[datetime] = None
    twilio_sid: Optional[str] = None
    reply_received: bool = False
    created_at: Optional[datetime] = None


# ── Research Enhancement Models ────────────────────────────────────────────────

class TieredResearchResult(BaseModel):
    id: Optional[str] = None
    lead_id: str
    tiers_run: list
    results: dict  # tier_1, tier_2, etc.
    executed_at: Optional[datetime] = None


class CompetitorAnalysisResult(BaseModel):
    id: Optional[str] = None
    lead_id: str
    competitors: list
    capability_gaps: list
    outreach_talking_points: list
    generated_at: Optional[datetime] = None


class PainPointAnalysisResult(BaseModel):
    id: Optional[str] = None
    lead_id: str
    total_reviews_analyzed: int
    pain_points: list
    solution_mapping: list
    outreach_intelligence: dict
    generated_at: Optional[datetime] = None


class SignalScoringResult(BaseModel):
    id: Optional[str] = None
    lead_id: str
    priority_score: int
    qualification: str
    signals_detected: list
    total_possible_points: int
    recommendation: str
    scored_at: Optional[datetime] = None
