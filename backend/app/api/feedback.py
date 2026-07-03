"""Feedback and review endpoints for answer-quality operations (#21)."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.deps.tenant import get_tenant_config
from app.models.answer import Answer
from app.models.feedback import RATING_BAD, RATING_GOOD, Feedback
from app.models.tenant_config import TenantConfig
from app.repository.feedback import AnswerNotFoundError, create_feedback, list_review_candidates

router = APIRouter(tags=["feedback"])


class FeedbackRequest(BaseModel):
    answer_id: int
    rating: str = Field(min_length=1)
    reason_category: str | None = None
    comment: str | None = Field(default=None, max_length=2_000)


class FeedbackResponse(BaseModel):
    id: int
    answer_id: int
    rating: str
    reason_category: str | None
    comment: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, feedback: Feedback) -> "FeedbackResponse":
        return cls(
            id=feedback.id,
            answer_id=feedback.answer_id,
            rating=feedback.rating,
            reason_category=feedback.reason_category,
            comment=feedback.comment,
            created_at=feedback.created_at,
        )


class ReviewFeedbackResponse(BaseModel):
    id: int
    answer_id: int
    rating: str
    reason_category: str | None
    comment: str | None
    created_at: datetime

    @classmethod
    def from_model(cls, feedback: Feedback) -> "ReviewFeedbackResponse":
        return cls(
            id=feedback.id,
            answer_id=feedback.answer_id,
            rating=feedback.rating,
            reason_category=feedback.reason_category,
            comment=feedback.comment,
            created_at=feedback.created_at,
        )


class ReviewItemResponse(BaseModel):
    answer_id: int
    query: str
    answer: str
    status: str
    mode: str | None
    created_at: datetime
    feedback: list[ReviewFeedbackResponse]

    @classmethod
    def from_answer(cls, answer: Answer) -> "ReviewItemResponse":
        return cls(
            answer_id=answer.id,
            query=answer.query,
            answer=answer.body,
            status=answer.status,
            mode=answer.mode,
            created_at=answer.created_at,
            feedback=[
                ReviewFeedbackResponse.from_model(feedback)
                for feedback in answer.feedback
                if feedback.rating == RATING_BAD
            ],
        )


@router.post("/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def post_feedback(
    payload: FeedbackRequest,
    db: Session = Depends(get_db),
    tenant_config: TenantConfig = Depends(get_tenant_config),
) -> FeedbackResponse:
    """Persist good/bad feedback for one tenant-scoped answer."""
    _validate_feedback_payload(payload, tenant_config.config)
    try:
        feedback = create_feedback(
            db,
            tenant_id=tenant_config.tenant_id,
            answer_id=payload.answer_id,
            rating=payload.rating,
            reason_category=payload.reason_category,
            comment=payload.comment,
        )
    except AnswerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return FeedbackResponse.from_model(feedback)


@router.get("/review", response_model=list[ReviewItemResponse])
def get_review_candidates(
    db: Session = Depends(get_db),
    tenant_config: TenantConfig = Depends(get_tenant_config),
) -> list[ReviewItemResponse]:
    """List bad-feedback and non-answered answers for quality review."""
    answers = list_review_candidates(db, tenant_id=tenant_config.tenant_id)
    return [ReviewItemResponse.from_answer(answer) for answer in answers]


def _validate_feedback_payload(payload: FeedbackRequest, config: dict[str, Any]) -> None:
    if payload.rating not in {RATING_GOOD, RATING_BAD}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="rating must be 'good' or 'bad'.",
        )

    feedback_cfg = config.get("feedback")
    feedback = feedback_cfg if isinstance(feedback_cfg, dict) else {}
    if feedback.get("enabled") is not True:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="feedback is disabled for this tenant.",
        )

    categories_value = feedback.get("reason_categories")
    categories = (
        [category for category in categories_value if isinstance(category, str)]
        if isinstance(categories_value, list)
        else []
    )
    if payload.rating == RATING_BAD and categories and payload.reason_category is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reason_category is required for bad feedback.",
        )
    if (
        payload.reason_category is not None
        and categories
        and payload.reason_category not in categories
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reason_category is not allowed for this tenant.",
        )
