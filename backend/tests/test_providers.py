"""Tests for the LLM/Embedding provider abstraction and factory selection.

No real network or API key is used: the mock path is network-free by design and
the Gemini path is exercised with the SDK fully mocked.
"""

import sys
import types

import pytest

from app.core.config import Settings
from app.providers import get_embedding_provider, get_llm_provider
from app.providers.base import EMBEDDING_DIM
from app.providers.gemini import (
    GeminiEmbeddingProvider,
    GeminiError,
    GeminiLLMProvider,
)
from app.providers.mock import MockEmbeddingProvider, MockLLMProvider


def _settings(environment: str, gemini_api_key: str) -> Settings:
    """Build a Settings instance for a given env/key combo without reading .env."""
    return Settings(
        ENVIRONMENT=environment,
        GEMINI_API_KEY=gemini_api_key,
        _env_file=None,
    )


# --- factory selection ---------------------------------------------------


def test_factory_falls_back_to_mock_without_key() -> None:
    settings = _settings("local", "")
    assert isinstance(get_embedding_provider(settings), MockEmbeddingProvider)
    assert isinstance(get_llm_provider(settings), MockLLMProvider)


def test_factory_selects_gemini_when_local_and_key_present() -> None:
    settings = _settings("local", "fake-key")
    assert isinstance(get_embedding_provider(settings), GeminiEmbeddingProvider)
    assert isinstance(get_llm_provider(settings), GeminiLLMProvider)


def test_factory_uses_mock_when_not_local_even_with_key() -> None:
    settings = _settings("production", "fake-key")
    assert isinstance(get_embedding_provider(settings), MockEmbeddingProvider)
    assert isinstance(get_llm_provider(settings), MockLLMProvider)


# --- mock behavior -------------------------------------------------------


def test_mock_embed_query_dimension_and_determinism() -> None:
    provider = MockEmbeddingProvider()
    first = provider.embed_query("hello")
    second = provider.embed_query("hello")
    assert len(first) == EMBEDDING_DIM
    assert first == second  # same input -> same output
    assert first != provider.embed_query("world")  # different input -> different output


def test_mock_embed_documents_dimension_and_determinism() -> None:
    provider = MockEmbeddingProvider()
    texts = ["alpha", "beta", "gamma"]
    first = provider.embed_documents(texts)
    second = provider.embed_documents(texts)
    assert len(first) == len(texts)
    assert all(len(vec) == EMBEDDING_DIM for vec in first)
    assert first == second


def test_mock_embed_values_in_unit_range() -> None:
    provider = MockEmbeddingProvider()
    vec = provider.embed_query("range-check")
    assert all(0.0 <= value < 1.0 for value in vec)


def test_mock_generate_returns_citation_shaped_text() -> None:
    provider = MockLLMProvider()
    answer = provider.generate("any prompt")
    assert isinstance(answer, str)
    assert answer  # non-empty
    assert "[1]" in answer  # citation-shaped so downstream steps can parse it


# --- gemini path (SDK mocked, no network) --------------------------------


def _install_fake_genai(monkeypatch: pytest.MonkeyPatch, module: types.ModuleType) -> None:
    """Register a fake google.generativeai module for lazy import inside providers."""
    google_pkg = types.ModuleType("google")
    google_pkg.__path__ = []  # mark as package so submodule import resolves
    monkeypatch.setitem(sys.modules, "google", google_pkg)
    monkeypatch.setitem(sys.modules, "google.generativeai", module)


def test_gemini_embedding_uses_sdk_and_returns_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    fake = types.ModuleType("google.generativeai")

    def configure(api_key: str) -> None:
        calls.append({"configure": api_key})

    def embed_content(model: str, content: str, task_type: str) -> dict:
        calls.append({"model": model, "content": content, "task_type": task_type})
        return {"embedding": [0.0] * EMBEDDING_DIM}

    fake.configure = configure
    fake.embed_content = embed_content
    _install_fake_genai(monkeypatch, fake)

    provider = GeminiEmbeddingProvider("fake-key")
    query_vec = provider.embed_query("q")
    doc_vecs = provider.embed_documents(["d1", "d2"])

    assert len(query_vec) == EMBEDDING_DIM
    assert len(doc_vecs) == 2
    assert all(len(v) == EMBEDDING_DIM for v in doc_vecs)
    # query vs document use distinct task types tuned for their role
    task_types = [c["task_type"] for c in calls if "task_type" in c]
    assert "retrieval_query" in task_types
    assert "retrieval_document" in task_types


def test_gemini_embedding_rejects_wrong_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("google.generativeai")
    fake.configure = lambda api_key: None
    fake.embed_content = lambda model, content, task_type: {"embedding": [0.0] * 10}
    _install_fake_genai(monkeypatch, fake)

    provider = GeminiEmbeddingProvider("fake-key")
    with pytest.raises(GeminiError):
        provider.embed_query("q")


def test_gemini_embedding_wraps_sdk_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("google.generativeai")
    fake.configure = lambda api_key: None

    def boom(model: str, content: str, task_type: str) -> dict:
        raise RuntimeError("network down")

    fake.embed_content = boom
    _install_fake_genai(monkeypatch, fake)

    provider = GeminiEmbeddingProvider("fake-key")
    with pytest.raises(GeminiError):
        provider.embed_query("q")


def test_gemini_generate_uses_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("google.generativeai")
    fake.configure = lambda api_key: None

    class FakeResponse:
        text = "generated answer"

    class FakeModel:
        def __init__(self, model: str) -> None:
            self.model = model

        def generate_content(self, prompt: str) -> FakeResponse:
            return FakeResponse()

    fake.GenerativeModel = FakeModel
    _install_fake_genai(monkeypatch, fake)

    provider = GeminiLLMProvider("fake-key")
    assert provider.generate("prompt") == "generated answer"


def test_gemini_generate_wraps_sdk_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("google.generativeai")
    fake.configure = lambda api_key: None

    class FakeModel:
        def __init__(self, model: str) -> None:
            pass

        def generate_content(self, prompt: str):
            raise RuntimeError("timeout")

    fake.GenerativeModel = FakeModel
    _install_fake_genai(monkeypatch, fake)

    provider = GeminiLLMProvider("fake-key")
    with pytest.raises(GeminiError):
        provider.generate("prompt")


def test_gemini_provider_requires_key() -> None:
    with pytest.raises(GeminiError):
        GeminiEmbeddingProvider("")
    with pytest.raises(GeminiError):
        GeminiLLMProvider("")
