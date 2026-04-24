import os
import logging
import time
import google.generativeai as genai

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-1.5-flash"
MAX_RETRIES = 3


class GeminiClient:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY must be set")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(GEMINI_MODEL)

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1024, temperature: float = 0.7) -> str:
        full_prompt = f"{system}\n\n{prompt}" if system else prompt

        for attempt in range(MAX_RETRIES):
            try:
                response = self.model.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=temperature,
                    ),
                )
                return response.text.strip()
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning(f"Gemini error ({e}), retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise
        raise RuntimeError("Gemini: max retries exceeded")
