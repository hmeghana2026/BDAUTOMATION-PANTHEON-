import time
import logging
import json
import re
from urllib.parse import urlparse
from typing import Optional
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


class TieredResearchService:
    """4-tier research pipeline for leads."""

    TIERS = {
        1: "Basic Info (Google Maps + Yelp)",
        2: "Digital Presence (Website + Reviews)",
        3: "Tech Stack (Firecrawl analysis)",
        4: "Decision Maker (Hunter.io)",
    }

    def __init__(self, db=None):
        self.llm = LLMRouter()
        self.scraper = FirecrawlClient()
        self.hunter = HunterClient()
        self._db = db
        self._yelp = None
        self._gmaps = None

    @property
    def yelp(self):
        """Lazily initialise YelpClient so missing YELP_API_KEY doesn't crash."""
        if self._yelp is None:
            from integrations.yelp_client import YelpClient
            self._yelp = YelpClient()
        return self._yelp

    @property
    def gmaps(self):
        """Lazily initialise GoogleMapsClient so missing key doesn't crash."""
        if self._gmaps is None:
            from integrations.gmaps_client import GoogleMapsClient
            self._gmaps = GoogleMapsClient()
        return self._gmaps

    def _get_db(self):
        if self._db is None:
            from database.supabase_client import SupabaseDB
            self._db = SupabaseDB()
        return self._db

    def run(self, lead: Lead, tiers: Optional[list] = None) -> dict:
        """Run specified tiers (default [1,2]) and return results dict."""
        if tiers is None:
            tiers = [1, 2]
        results = {}
        for tier in sorted(tiers):
            try:
                if tier == 1:
                    results["tier_1"] = self._tier1(lead)
                elif tier == 2:
                    results["tier_2"] = self._tier2(lead)
                elif tier == 3:
                    results["tier_3"] = self._tier3(lead)
                elif tier == 4:
                    results["tier_4"] = self._tier4(lead)
            except Exception as e:
                logger.warning(f"Tier {tier} failed for {lead.company_name}: {e}")
                results[f"tier_{tier}"] = {"status": "failed", "error": str(e)}
        return results

    def _tier1(self, lead: Lead) -> dict:
        """Basic info from Google Maps + Yelp."""
        data = {}
        sources = []

        # Google Maps lookup
        try:
            places = self.gmaps.search_businesses(
                lead.company_name,
                lead.geography or lead.company_name,
                max_results=1,
            )
            if places:
                place = places[0]
                data["google_name"] = place.get("business_name")
                data["google_address"] = place.get("address")
                data["google_rating"] = place.get("rating")
                data["google_phone"] = place.get("phone")
                data["google_website"] = place.get("website")
                sources.append("google_maps")
        except Exception as e:
            logger.warning(f"Tier 1 Google Maps failed for {lead.company_name}: {e}")

        # Yelp lookup
        try:
            yelp_biz = self.yelp.search_business(
                lead.company_name,
                lead.geography or lead.company_name,
            )
            if yelp_biz:
                data["yelp_id"] = yelp_biz.get("id")
                data["yelp_name"] = yelp_biz.get("name")
                data["yelp_rating"] = yelp_biz.get("rating")
                data["yelp_review_count"] = yelp_biz.get("review_count")
                data["yelp_phone"] = yelp_biz.get("phone")
                data["yelp_url"] = yelp_biz.get("url")
                data["yelp_categories"] = yelp_biz.get("categories", [])
                sources.append("yelp")

                # Fetch reviews while we have the ID
                if yelp_biz.get("id"):
                    try:
                        reviews = self.yelp.get_reviews(yelp_biz["id"])
                        data["yelp_reviews"] = reviews
                    except Exception as rev_err:
                        logger.warning(f"Yelp reviews fetch failed: {rev_err}")
                        data["yelp_reviews"] = []
        except Exception as e:
            logger.warning(f"Tier 1 Yelp failed for {lead.company_name}: {e}")

        return {"status": "completed", "data": data, "sources": sources}

    def _tier2(self, lead: Lead) -> dict:
        """Digital presence: scrape website for reviews + online presence signals."""
        if not lead.website:
            return {"status": "skipped", "reason": "no website", "data": {}, "sources": []}

        try:
            content = self.scraper.scrape(lead.website)
        except Exception as e:
            logger.warning(f"Tier 2 scrape failed for {lead.company_name}: {e}")
            return {"status": "failed", "error": str(e), "data": {}, "sources": []}

        content_lower = content.lower() if content else ""

        ordering_keywords = ["order online", "order now", "doordash", "grubhub", "ubereats", "toast", "online ordering"]
        reservation_keywords = ["reservation", "opentable", "resy", "book a table"]
        booking_keywords = ["book appointment", "book online", "schedule online", "book now", "request appointment"]

        has_online_ordering = any(kw in content_lower for kw in ordering_keywords)
        has_reservation = any(kw in content_lower for kw in reservation_keywords)
        has_booking = any(kw in content_lower for kw in booking_keywords)

        # Social media presence detection
        social_platforms = ["facebook.com", "instagram.com", "twitter.com", "linkedin.com", "tiktok.com"]
        social_links = [p for p in social_platforms if p in content_lower]

        data = {
            "online_presence": {
                "has_online_ordering": has_online_ordering,
                "has_reservation": has_reservation,
                "has_booking": has_booking,
            },
            "social_media": social_links,
            "website_content_length": len(content),
            "website_content": content[:3000] if content else "",
        }

        return {"status": "completed", "data": data, "sources": ["website_scrape"]}

    def _tier3(self, lead: Lead) -> dict:
        """Tech stack detection from website HTML inspection."""
        if not lead.website:
            return {"status": "skipped", "reason": "no website", "data": {}, "sources": []}

        try:
            content = self.scraper.scrape(lead.website)
        except Exception as e:
            logger.warning(f"Tier 3 scrape failed for {lead.company_name}: {e}")
            return {"status": "failed", "error": str(e), "data": {}, "sources": []}

        content_lower = content.lower() if content else ""

        tech_signals = {
            "cms": {
                "wordpress": ["wordpress", "wp-content", "wp-includes"],
                "shopify": ["shopify", "cdn.shopify"],
                "wix": ["wix.com", "wixsite"],
                "squarespace": ["squarespace"],
                "webflow": ["webflow"],
            },
            "analytics": {
                "google_analytics": ["google-analytics", "gtag(", "ga(", "googletagmanager"],
                "hotjar": ["hotjar"],
                "mixpanel": ["mixpanel"],
            },
            "marketing": {
                "mailchimp": ["mailchimp", "list-manage.com"],
                "klaviyo": ["klaviyo"],
                "constant_contact": ["constant contact", "constantcontact"],
                "hubspot": ["hubspot", "hs-scripts"],
            },
            "crm": {
                "salesforce": ["salesforce", "pardot"],
                "hubspot_crm": ["hubspot"],
                "zoho": ["zoho"],
            },
            "booking_systems": {
                "opentable": ["opentable"],
                "resy": ["resy.com"],
                "toast": ["toasttab", "pos.toasttab"],
                "square": ["square.com", "squareup"],
                "acuity": ["acuityscheduling"],
                "calendly": ["calendly"],
                "zocdoc": ["zocdoc"],
                "vetstoria": ["vetstoria"],
            },
            "ecommerce": {
                "stripe": ["stripe.com", "js.stripe"],
                "paypal": ["paypal"],
            },
        }

        detected = {}
        for category, tools in tech_signals.items():
            detected[category] = {}
            for tool_name, keywords in tools.items():
                detected[category][tool_name] = any(kw in content_lower for kw in keywords)

        return {"status": "completed", "data": {"tech_stack": detected}, "sources": ["website_scrape"]}

    def _tier4(self, lead: Lead) -> dict:
        """Decision maker discovery via Hunter.io."""
        if not lead.website:
            return {"status": "skipped", "reason": "no website", "data": {}, "sources": []}

        try:
            domain = urlparse(lead.website).netloc.lstrip("www.")
        except Exception:
            domain = ""

        if not domain:
            return {"status": "skipped", "reason": "could not parse domain", "data": {}, "sources": []}

        decision_makers = []
        sources = []

        try:
            emails = self.hunter.domain_search(domain)
            for entry in emails:
                decision_makers.append({
                    "email": entry.get("value"),
                    "first_name": entry.get("first_name"),
                    "last_name": entry.get("last_name"),
                    "position": entry.get("position"),
                    "confidence": entry.get("confidence", 0),
                })
            if emails:
                sources.append("hunter_domain_search")
        except Exception as e:
            logger.warning(f"Tier 4 Hunter domain_search failed for {lead.company_name}: {e}")

        if not decision_makers:
            try:
                result = self.hunter.find_email(domain, "", "")
                if result.get("email"):
                    decision_makers.append({
                        "email": result["email"],
                        "first_name": None,
                        "last_name": None,
                        "position": None,
                        "confidence": result.get("confidence", 0),
                    })
                    sources.append("hunter_email_finder")
            except Exception as e:
                logger.warning(f"Tier 4 Hunter find_email failed for {lead.company_name}: {e}")

        return {
            "status": "completed",
            "data": {"decision_makers": decision_makers, "domain": domain},
            "sources": sources,
        }
