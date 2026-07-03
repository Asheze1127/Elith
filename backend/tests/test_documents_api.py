"""API tests for POST /documents and GET /documents.

Exercises the DoD for #7 at the HTTP layer: ingesting the sample document
stores chunks and is reflected in the listing, a second tenant's documents
never leak into another tenant's listing, and invalid input / unknown tenant
return clear 4xx responses rather than a 500.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_DOC_PATH = Path(__file__).resolve().parents[1] / "sample_data" / "shinonome_faq.txt"


def test_post_documents_ingests_sample_and_returns_chunk_count(make_tenant) -> None:
    tenant = make_tenant("Shinonome Business Support")
    content = SAMPLE_DOC_PATH.read_text(encoding="utf-8")

    response = client.post(
        "/documents",
        json={"tenant_id": tenant.id, "title": "Shinonome FAQ", "content": content},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["tenant_id"] == tenant.id
    assert body["title"] == "Shinonome FAQ"
    assert body["chunk_count"] > 0


def test_get_documents_returns_ingested_document(make_tenant) -> None:
    tenant = make_tenant()
    client.post(
        "/documents", json={"tenant_id": tenant.id, "title": "Doc A", "content": "hello world"}
    )

    response = client.get("/documents", params={"tenant_id": tenant.id})

    assert response.status_code == 200
    titles = [doc["title"] for doc in response.json()]
    assert "Doc A" in titles


def test_get_documents_does_not_leak_other_tenants(make_tenant) -> None:
    tenant_a = make_tenant("Tenant A")
    tenant_b = make_tenant("Tenant B")

    client.post(
        "/documents", json={"tenant_id": tenant_a.id, "title": "A doc", "content": "hello from A"}
    )
    client.post(
        "/documents", json={"tenant_id": tenant_b.id, "title": "B doc", "content": "hello from B"}
    )

    response = client.get("/documents", params={"tenant_id": tenant_a.id})

    assert response.status_code == 200
    titles = [doc["title"] for doc in response.json()]
    assert "A doc" in titles
    assert "B doc" not in titles


def test_post_documents_rejects_empty_content_with_clear_message(make_tenant) -> None:
    tenant = make_tenant()

    response = client.post(
        "/documents", json={"tenant_id": tenant.id, "title": "Empty", "content": "   "}
    )

    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()


def test_post_documents_rejects_blank_title(make_tenant) -> None:
    tenant = make_tenant()

    response = client.post(
        "/documents", json={"tenant_id": tenant.id, "title": "", "content": "hello"}
    )

    assert response.status_code == 422


def test_post_documents_unknown_tenant_returns_404() -> None:
    response = client.post(
        "/documents", json={"tenant_id": 999_999, "title": "X", "content": "hello"}
    )

    assert response.status_code == 404
    assert "999999" in response.json()["detail"] or "999_999" in response.json()["detail"]
