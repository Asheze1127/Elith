"""Smoke and regression tests for the foundation layer."""

import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_touch_db() -> None:
    # Regression: /health must be a pure liveness probe. The lazy engine in
    # app.core.db must stay uninitialized (None) even after calling /health,
    # so the probe never requires a live database.
    import app.core.db as db

    db._engine = None
    db._SessionLocal = None

    response = client.get("/health")
    assert response.status_code == 200

    assert db._engine is None
    assert db._SessionLocal is None


def test_setup_logging_falls_back_on_invalid_level(monkeypatch) -> None:
    # Regression: an invalid LOG_LEVEL must not crash startup; setup_logging
    # should fall back to a valid level (INFO) instead of raising.
    from app.core import config
    from app.core import logging as app_logging

    # setup_logging binds get_settings in its own module namespace, so patch
    # the name there. Build Settings directly to bypass the lru_cache.
    monkeypatch.setattr(app_logging, "get_settings", lambda: config.Settings(LOG_LEVEL="NOTALEVEL"))

    # basicConfig is a no-op when the root logger already has handlers, so clear
    # them to observe the level that setup_logging actually applies.
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    for handler in original_handlers:
        root.removeHandler(handler)
    try:
        # Should not raise despite the invalid level, and must fall back to INFO.
        app_logging.setup_logging()
        assert root.level == logging.INFO
    finally:
        for handler in root.handlers[:]:
            root.removeHandler(handler)
        for handler in original_handlers:
            root.addHandler(handler)
        root.setLevel(original_level)
