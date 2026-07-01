"""Deterministic, network-free provider implementations.

Used when ENVIRONMENT is not ``local`` or when GEMINI_API_KEY is absent, and in
tests. Embeddings are derived deterministically from the input so the same text
always yields the same vector (stable retrieval in local/CI without a key).
"""

import hashlib

from app.providers.base import EMBEDDING_DIM, EmbeddingProvider, LLMProvider


def _hash_embedding(text: str) -> list[float]:
    """Map text to a deterministic EMBEDDING_DIM-length unit-scaled vector.

    We hash the text and expand the digest into enough bytes to fill every
    dimension, then scale each byte to [0, 1). This is deterministic (same input
    -> same output) and needs no network, which is all the mock must guarantee;
    it carries no real semantic meaning.
    """
    dims: list[float] = []
    counter = 0
    while len(dims) < EMBEDDING_DIM:
        # Salt the hash with a counter so we can generate arbitrarily many bytes
        # while staying fully deterministic for a given input text.
        digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
        for byte in digest:
            if len(dims) >= EMBEDDING_DIM:
                break
            # 256 = number of distinct byte values; scales each byte into [0, 1).
            dims.append(byte / 256)
        counter += 1
    return dims


class MockEmbeddingProvider(EmbeddingProvider):
    """Hash-based deterministic embeddings; no network access."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [_hash_embedding(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return _hash_embedding(text)


class MockLLMProvider(LLMProvider):
    """Returns a fixed, citation-shaped dummy answer; no network access."""

    def generate(self, prompt: str, **opts: object) -> str:
        # Citation-shaped so downstream cite/ground_check steps have something to
        # parse without a real model. Not semantically meaningful.
        return "これはモック応答です。実際のLLMは呼び出していません。根拠: [1] mock-source"
