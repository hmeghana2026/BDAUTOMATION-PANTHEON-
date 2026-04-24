import logging
import json
import re
from urllib.parse import urlparse
from database.models import Lead, Contact, ResearchResult
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


class LeadResearchAgent:
    def __init__(self):
        self.llm = LLMRouter()
        self.scraper = FirecrawlClient()
        self.hunter = HunterClient()

    def research_lead(self, lead: Lead) -> ResearchResult:
        """Full research pipeline for a single lead."""
        logger.info(f"Researching lead: {lead.company_name}")

        content = ""
        if lead.website:
            content = self.scraper.scrape(lead.website)
            logger.info(f"Scraped {len(content)} chars from {lead.website}")

        extracted = self._extract_with_llm(content, lead.vertical, lead.company_name)

        # Hunter.io email discovery if we have a domain
        if lead.website and not extracted.get("email"):
            domain = self._extract_domain(lead.website)
            if domain:
                first = ""
                last = ""
                if extracted.get("owner_name"):
                    parts = extracted["owner_name"].split()
                    first = parts[0] if parts else ""
                    last = parts[-1] if len(parts) > 1 else ""
                hunter_result = self.hunter.find_email(domain, first, last)
                if hunter_result.get("email") and hunter_result.get("confidence", 0) >= 60:
                    extracted["email"] = hunter_result["email"]
                    logger.info(f"Hunter found email: {extracted['email']}")

        # Verify email if found
        if extracted.get("email"):
            verification = self.hunter.verify_email(extracted["email"])
            if not verification.get("deliverable", True):
                logger.warning(f"Email {extracted['email']} failed verification — clearing")
                extracted["email"] = None

        # Generate richer insights if content is available
        if content and len(content) > 200:
            extracted["insights"] = self._generate_insights(
                lead.company_name,
                lead.vertical,
                lead.geography or "",
                content[:3000],
            )

        return ResearchResult(
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

    def _extract_with_llm(self, content: str, vertical: str, company_name: str) -> dict:
        if not content:
            return {}
        prompt = RESEARCH_PROMPT.format(
            vertical=vertical,
            content=content[:6000],
        )
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
            parsed = urlparse(url)
            return parsed.netloc.lstrip("www.")
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
