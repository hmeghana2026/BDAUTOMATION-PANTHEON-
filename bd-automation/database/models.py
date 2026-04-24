from pydantic import BaseModel, EmailStr, field_validator
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
