"""Gemini free-tier provider implementations.

Selected by the factory when ENVIRONMENT=local and GEMINI_API_KEY is set. The
SDK is imported lazily inside methods so that importing this module (and running
mock-only tests) never requires the SDK or a network. Callers must go through
the EmbeddingProvider / LLMProvider interfaces, not the SDK directly.
"""

from app.providers.base import EMBEDDING_DIM, EmbeddingProvider, LLMProvider

# text-embedding-004 returns 768-dim vectors, matching EMBEDDING_DIM so the mock
# and Gemini are interchangeable against the same pgvector column.
_EMBEDDING_MODEL = "models/text-embedding-004"
# Free-tier generation model.
_GENERATION_MODEL = "models/gemini-1.5-flash"


class GeminiError(RuntimeError):
    """Raised when the Gemini SDK fails (bad key, network, malformed response)."""


def _configure(api_key: str) -> "object":
    """Configure and return the genai module, raising GeminiError on failure."""
    try:
        import google.generativeai as genai
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise GeminiError("google-generativeai is not installed") from exc
    genai.configure(api_key=api_key)
    return genai


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Embeds text via Gemini text-embedding-004 (768-dim)."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise GeminiError("GEMINI_API_KEY is required for the Gemini provider")
        self._api_key = api_key

    def _embed(self, text: str, task_type: str) -> list[float]:
        genai = _configure(self._api_key)
        try:
            result = genai.embed_content(
                model=_EMBEDDING_MODEL,
                content=text,
                task_type=task_type,
            )
        except Exception as exc:  # SDK raises varied network/auth errors
            raise GeminiError(f"Gemini embedding request failed: {exc}") from exc
        embedding = result.get("embedding") if isinstance(result, dict) else None
        if not embedding or len(embedding) != EMBEDDING_DIM:
            raise GeminiError("Gemini returned an unexpected embedding shape")
        return list(embedding)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # task_type retrieval_document tunes the vector for indexed content.
        return [self._embed(text, "retrieval_document") for text in texts]

    def embed_query(self, text: str) -> list[float]:
        # task_type retrieval_query tunes the vector for search queries.
        return self._embed(text, "retrieval_query")


class GeminiLLMProvider(LLMProvider):
    """Generates text via a Gemini free-tier model."""

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise GeminiError("GEMINI_API_KEY is required for the Gemini provider")
        self._api_key = api_key

    def generate(self, prompt: str, **opts: object) -> str:
        genai = _configure(self._api_key)
        try:
            model = genai.GenerativeModel(_GENERATION_MODEL)
            response = model.generate_content(prompt)
        except Exception as exc:  # SDK raises varied network/auth errors
            raise GeminiError(f"Gemini generation request failed: {exc}") from exc
        text = getattr(response, "text", None)
        if not text:
            raise GeminiError("Gemini returned an empty generation response")
        return text
