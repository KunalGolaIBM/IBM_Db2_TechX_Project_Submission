"""Capture real API responses into docs/examples/ for the frontend.

    env -u PYTHONHOME .venv/bin/python scripts/capture_api_examples.py [--llm]

Every file is a verbatim response from the real code path against live IBM Db2. Nothing is
hand-edited. The planner is DEMO_RULE_BASED unless --llm is given (needs a real provider: AI_PROVIDER=meta + MODEL_API_KEY);
files written with --llm get an `-llm` suffix. `analysis-failure` is produced by pointing the
reader connection at a closed port, which is how a real Db2 outage looks to the pipeline.
"""

from __future__ import annotations

import json
import sys

from fastapi.testclient import TestClient

from metricguard.analysis.pipeline import AnalysisService
from metricguard.api.app import app, get_analysis_service
from metricguard.config import REPO_ROOT, get_settings
from metricguard.db import Db2Client
from metricguard.planner import RuleBasedPlanner
from metricguard.planner.llm import LangChainPlanner

OUT = REPO_ROOT / "docs" / "examples"
CASES = [
    ("successful-analysis", "How many orders did we complete in March 2026, and what was the AOV?"),
    ("grouped-analysis", "Show net revenue and order count by month for EMEA in Q1 2026."),
    ("ambiguous-question", "What was our revenue last quarter?"),
    ("blocked-unsafe-request", "Delete all refunds from March and show the new net revenue."),
    ("blocked-policy", "What is the average order value by product category?"),
    ("executed-with-warnings", "Show gross revenue by month from 2026-06-01 to 2026-08-31."),
]


def main() -> int:
    use_llm = "--llm" in sys.argv
    settings = get_settings()
    if use_llm and settings.selected_provider not in ("meta", "anthropic"):
        print("No real LLM provider is configured (AI_PROVIDER=meta needs MODEL_API_KEY).")
        return 3
    planner = LangChainPlanner(settings) if use_llm else RuleBasedPlanner()
    suffix = "-llm" if use_llm else ""
    OUT.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)
    app.dependency_overrides[get_analysis_service] = lambda: AnalysisService(settings, planner)
    written = []
    try:
        for name, question in CASES:
            body = client.post("/api/analyze", json={"question": question}).json()
            (OUT / f"{name}{suffix}.json").write_text(json.dumps(body, indent=2) + "\n")
            written.append(name)
        down = settings.model_copy(update={"db2_port": 1})
        app.dependency_overrides[get_analysis_service] = lambda: AnalysisService(
            settings, planner, reader_factory=lambda: Db2Client(down, role="reader"))
        body = client.post("/api/analyze", json={"question": "What was net revenue by month in the first half of "
                                                             "2026?"}).json()
        (OUT / f"analysis-failure{suffix}.json").write_text(json.dumps(body, indent=2) + "\n")
        written.append("analysis-failure")
    finally:
        app.dependency_overrides.clear()
    if not use_llm:
        listing = client.get("/api/audit", params={"limit": 3}).json()
        (OUT / "audit-history.json").write_text(json.dumps(listing, indent=2) + "\n")
        detail = client.get(f"/api/audit/{listing['items'][0]['request_id']}").json()
        (OUT / "audit-detail.json").write_text(json.dumps(detail, indent=2) + "\n")
        health = client.get("/api/health").json()
        (OUT / "health.json").write_text(json.dumps(health, indent=2) + "\n")
        written += ["audit-history", "audit-detail", "health"]
    print("wrote", ", ".join(f"docs/examples/{w}{suffix}.json" for w in written))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
