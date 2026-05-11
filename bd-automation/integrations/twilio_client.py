"""Twilio SMS client for outreach messaging."""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SMS_DAILY_CAP = 50


class TwilioClient:
    def __init__(self):
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = os.getenv("TWILIO_PHONE_NUMBER")
        if not account_sid or not auth_token or not self.from_number:
            raise ValueError("TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER must be set")
        from twilio.rest import Client
        self.client = Client(account_sid, auth_token)

    def send_sms(self, to_number: str, body: str) -> Optional[str]:
        """Send a single SMS. Returns Twilio SID on success, None on failure.

        Enforces 160-char limit and E.164 phone format.
        """
        if len(body) > 160:
            logger.warning(f"SMS body truncated from {len(body)} to 160 chars")
            body = body[:160]

        to_number = self._normalize_phone(to_number)
        if not to_number:
            logger.error("Invalid phone number — cannot send SMS")
            return None

        try:
            message = self.client.messages.create(
                body=body,
                from_=self.from_number,
                to=to_number,
            )
            logger.info(f"SMS sent to {to_number} — SID: {message.sid}")
            return message.sid
        except Exception as e:
            logger.error(f"Twilio send failed to {to_number}: {e}")
            return None

    def get_message_status(self, twilio_sid: str) -> Optional[str]:
        """Fetch delivery status for a message SID."""
        try:
            message = self.client.messages(twilio_sid).fetch()
            return message.status
        except Exception as e:
            logger.error(f"Failed to fetch status for {twilio_sid}: {e}")
            return None

    @staticmethod
    def _normalize_phone(phone: str) -> Optional[str]:
        """Normalize to E.164 format. Returns None if not parseable."""
        import re
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        if phone.startswith("+") and len(digits) >= 10:
            return f"+{digits}"
        return None
