"""Provider package: interfaces and the factory that selects an implementation.

Selection is driven purely by environment config (app-wide startup condition),
never by tenant_config. Rule: ENVIRONMENT=local AND GEMINI_API_KEY set -> Gemini
free API; otherwise -> deterministic mock (no network, no key required).
"""

from app.core.config import Settings, get_settings
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.mock import MockEmbeddingProvider, MockLLMProvider


def _use_gemini(settings: Settings) -> bool:
    """True only when local environment has a Gemini key configured."""
    # strip() so a whitespace-only key ('   ') falls back to mock instead of
    # picking Gemini and failing later with an opaque auth error; case-insensitive
    # ENVIRONMENT compare so 'LOCAL'/'Local' behave like 'local'.
    return settings.ENVIRONMENT.strip().lower() == "local" and bool(settings.GEMINI_API_KEY.strip())


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Return the embedding provider selected by environment config."""
    settings = settings or get_settings()
    if _use_gemini(settings):
        # Imported lazily so mock-only environments never load the SDK.
        from app.providers.gemini import GeminiEmbeddingProvider

        return GeminiEmbeddingProvider(settings.GEMINI_API_KEY)
    return MockEmbeddingProvider()


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Return the LLM provider selected by environment config."""
    settings = settings or get_settings()
    if _use_gemini(settings):
        # Imported lazily so mock-only environments never load the SDK.
        from app.providers.gemini import GeminiLLMProvider

        return GeminiLLMProvider(settings.GEMINI_API_KEY)
    return MockLLMProvider()


__all__ = [
    "EmbeddingProvider",
    "LLMProvider",
    "get_embedding_provider",
    "get_llm_provider",
]
