"""API tests for /feedback and /review improvement candidates."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.main import app
from app.models.answer import STATUS_ANSWERED, STATUS_NO_DATA, Answer
from app.models.feedback import RATING_BAD, RATING_GOOD, Feedback
from app.models.tenant_config import TenantConfig


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: Settings(ENVIRONMENT="local", _env_file=None)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_settings, None)


def _add_config(db_session, *, tenant_id: int) -> None:
    db_session.add(
        TenantConfig(
            tenant_id=tenant_id,
            config={
                "feedback": {
                    "enabled": True,
                    "reason_categories": ["古い根拠", "誤った引用"],
                }
            },
        )
    )
    db_session.commit()


def _add_answer(db_session, *, tenant_id: int, status: str = STATUS_ANSWERED) -> Answer:
    answer = Answer(
        tenant_id=tenant_id,
        query="請求書の再発行はできますか",
        body="請求書の再発行は可能です。",
        status=status,
        mode="internal",
    )
    db_session.add(answer)
    db_session.commit()
    db_session.refresh(answer)
    return answer


def test_post_feedback_saves_good_rating(client, db_session, make_tenant) -> None:
    tenant = make_tenant()
    _add_config(db_session, tenant_id=tenant.id)
    answer = _add_answer(db_session, tenant_id=tenant.id)

    response = client.post(
        "/feedback",
        headers={"X-Tenant-ID": str(tenant.id)},
        json={"answer_id": answer.id, "rating": RATING_GOOD},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["answer_id"] == answer.id
    assert body["rating"] == RATING_GOOD
    feedback = (
        db_session.query(Feedback)
        .filter(Feedback.tenant_id == tenant.id, Feedback.answer_id == answer.id)
        .one()
    )
    assert feedback.tenant_id == tenant.id
    assert feedback.answer_id == answer.id


def test_post_feedback_rejects_cross_tenant_answer(client, db_session, make_tenant) -> None:
    tenant_a = make_tenant("A")
    tenant_b = make_tenant("B")
    _add_config(db_session, tenant_id=tenant_a.id)
    answer_b = _add_answer(db_session, tenant_id=tenant_b.id)

    response = client.post(
        "/feedback",
        headers={"X-Tenant-ID": str(tenant_a.id)},
        json={"answer_id": answer_b.id, "rating": RATING_GOOD},
    )

    assert response.status_code == 404


def test_post_feedback_validates_bad_reason_category(client, db_session, make_tenant) -> None:
    tenant = make_tenant()
    _add_config(db_session, tenant_id=tenant.id)
    answer = _add_answer(db_session, tenant_id=tenant.id)

    response = client.post(
        "/feedback",
        headers={"X-Tenant-ID": str(tenant.id)},
        json={
            "answer_id": answer.id,
            "rating": RATING_BAD,
            "reason_category": "カテゴリ外",
        },
    )

    assert response.status_code == 400
    assert "reason_category" in response.json()["detail"]


def test_get_review_returns_bad_feedback_and_no_data_answers(
    client, db_session, make_tenant
) -> None:
    tenant = make_tenant()
    _add_config(db_session, tenant_id=tenant.id)
    bad_answer = _add_answer(db_session, tenant_id=tenant.id)
    no_data_answer = _add_answer(db_session, tenant_id=tenant.id, status=STATUS_NO_DATA)
    good_answer = _add_answer(db_session, tenant_id=tenant.id)
    db_session.add(
        Feedback(
            tenant_id=tenant.id,
            answer_id=bad_answer.id,
            rating=RATING_BAD,
            reason_category="古い根拠",
            comment="旧資料を参照している",
        )
    )
    db_session.commit()

    response = client.get("/review", headers={"X-Tenant-ID": str(tenant.id)})

    assert response.status_code == 200
    items = response.json()
    answer_ids = {item["answer_id"] for item in items}
    assert bad_answer.id in answer_ids
    assert no_data_answer.id in answer_ids
    assert good_answer.id not in answer_ids
    bad_item = next(item for item in items if item["answer_id"] == bad_answer.id)
    assert bad_item["feedback"][0]["reason_category"] == "古い根拠"
