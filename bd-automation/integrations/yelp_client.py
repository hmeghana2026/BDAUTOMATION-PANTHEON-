"""Yelp Fusion API client for business search and review retrieval."""
import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class YelpClient:
    BASE_URL = "https://api.yelp.com/v3"

    def __init__(self):
        self.api_key = os.getenv("YELP_API_KEY", "")
        if not self.api_key:
            logger.warning("YELP_API_KEY not set — Yelp integration disabled")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def search_business(self, name: str, location: str) -> Optional[dict]:
        """Search for a business by name and location. Returns first match or None."""
        if not self.api_key:
            return None
        try:
            params = {
                "term": name,
                "location": location,
                "limit": 1,
            }
            resp = self.session.get(
                f"{self.BASE_URL}/businesses/search",
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            businesses = resp.json().get("businesses", [])
            if not businesses:
                logger.info(f"No Yelp results for '{name}' in '{location}'")
                return None

            biz = businesses[0]
            location_data = biz.get("location", {})
            return {
                "id": biz.get("id"),
                "name": biz.get("name"),
                "url": biz.get("url"),
                "rating": biz.get("rating"),
                "review_count": biz.get("review_count"),
                "phone": biz.get("phone"),
                "location": {
                    "address1": location_data.get("address1"),
                    "city": location_data.get("city"),
                    "state": location_data.get("state"),
                    "zip_code": location_data.get("zip_code"),
                    "display_address": location_data.get("display_address", []),
                },
                "categories": [
                    {"alias": c.get("alias"), "title": c.get("title")}
                    for c in biz.get("categories", [])
                ],
                "photos": biz.get("photos", []),
            }
        except Exception as e:
            logger.warning(f"Yelp search_business failed for '{name}': {e}")
            return None

    def get_reviews(self, business_id: str) -> list:
        """Get reviews for a business by Yelp business ID."""
        if not self.api_key or not business_id:
            return []
        try:
            resp = self.session.get(
                f"{self.BASE_URL}/businesses/{business_id}/reviews",
                timeout=10,
            )
            resp.raise_for_status()
            reviews = resp.json().get("reviews", [])
            return [
                {
                    "text": r.get("text", ""),
                    "time_created": r.get("time_created", ""),
                    "rating": r.get("rating"),
                    "user": r.get("user", {}).get("name", ""),
                }
                for r in reviews
            ]
        except Exception as e:
            logger.warning(f"Yelp get_reviews failed for business_id '{business_id}': {e}")
            return []
