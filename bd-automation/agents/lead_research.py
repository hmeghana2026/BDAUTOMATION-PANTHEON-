import time
import logging
import json
import re
from urllib.parse import urlparse
from database.models import Lead, Contact, ResearchResult, ResearchLog, LeadScore
from integrations import LLMRouter, FirecrawlClient, HunterClient

logger = logging.getLogger(__name__)

RESEARCH_SYSTEM = """You are a business intelligence analyst extracting contact and business information.
Return ONLY valid JSON — no markdown, no explanation."""

RESEARCH_PROMPT = """Extract business information from the following web content for a {vertical} business.

Website content:
{content}

Return JSON with these exact keys:
{{
  "owner_name": "string or null",
  "owner_role": "string or null",
  "phone": "string or null",
  "email": "string or null",
  "description": "1-2 sentence business description",
  "insights": "2-3 specific observations useful for personalized outreach (pain points, recent news, unique selling points)",
  "services": "comma-separated list of main services"
}}"""

INSIGHTS_PROMPT = """You are a BD expert analyzing a {vertical} business for outreach.

Business: {company_name}
Location: {geography}
Website content summary: {content_snippet}

Write 2-3 specific, actionable insights about this business that would make an outreach email feel highly personalized.
Focus on: likely pain points, growth opportunities, operational challenges typical for {vertical} businesses.
Keep it under 100 words. Return plain text only."""

BOOKING_KEYWORDS = ["appointment", "booking", "schedule", "reserve", "contact", "book"]


class LeadResearchAgent:
    def __init__(self, db=None):
        self.llm = LLMRouter()
        self.scraper = FirecrawlClient()
        self.hunter = HunterClient()
        self._db = db

    def _get_db(self):
        if self._db is None:
            from database.supabase_client import SupabaseDB
            self._db = SupabaseDB()
        return self._db

    def research_lead(self, lead: Lead) -> ResearchResult:
        """Full research pipeline for a single lead. Persists a ResearchLog and LeadScore."""
        logger.info(f"Researching lead: {lead.company_name}")

        content = ""
        scrape_duration_ms = None
        email_verification_status = "skipped"
        hunter_confidence = None
        extracted: dict = {}

        if lead.website:
            t0 = time.monotonic()
            content = self.scraper.scrape(lead.website)
            scrape_duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info(f"Scraped {len(content)} chars from {lead.website} in {scrape_duration_ms}ms")

        if content:
            extracted = self._extract_with_llm(content, lead.vertical, lead.company_name)

        # Hunter.io email discovery if not found in page
        if lead.website and not extracted.get("email"):
            domain = self._extract_domain(lead.website)
            if domain:
                first = last = ""
                if extracted.get("owner_name"):
                    parts = extracted["owner_name"].split()
                    first = parts[0] if parts else ""
                    last = parts[-1] if len(parts) > 1 else ""
                hunter_result = self.hunter.find_email(domain, first, last)
                hunter_confidence = hunter_result.get("confidence", 0)
                if hunter_result.get("email") and hunter_confidence >= 60:
                    extracted["email"] = hunter_result["email"]
                    logger.info(f"Hunter found email: {extracted['email']}")

        # Email verification
        if extracted.get("email"):
            verification = self.hunter.verify_email(extracted["email"])
            if verification.get("deliverable", True):
                email_verification_status = "verified"
            else:
                logger.warning(f"Email {extracted['email']} failed verification — clearing")
                extracted["email"] = None
                email_verification_status = "unverified"
        else:
            email_verification_status = "not_found"

        # Richer insights from scraped content
        if content and len(content) > 200:
            extracted["insights"] = self._generate_insights(
                lead.company_name, lead.vertical, lead.geography or "", content[:3000]
            )

        result = ResearchResult(
            company_name=lead.company_name,
            website=lead.website,
            vertical=lead.vertical,
            description=extracted.get("description"),
            owner_name=extracted.get("owner_name"),
            owner_role=extracted.get("owner_role"),
            phone=extracted.get("phone"),
            email=extracted.get("email"),
            insights=extracted.get("insights", f"Local {lead.vertical} business in {lead.geography or 'the area'}"),
        )

        # Persist research log + lead score
        if lead.id:
            self._persist_research(lead, result, extracted, content,
                                   email_verification_status, hunter_confidence, scrape_duration_ms)

        return result

    def _persist_research(self, lead: Lead, result: ResearchResult, extracted: dict,
                          content: str, email_verification_status: str,
                          hunter_confidence, scrape_duration_ms):
        try:
            db = self._get_db()

            db.create_research_log(ResearchLog(
                lead_id=lead.id,
                scraped_content=content[:5000] if content else None,
                extracted_data=extracted or None,
                insights=result.insights,
                email_verification_status=email_verification_status,
                hunter_confidence=hunter_confidence,
                scrape_duration_ms=scrape_duration_ms,
            ))

            # Score components
            website_q = 0
            if lead.website:
                website_q = 20 if any(k in lead.website.lower() for k in BOOKING_KEYWORDS) else 10

            contact_q = 0
            if result.email:
                contact_q += 8
            if result.phone:
                contact_q += 4
            if result.owner_role:
                contact_q += 3

            research_q = 0
            if email_verification_status == "verified":
                research_q += 15
            if result.insights and len(result.insights) > 100:
                research_q += 10
            if hunter_confidence and hunter_confidence >= 90:
                research_q += 5

            geo_q = 0
            if lead.geography:
                parts = [p.strip() for p in lead.geography.split(",")]
                geo_q = 10 if len(parts) >= 2 else 5

            from agents.automation_rules import VERTICAL_WEIGHTS
            vertical_q = VERTICAL_WEIGHTS.get(lead.vertical, 5)

            priority = min(website_q + geo_q + vertical_q + contact_q + research_q, 100)

            db.upsert_lead_score(LeadScore(
                lead_id=lead.id,
                priority_score=priority,
                website_quality_score=website_q,
                contact_quality_score=contact_q,
                research_quality_score=research_q,
            ))

        except Exception as e:
            logger.warning(f"Failed to persist research log for {lead.company_name}: {e}")

    def _extract_with_llm(self, content: str, vertical: str, company_name: str) -> dict:
        if not content:
            return {}
        prompt = RESEARCH_PROMPT.format(vertical=vertical, content=content[:6000])
        try:
            raw = self.llm.complete(prompt, system=RESEARCH_SYSTEM, max_tokens=512, temperature=0.2)
            raw = re.sub(r"```json|```", "", raw).strip()
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"LLM extraction failed for {company_name}: {e}")
            return {}

    def _generate_insights(self, company_name: str, vertical: str, geography: str, content: str) -> str:
        prompt = INSIGHTS_PROMPT.format(
            vertical=vertical,
            company_name=company_name,
            geography=geography,
            content_snippet=content,
        )
        try:
            return self.llm.complete(prompt, max_tokens=150, temperature=0.6)
        except Exception as e:
            logger.warning(f"Insight generation failed: {e}")
            return f"Local {vertical} business in {geography}"

    def _extract_domain(self, url: str) -> str:
        try:
            return urlparse(url).netloc.lstrip("www.")
        except Exception:
            return ""

    def batch_research(self, leads: list[Lead]) -> list[tuple[Lead, ResearchResult]]:
        results = []
        for lead in leads:
            try:
                result = self.research_lead(lead)
                results.append((lead, result))
            except Exception as e:
                logger.error(f"Research failed for {lead.company_name}: {e}")
        return results
