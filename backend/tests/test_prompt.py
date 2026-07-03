"""Tests for app.rag.prompt.build_prompt (#9).

build_prompt is pure text assembly over in-memory Chunk objects and a config
dict -- no DB or provider access is exercised, so these tests construct Chunk
instances directly without persisting them (SQLAlchemy models can be
instantiated and have their attributes read without ever touching a session).
"""

from app.models.chunk import Chunk
from app.rag.prompt import build_prompt


def _chunk(content: str) -> Chunk:
    return Chunk(content=content)


def test_build_prompt_reflects_citation_required_vs_not() -> None:
    chunks = [_chunk("the office closes at 6pm")]
    query = "when does the office close"

    required_prompt = build_prompt({"answer": {"citation": "required"}}, chunks, query)
    optional_prompt = build_prompt({"answer": {"citation": "optional"}}, chunks, query)

    assert "must be grounded in the context" in required_prompt
    assert "must be grounded in the context" not in optional_prompt
    assert "citation is not mandatory" in optional_prompt


def test_build_prompt_reflects_external_vs_internal_mode() -> None:
    chunks = [_chunk("internal escalation contact: ext. 1234")]
    query = "who do I escalate to"

    external_prompt = build_prompt({"answer": {"default_mode": "external"}}, chunks, query)
    internal_prompt = build_prompt({"answer": {"default_mode": "internal"}}, chunks, query)

    assert "Mode: external" in external_prompt
    assert "do not reveal" in external_prompt
    assert "Mode: internal" in internal_prompt
    assert "do not reveal" not in internal_prompt


def test_build_prompt_reflects_category_policy_human_check() -> None:
    chunks = [_chunk("standard contract terms are net-30")]
    query = "can we change the contract terms"
    config = {
        "category_policies": {
            "contract": {"require_human_check": True},
        }
    }

    prompt = build_prompt(config, chunks, query)
    no_policy_prompt = build_prompt({}, chunks, query)

    assert "contract" in prompt
    assert "a human must confirm the answer" in prompt
    assert "a human must confirm the answer" not in no_policy_prompt


def test_build_prompt_reflects_category_tone() -> None:
    chunks = [_chunk("invoice due dates are the 1st of each month")]
    query = "when is my invoice due"
    config = {"category_policies": {"billing": {"tone": "formal"}}}

    prompt = build_prompt(config, chunks, query)

    assert "respond in a formal tone" in prompt


def test_build_prompt_notes_low_confidence_action() -> None:
    chunks = [_chunk("unrelated content")]
    query = "something not covered"

    flagged = build_prompt({"answer": {"low_confidence_action": "needs_review"}}, chunks, query)
    unflagged = build_prompt({"answer": {}}, chunks, query)

    assert "needs review" in flagged
    assert "needs review" not in unflagged


def test_build_prompt_notes_when_no_chunks_found() -> None:
    prompt = build_prompt({}, [], "anything")

    assert "no relevant context was found" in prompt


def test_build_prompt_includes_query_and_numbered_context() -> None:
    chunks = [_chunk("first passage"), _chunk("second passage")]

    prompt = build_prompt({}, chunks, "my question")

    assert "my question" in prompt
    assert "[1] first passage" in prompt
    assert "[2] second passage" in prompt


def test_build_prompt_tolerates_non_dict_answer_section() -> None:
    # tenant_config.config is unvalidated JSONB -- a mis-seeded row like this
    # (answer should be a dict, e.g. {"default_mode": "external"}) must not
    # raise a raw AttributeError; it should fall back to the default policy.
    chunks = [_chunk("some content")]

    prompt = build_prompt({"answer": "external"}, chunks, "a question")

    assert "Mode: internal" in prompt  # falls back to the documented default


def test_build_prompt_tolerates_non_dict_category_policies() -> None:
    # Same defensive-shape guarantee for category_policies: a list instead of
    # a dict keyed by category must not raise, and contributes no category
    # instructions since it can't be interpreted as one.
    chunks = [_chunk("some content")]

    prompt = build_prompt({"category_policies": ["contract"]}, chunks, "a question")

    assert "a human must confirm the answer" not in prompt
    assert "respond in a" not in prompt
