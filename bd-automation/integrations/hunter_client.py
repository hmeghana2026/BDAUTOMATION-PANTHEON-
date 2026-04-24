import os
import logging
import requests

logger = logging.getLogger(__name__)

HUNTER_BASE = "https://api.hunter.io/v2"


class HunterClient:
    def __init__(self):
        self.api_key = os.getenv("HUNTER_API_KEY", "")
        if not self.api_key:
            logger.warning("HUNTER_API_KEY not set — email verification disabled")

    def find_email(self, domain: str, first_name: str = "", last_name: str = "") -> dict:
        """Find email for a person at a domain. Returns {email, confidence, verified}."""
        if not self.api_key:
            return {"email": None, "confidence": 0, "verified": False}
        try:
            params = {"domain": domain, "api_key": self.api_key}
            if first_name:
                params["first_name"] = first_name
            if last_name:
                params["last_name"] = last_name

            resp = requests.get(f"{HUNTER_BASE}/email-finder", params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return {
                "email": data.get("email"),
                "confidence": data.get("confidence", 0),
                "verified": data.get("verification", {}).get("result") == "deliverable",
            }
        except Exception as e:
            logger.error(f"Hunter find_email failed: {e}")
            return {"email": None, "confidence": 0, "verified": False}

    def verify_email(self, email: str) -> dict:
        """Verify whether an email is deliverable."""
        if not self.api_key:
            return {"result": "unknown", "score": 0}
        try:
            resp = requests.get(
                f"{HUNTER_BASE}/email-verifier",
                params={"email": email, "api_key": self.api_key},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            return {
                "result": data.get("result", "unknown"),
                "score": data.get("score", 0),
                "deliverable": data.get("result") == "deliverable",
            }
        except Exception as e:
            logger.error(f"Hunter verify_email failed: {e}")
            return {"result": "unknown", "score": 0, "deliverable": False}

    def domain_search(self, domain: str) -> list[dict]:
        """Find all emails associated with a domain."""
        if not self.api_key:
            return []
        try:
            resp = requests.get(
                f"{HUNTER_BASE}/domain-search",
                params={"domain": domain, "api_key": self.api_key, "limit": 5},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("data", {}).get("emails", [])
        except Exception as e:
            logger.error(f"Hunter domain_search failed: {e}")
            return []
