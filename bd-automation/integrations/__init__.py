from .groq_client import GroqClient
from .gemini_client import GeminiClient
from .resend_client import ResendClient
from .firecrawl_client import FirecrawlClient
from .hunter_client import HunterClient
from .yelp_client import YelpClient


class LLMRouter:
    """Routes LLM calls to Groq with automatic fallback to Gemini."""

    def __init__(self):
        self._groq = None
        self._gemini = None

    @property
    def groq(self) -> GroqClient:
        if self._groq is None:
            self._groq = GroqClient()
        return self._groq

    @property
    def gemini(self) -> GeminiClient:
        if self._gemini is None:
            self._gemini = GeminiClient()
        return self._gemini

    def complete(self, prompt: str, system: str = "", max_tokens: int = 1024, temperature: float = 0.7) -> str:
        try:
            return self.groq.complete(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Groq failed ({e}), falling back to Gemini")
            return self.gemini.complete(prompt, system=system, max_tokens=max_tokens, temperature=temperature)


__all__ = ["GroqClient", "GeminiClient", "ResendClient", "FirecrawlClient", "HunterClient", "LLMRouter", "YelpClient"]
