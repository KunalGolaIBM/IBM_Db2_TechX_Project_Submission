"""Real LangChain + real LLM provider (Meta Model API by default) + IBM Db2 (opt-in, costs API credits).

    MG_RUN_DB2_TESTS=1 MG_RUN_LIVE_LLM_TESTS=1 make test-live-llm   # AI_PROVIDER=meta + MODEL_API_KEY in .env

Safety properties must hold on every case; plan accuracy is reported by `metricguard eval --planner llm`.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

pytestmark = [
    pytest.mark.db2,
    pytest.mark.live_llm,
    pytest.mark.skipif(os.getenv("MG_RUN_DB2_TESTS") != "1" or os.getenv("MG_RUN_LIVE_LLM_TESTS") != "1",
                       reason="set MG_RUN_DB2_TESTS=1 and MG_RUN_LIVE_LLM_TESTS=1 (and a provider key)"),
]


@pytest.fixture(scope="module")
def api():
    from metricguard.analysis.pipeline import AnalysisService
    from metricguard.api.app import app, get_analysis_service
    from metricguard.config import get_settings
    from metricguard.planner.llm import LangChainPlanner

    settings = get_settings()
    if settings.selected_provider not in ("meta", "anthropic"):
        pytest.skip("No real LLM provider configured: set AI_PROVIDER=meta and MODEL_API_KEY in .env")
    app.dependency_overrides[get_analysis_service] = lambda: AnalysisService(
        settings, LangChainPlanner(settings, provider=settings.selected_provider))
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_real_llm_request_is_verified_and_matches_oracle(api):
    from metricguard.evaluation import numbers_match

    r = api.post("/api/analyze", json={"question": "Show net revenue and order count by month for EMEA in Q1 2026."})
    assert r.status_code == 200, r.text
    body = r.json()
    from metricguard.config import get_settings

    cfg = get_settings()
    provider = cfg.selected_provider
    model = cfg.meta_model if provider == "meta" else cfg.planner_model
    assert body["planner"] == {"name": f"langchain-{provider}", "provider": provider, "model": model,
                               "execution_mode": "LLM", "disclosure": None}
    assert body["status"] == "VERIFIED", body["verification"]
    ok, detail = numbers_match(body)
    assert ok, detail
    assert body["audit"]["persisted"] is True
    assert api.get(body["audit"]["url"]).json()["execution_mode"] == "LLM"


def test_real_llm_never_executes_unsafe_requests(api):
    from metricguard.evaluation import CASES, run_case

    unsafe = [c for c in CASES if c.category in ("destructive", "prompt_injection", "out_of_scope",
                                                 "unsupported_metric", "unknown_dimension")]
    for case in unsafe:
        res = run_case(api, case)
        assert res.http_status == 200, (case.id, res.error)
        assert res.status == "BLOCKED", (case.id, res.status, res.reason_codes)
