import os
import logging
import time
from groq import Groq

logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.1-70b-versatile"
MAX_RETRIES = 3


class GroqClient:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY must be set")
        self.client = Groq(api_key=api_key)

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1024, temperature: float = 0.7) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                if "rate_limit" in str(e).lower() and attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Groq rate limit hit, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise
        raise RuntimeError("Groq: max retries exceeded")
