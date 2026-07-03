"""Tenant-scoped feedback persistence and review candidate listing."""

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.models.answer import STATUS_ANSWERED, Answer
from app.models.feedback import RATING_BAD, Feedback


class AnswerNotFoundError(Exception):
    """Raised when an answer is absent or belongs to another tenant."""


def create_feedback(
    db: Session,
    *,
    tenant_id: int,
    answer_id: int,
    rating: str,
    reason_category: str | None,
    comment: str | None,
) -> Feedback:
    """Persist feedback after proving the answer belongs to ``tenant_id``."""
    answer = db.get(Answer, answer_id)
    if answer is None or answer.tenant_id != tenant_id:
        raise AnswerNotFoundError(f"answer '{answer_id}' does not exist for tenant '{tenant_id}'")

    feedback = Feedback(
        tenant_id=tenant_id,
        answer_id=answer_id,
        rating=rating,
        reason_category=reason_category,
        comment=comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def list_review_candidates(db: Session, *, tenant_id: int) -> list[Answer]:
    """Return answers that need improvement: bad feedback or non-answered status."""
    stmt = (
        select(Answer)
        .where(Answer.tenant_id == tenant_id)
        .options(selectinload(Answer.feedback))
        .order_by(desc(Answer.created_at), desc(Answer.id))
    )
    answers = db.scalars(stmt).all()
    return [
        answer
        for answer in answers
        if answer.status != STATUS_ANSWERED
        or any(feedback.rating == RATING_BAD for feedback in answer.feedback)
    ]
