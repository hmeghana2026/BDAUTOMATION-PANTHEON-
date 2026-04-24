import logging
import json
import os
from database.models import Lead, Contact, Email, ResearchResult
from integrations import LLMRouter

logger = logging.getLogger(__name__)

TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "email_templates.json")

DRAFT_SYSTEM = """You are a senior business development specialist writing personalized cold outreach emails.
Write concise, genuine emails that don't sound like templates. Be specific to the business.
Return ONLY valid JSON with keys: subject, body."""

DRAFT_PROMPT = """Write a personalized outreach email for the following business.

Business: {company_name}
Vertical: {vertical}
Contact: {contact_name} ({contact_role})
Insights: {insights}
Template guidance: {template_guidance}
Sequence touch: {touch_number} (1=initial, 2=value-add, 3=breakup, 4=final offer)

Requirements:
- Subject line: under 10 words, curiosity-driven
- Body: 4-6 sentences max
- Reference at least one specific insight
- CTA: soft ask for a 15-min call
- Tone: friendly, peer-to-peer, NOT salesy

Return JSON: {{"subject": "...", "body": "..."}}"""


class EmailDrafterAgent:
    def __init__(self):
        self.llm = LLMRouter()
        self.templates = self._load_templates()

    def _load_templates(self) -> dict:
        try:
            with open(TEMPLATES_PATH) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load templates: {e}")
            return {}

    def draft_email(
        self,
        lead: Lead,
        contact: Contact,
        research: ResearchResult,
        touch_number: int = 1,
    ) -> Email:
        template = self.templates.get(lead.vertical, {})
        template_guidance = template.get("prompt_template", "").format(
            company_name=lead.company_name,
            insights=research.insights or "",
        )

        prompt = DRAFT_PROMPT.format(
            company_name=lead.company_name,
            vertical=lead.vertical,
            contact_name=contact.name,
            contact_role=contact.role or "Owner",
            insights=research.insights or f"Local {lead.vertical} business",
            template_guidance=template_guidance,
            touch_number=touch_number,
        )

        try:
            raw = self.llm.complete(prompt, system=DRAFT_SYSTEM, max_tokens=400, temperature=0.8)
            import re
            raw = re.sub(r"```json|```", "", raw).strip()
            parsed = json.loads(raw)
            subject = parsed.get("subject", f"Quick question about {lead.company_name}")
            body = parsed.get("body", "")
        except Exception as e:
            logger.warning(f"Email draft LLM failed: {e}. Using fallback template.")
            subject, body = self._fallback_draft(lead, contact, research, touch_number)

        return Email(
            contact_id=contact.id,
            subject=subject,
            body=body,
            status="draft",
        )

    def _fallback_draft(
        self, lead: Lead, contact: Contact, research: ResearchResult, touch_number: int
    ) -> tuple[str, str]:
        template = self.templates.get(lead.vertical, {})
        subject_tmpl = template.get("subject", "Quick question about {company_name}")
        subject = subject_tmpl.format(company_name=lead.company_name)

        touches = {
            1: (
                f"Hi {contact.name},\n\n"
                f"I came across {lead.company_name} and was impressed by what you're doing.\n\n"
                f"{research.insights or ''}\n\n"
                "I help businesses like yours grow with targeted customer engagement tools. "
                "Would you have 15 minutes this week for a quick chat?\n\n"
                "Best,\n{sender}"
            ),
            2: (
                f"Hi {contact.name},\n\n"
                f"Following up on my last email — I wanted to share a quick case study "
                f"from a similar {lead.vertical} that saw a 23% increase in repeat customers.\n\n"
                "Happy to walk you through it. 15 minutes this week?\n\n"
                "Best,\n{sender}"
            ),
            3: (
                f"Hi {contact.name},\n\n"
                "I don't want to keep bothering you — should I close your file?\n\n"
                "If timing is just off, no worries at all. Just let me know.\n\n"
                "Best,\n{sender}"
            ),
            4: (
                f"Hi {contact.name},\n\n"
                "Last note from me — I have one opening this month for a complimentary strategy session. "
                "First come, first served.\n\n"
                "Interested? Just reply 'yes' and I'll send a link.\n\n"
                "Best,\n{sender}"
            ),
        }
        sender = os.getenv("FROM_NAME", "Your Name")
        body = touches.get(touch_number, touches[1]).format(sender=sender)
        return subject, body

    def draft_batch(
        self, leads_contacts: list[tuple[Lead, Contact, ResearchResult]]
    ) -> list[Email]:
        return [
            self.draft_email(lead, contact, research)
            for lead, contact, research in leads_contacts
        ]
