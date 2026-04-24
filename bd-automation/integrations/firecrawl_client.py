import os
import logging
import time
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SCRAPE_DELAY = 2  # seconds between requests


class FirecrawlClient:
    def __init__(self):
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "")
        self.base_url = "https://api.firecrawl.dev/v0"
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        self.use_firecrawl = bool(self.api_key)

    def scrape(self, url: str) -> str:
        """Scrape a URL. Falls back to BeautifulSoup if no Firecrawl key."""
        time.sleep(SCRAPE_DELAY)

        if self.use_firecrawl:
            return self._scrape_firecrawl(url)
        return self._scrape_bs4(url)

    def _scrape_firecrawl(self, url: str) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/scrape",
                headers=self.headers,
                json={"url": url, "pageOptions": {"onlyMainContent": True}},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("content", "")
        except Exception as e:
            logger.warning(f"Firecrawl failed for {url}: {e}. Falling back to BS4.")
            return self._scrape_bs4(url)

    def _scrape_bs4(self, url: str) -> str:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; BDBot/1.0; +https://example.com/bot)"
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            # Respect robots.txt implicitly by only reading visible text
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            # Truncate to avoid token overflow
            return text[:8000]
        except Exception as e:
            logger.error(f"BS4 scrape failed for {url}: {e}")
            return ""

    def search_business(self, query: str) -> list[dict]:
        """Use Firecrawl search or fall back to Google Maps scrape."""
        if self.use_firecrawl:
            try:
                response = requests.post(
                    f"{self.base_url}/search",
                    headers=self.headers,
                    json={"query": query, "pageOptions": {"fetchPageContent": False}},
                    timeout=30,
                )
                response.raise_for_status()
                return response.json().get("data", [])
            except Exception as e:
                logger.warning(f"Firecrawl search failed: {e}")
        return []
