"""Checks for the A-company sample config used by local demos."""

import json
from pathlib import Path

from app.rag.steps import STEPS

SAMPLE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "sample_data" / "shinonome_config.json"


def test_sample_config_uses_registered_pipeline_steps() -> None:
    config = json.loads(SAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))

    steps = [step for step in config["pipeline"] if step != "retrieve"]

    assert steps
    assert set(steps).issubset(STEPS)
    assert config["answer"]["citation"] == "required"
    assert "external" in config["answer"]["modes"]
    assert config["feedback"]["reason_categories"]
