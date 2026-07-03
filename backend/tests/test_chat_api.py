"""API tests for POST /chat (#12).

Exercises the HTTP boundary that ties tenant resolution, the shared RAG
pipeline, and Answer/Citation persistence together.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.main import app
from app.models.answer import STATUS_NEEDS_REVIEW, Answer
from app.models.chunk import Chunk
from app.models.citation import Citation
from app.models.document import Document
from app.models.tenant_config import TenantConfig
from app.providers import get_embedding_provider


@pytest.fixture()
def client(db_session):
    """TestClient wired to the transactional db_session fixture."""

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(ENVIRONMENT="local", _env_file=None)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_settings, None)


def _add_config(db_session, *, tenant_id: int, config: dict) -> None:
    db_session.add(TenantConfig(tenant_id=tenant_id, config=config))
    db_session.commit()


def _seed_matching_document(db_session, *, tenant_id: int, query: str) -> Document:
    provider = get_embedding_provider()
    document = Document(
        tenant_id=tenant_id,
        title="請求処理FAQ",
        source_uri="https://example.test/billing",
        source_updated_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    document.chunks = [
        Chunk(
            tenant_id=tenant_id,
            content="請求処理は月末締めで、翌月5営業日以内に承認します。",
            embedding=provider.embed_query(query),
        )
    ]
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)
    return document


def test_post_chat_returns_answer_citations_status_and_persists_rows(
    client, db_session, make_tenant
) -> None:
    tenant = make_tenant("Shinonome Business Support")
    query = "請求処理の締め日はいつですか"
    document = _seed_matching_document(db_session, tenant_id=tenant.id, query=query)
    _add_config(
        db_session,
        tenant_id=tenant.id,
        config={
            "answer": {
                "modes": ["internal", "external"],
                "default_mode": "internal",
                "citation": "required",
                "show_source_metadata": True,
                "low_confidence_action": STATUS_NEEDS_REVIEW,
            },
            "pipeline": ["ground_check", "cite"],
        },
    )

    response = client.post(
        "/chat",
        headers={"X-Tenant-ID": str(tenant.id)},
        json={"query": query, "mode": "external"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert body["status"] == STATUS_NEEDS_REVIEW
    assert body["warnings"] == []
    assert body["citations"] == [
        {
            "chunk_id": document.chunks[0].id,
            "document_id": document.id,
            "title": "請求処理FAQ",
            "snippet": "請求処理は月末締めで、翌月5営業日以内に承認します。",
            "source_uri": "https://example.test/billing",
            "source_updated_at": "2026-01-02T00:00:00Z",
        }
    ]

    answers = db_session.query(Answer).all()
    citations = db_session.query(Citation).all()
    assert len(answers) == 1
    assert answers[0].tenant_id == tenant.id
    assert answers[0].query == query
    assert answers[0].mode == "external"
    assert answers[0].status == STATUS_NEEDS_REVIEW
    assert len(citations) == 1
    assert citations[0].answer_id == answers[0].id
    assert citations[0].document_id == document.id


def test_post_chat_rejects_mode_not_allowed_by_config(client, db_session, make_tenant) -> None:
    tenant = make_tenant()
    _add_config(
        db_session,
        tenant_id=tenant.id,
        config={"answer": {"modes": ["internal"], "default_mode": "internal"}, "pipeline": []},
    )

    response = client.post(
        "/chat",
        headers={"X-Tenant-ID": str(tenant.id)},
        json={"query": "hello", "mode": "external"},
    )

    assert response.status_code == 400
    assert "mode" in response.json()["detail"]


def test_post_chat_unknown_pipeline_step_returns_clear_message(
    client, db_session, make_tenant
) -> None:
    tenant = make_tenant()
    _add_config(db_session, tenant_id=tenant.id, config={"pipeline": ["not_registered"]})

    response = client.post(
        "/chat",
        headers={"X-Tenant-ID": str(tenant.id)},
        json={"query": "hello"},
    )

    assert response.status_code == 400
    assert "チャット設定" in response.json()["detail"]
