"""Evaluation result endpoint.

Reads only a real, previously written metrics file. When the SciFact harness has
not been run, the endpoint returns an explicit `not_run` state so the UI cannot
mistake placeholder numbers for measured results.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from app.schemas.verification import EvaluationResponse

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])

RESULTS_FILES = [
    Path(__file__).resolve().parents[4] / "experiments" / "results" / "scifact_test_metrics.json",
    Path(__file__).resolve().parents[4] / "experiments" / "results" / "scifact_dev_metrics.json",
]


@router.get("", response_model=EvaluationResponse)
def get_evaluation() -> EvaluationResponse:
    results_file = next((path for path in RESULTS_FILES if path.exists()), None)
    if results_file is None:
        return EvaluationResponse(
            status="not_run",
            message=(
                "No SciFact benchmark has been executed. The evaluation harness, metrics, "
                "and dataset manifest are prepared, but no measured score is available."
            ),
        )
    try:
        results = json.loads(results_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return EvaluationResponse(
            status="error",
            message="A metrics file exists but could not be read. Inspect experiments/results.",
        )
    return EvaluationResponse(
        status="completed",
        message=f"Metrics loaded from {results_file.name}.",
        results=results,
    )
