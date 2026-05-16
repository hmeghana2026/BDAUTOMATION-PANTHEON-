"""V2: SMS message drafting agent with strict 160-char limit."""
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SMS_MAX_CHARS = 160


class SMSDrafterAgent:
    def __init__(self):
        self._templates = self._load_templates()

    def _load_templates(self) -> dict:
        """Load SMS templates from JSON file."""
        try:
            template_path = os.path.join(
                os.path.dirname(__file__), "..", "templates", "sms_templates.json"
            )
            with open(template_path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load SMS templates: {e}")
            return {}

    def draft_sms(
        self,
        business_name: str,
        vertical: str,
        phone_number: str,
        touch_number: int = 1,
    ) -> Optional[str]:
        """Draft a personalized SMS message under 160 chars.

        No links — carrier filters flag them.
        Includes a reply instruction.
        """
        try:
            from integrations.groq_client import GroqClient
            groq = GroqClient()
            message = self._draft_with_llm(groq, business_name, vertical, touch_number)
        except Exception as e:
            logger.warning(f"Groq draft failed, using template: {e}")
            message = self._draft_from_template(business_name, vertical, touch_number)

        if not message:
            message = self._draft_from_template(business_name, vertical, touch_number)

        return self._enforce_limit(message)

    def _draft_with_llm(self, groq, business_name: str, vertical: str, touch_number: int) -> str:
        """Use Groq LLM to generate a personalized SMS."""
        prompt = (
            f"Write a {touch_number == 1 and 'first outreach' or 'follow-up'} SMS to {business_name}, "
            f"a {vertical} business. Rules: HARD MAX 155 characters, no links, no emojis, "
            f"casual friendly tone, end with 'Reply YES if interested'. "
            f"Output only the SMS text, nothing else."
        )
        response = groq.complete(prompt, max_tokens=80)
        return response.strip() if response else ""

    def _draft_from_template(self, business_name: str, vertical: str, touch_number: int) -> str:
        """Fall back to JSON templates."""
        templates = self._templates.get(vertical, self._templates.get("default", []))
        if not templates:
            return (
                f"Hi {business_name}! We help {vertical}s get more clients online. "
                f"Quick call this week? Reply YES if interested."
            )
        idx = min(touch_number - 1, len(templates) - 1)
        template = templates[idx]
        return template.replace("{business_name}", business_name).replace("{vertical}", vertical)

    @staticmethod
    def _enforce_limit(message: str) -> str:
        """Truncate to 160 chars, preserving the reply instruction if possible."""
        if len(message) <= SMS_MAX_CHARS:
            return message
        # Truncate and append minimal reply instruction
        reply_suffix = " Reply YES."
        truncated = message[: SMS_MAX_CHARS - len(reply_suffix)].rstrip()
        return truncated + reply_suffix
