"""Health check endpoint. Must not touch the database."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe used by local/compose and Cloud Run."""
    return {"status": "ok"}
