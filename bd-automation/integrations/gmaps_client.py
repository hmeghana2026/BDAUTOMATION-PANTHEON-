"""Google Maps Places API client for bulk business discovery."""
import os
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class GoogleMapsClient:
    def __init__(self):
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY must be set")
        import googlemaps
        self.client = googlemaps.Client(key=api_key)

    def search_businesses(
        self,
        business_type: str,
        location: str,
        radius_miles: float = 10.0,
        max_results: int = 50,
    ) -> list[dict]:
        """Search for businesses using Places API text search.

        Returns a list of raw place dicts with name, address, phone, website, rating.
        """
        radius_meters = int(radius_miles * 1609.34)

        try:
            geocode = self.client.geocode(location)
            if not geocode:
                logger.error(f"Could not geocode location: {location}")
                return []
            lat_lng = geocode[0]["geometry"]["location"]
        except Exception as e:
            logger.error(f"Geocoding failed for {location}: {e}")
            return []

        results = []
        query = f"{business_type} near {location}"
        page_token = None

        while len(results) < max_results:
            try:
                kwargs = {
                    "query": query,
                    "location": lat_lng,
                    "radius": radius_meters,
                }
                if page_token:
                    kwargs["page_token"] = page_token

                response = self.client.places(**kwargs)
                places = response.get("results", [])

                for place in places:
                    if len(results) >= max_results:
                        break

                    detail = self._get_place_detail(place.get("place_id", ""))
                    results.append({
                        "business_name": place.get("name", ""),
                        "address": place.get("formatted_address", ""),
                        "rating": place.get("rating"),
                        "phone": detail.get("formatted_phone_number"),
                        "website": detail.get("website"),
                        "place_id": place.get("place_id"),
                    })
                    time.sleep(0.5)

                page_token = response.get("next_page_token")
                if not page_token:
                    break
                time.sleep(2)

            except Exception as e:
                logger.error(f"Places search failed: {e}")
                break

        logger.info(f"Discovered {len(results)} businesses for '{business_type}' near '{location}'")
        return results

    def _get_place_detail(self, place_id: str) -> dict:
        """Fetch phone and website for a place."""
        if not place_id:
            return {}
        try:
            detail = self.client.place(
                place_id,
                fields=["formatted_phone_number", "website"],
            )
            return detail.get("result", {})
        except Exception as e:
            logger.warning(f"Place detail fetch failed for {place_id}: {e}")
            return {}
