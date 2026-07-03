"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api import health
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    """Build the FastAPI app: init logging and register routers."""
    setup_logging()
    app = FastAPI(title="Elith RAG Backend")
    app.include_router(health.router)
    return app


app = create_app()
