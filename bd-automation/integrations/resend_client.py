import os
import logging
import resend

logger = logging.getLogger(__name__)

DAILY_LIMIT = 50


class ResendClient:
    def __init__(self):
        api_key = os.getenv("RESEND_API_KEY")
        if not api_key:
            raise ValueError("RESEND_API_KEY must be set")
        resend.api_key = api_key
        self.from_email = os.getenv("FROM_EMAIL", "outreach@yourdomain.com")
        self.from_name = os.getenv("FROM_NAME", "Your Name")

    def send_email(self, to: str, subject: str, body: str, reply_to: str = None) -> dict:
        params = {
            "from": f"{self.from_name} <{self.from_email}>",
            "to": [to],
            "subject": subject,
            "text": body,
        }
        if reply_to:
            params["reply_to"] = reply_to

        try:
            response = resend.Emails.send(params)
            logger.info(f"Email sent to {to}: id={response.get('id')}")
            return {"success": True, "id": response.get("id")}
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return {"success": False, "error": str(e)}

    def send_batch(self, emails: list[dict]) -> list[dict]:
        """Send up to DAILY_LIMIT emails. Each dict: {to, subject, body}."""
        results = []
        for i, email in enumerate(emails[:DAILY_LIMIT]):
            result = self.send_email(
                to=email["to"],
                subject=email["subject"],
                body=email["body"],
                reply_to=email.get("reply_to"),
            )
            results.append({**email, **result})
        return results
