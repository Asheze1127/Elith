"""Provider interfaces for LLM generation and text embedding.

Callers (RAG pipeline, ingestion) must depend only on these abstractions and
never on a concrete SDK. Concrete providers (Gemini, mock) are selected by the
factory in ``app.providers`` based on environment config.
"""

from abc import ABC, abstractmethod

# Embedding dimensionality shared by every provider. Chosen to match Gemini's
# text-embedding-004 native output (768), so the mock produces vectors of the
# same shape and a pgvector column sized for it works with either provider.
EMBEDDING_DIM = 768


class EmbeddingProvider(ABC):
    """Turns text into fixed-size vectors for similarity search."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of documents; returns one vector per input text."""
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string; returns one vector."""
        raise NotImplementedError


class LLMProvider(ABC):
    """Generates answer text from a prompt."""

    @abstractmethod
    def generate(self, prompt: str, **opts: object) -> str:
        """Generate a completion for ``prompt``; extra opts are provider-specific."""
        raise NotImplementedError
