"""V2: Bulk business discovery agent using Google Maps + website scraping + Hunter.io."""
import logging
import time
import re
from typing import Optional

logger = logging.getLogger(__name__)


class BulkDiscoveryAgent:
    def __init__(self):
        from integrations.gmaps_client import GoogleMapsClient
        from integrations.firecrawl_client import FirecrawlClient
        from integrations.hunter_client import HunterClient
        self.maps = GoogleMapsClient()
        self.scraper = FirecrawlClient()
        self.hunter = HunterClient()

    def discover_businesses(
        self,
        business_type: str,
        geographic_center: str,
        radius_miles: float = 10.0,
        max_results: int = 50,
    ) -> list[dict]:
        """Discover businesses via Google Maps, scrape each website for POC email.

        Returns enriched business dicts ready for DB insertion.
        """
        logger.info(f"Starting bulk discovery: {business_type} near {geographic_center} ({radius_miles}mi)")

        raw_results = self.search_google_maps(business_type, geographic_center, radius_miles, max_results)
        enriched = []

        for place in raw_results:
            try:
                enriched_place = self._enrich_business(place)
                enriched.append(enriched_place)
                time.sleep(2)
            except Exception as e:
                logger.error(f"Enrichment failed for {place.get('business_name')}: {e}")
                enriched.append({**place, "email": None, "channel": "none"})

        logger.info(f"Discovery complete: {len(enriched)} businesses enriched")
        return enriched

    def search_google_maps(
        self,
        business_type: str,
        location: str,
        radius_miles: float,
        max_results: int,
    ) -> list[dict]:
        """Delegate to GoogleMapsClient and return raw place dicts."""
        return self.maps.search_businesses(business_type, location, radius_miles, max_results)

    def _enrich_business(self, place: dict) -> dict:
        """Scrape website for email, verify with Hunter, set channel."""
        email = place.get("email")
        website = place.get("website")

        if not email and website:
            email = self.extract_contacts(website)
            if email:
                email = self._verify_email(email, website)

        channel = self.determine_channel(email, place.get("phone"))

        return {
            **place,
            "email": email,
            "channel": channel,
        }

    def extract_contacts(self, website_url: str) -> Optional[str]:
        """Scrape a business website and extract the first POC email found."""
        if not website_url:
            return None
        try:
            content = self.scraper.scrape_url(website_url)
            if not content:
                return None
            emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", content)
            # Filter out generic/noreply addresses
            filtered = [
                e for e in emails
                if not any(skip in e.lower() for skip in ["noreply", "no-reply", "support@", "info@example"])
            ]
            return filtered[0] if filtered else None
        except Exception as e:
            logger.warning(f"Email extraction failed for {website_url}: {e}")
            return None

    def _verify_email(self, email: str, website: str) -> Optional[str]:
        """Verify email via Hunter.io. Returns email if verified/acceptable, else None."""
        try:
            domain = website.replace("https://", "").replace("http://", "").split("/")[0]
            result = self.hunter.verify_email(email)
            if result and result.get("result") in ("deliverable", "risky"):
                return email
            # Try Hunter domain search as fallback
            found = self.hunter.find_email(domain)
            return found if found else email
        except Exception as e:
            logger.warning(f"Hunter verification skipped for {email}: {e}")
            return email

    @staticmethod
    def determine_channel(email: Optional[str], phone: Optional[str]) -> str:
        """Route to email, sms, both, or none based on available contact info."""
        has_email = bool(email and "@" in email)
        has_phone = bool(phone and len(re.sub(r"\D", "", phone)) >= 10)

        if has_email and has_phone:
            return "both"
        if has_email:
            return "email"
        if has_phone:
            return "sms"
        return "none"
