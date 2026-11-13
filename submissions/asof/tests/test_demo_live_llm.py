"""The public demo with live checks, end to end: a real OpenRouter call, the real check graph, Db2's cap and ledger.

    ASOF_RUN_LLM_TESTS=1 pytest -m llm tests/test_demo_live_llm.py -s

Needs OPENROUTER_API_KEY in .env; the test puts it in the process environment, where the demo takes it from.
One live check (about four model calls) and one replayed scenario.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from asof import db
from asof.api import create_app
from asof.config import ConfigError, Settings
from asof.replay import Recording

pytestmark = [pytest.mark.llm, pytest.mark.db2]

QUESTION = "My grandmother died last week. Can I claim the bereavement fare after my trip?"
DRAFT = "Yes. Book now at the normal fare and claim the bereavement discount back within 90 days after you travel."


def test_a_new_draft_is_checked_live_and_a_built_in_one_still_replays(settings, test_schema, admin_conn, monkeypatch):
    try:
        key = settings.secret("openrouter_api_key")
    except ConfigError:
        pytest.skip("no OPENROUTER_API_KEY in .env")
    monkeypatch.setenv("OPENROUTER_API_KEY", key)
    db.use_schema(admin_conn, test_schema)
    db.execute(admin_conn, "DELETE FROM DEMO_SPEND")
    admin_conn.commit()
    demo = Settings(asof_public_demo=True, llm_provider="replay", asof_demo_live=True, asof_demo_live_daily_cap=3,
                    embedding_api_key=None, openai_compat_api_key=None, watsonx_api_key=None)
    with TestClient(create_app(demo, schema=test_schema), client=("127.0.0.1", 51000)) as c:
        assert c.get("/healthz").json()["live_checks"] == "on"
        r = c.post("/api/gate", json={"question": QUESTION, "draft_answer": DRAFT, "as_of_date": "2026-03-10"},
                   headers={"x-forwarded-for": "203.0.113.7"})
        body = r.json()
        assert body["model"].startswith("openrouter:"), body
        assert body["decision"] in ("CORRECTED", "ESCALATED"), body["final_answer"]  # March: v1 forbids it
        assert body["ledger_id"] and "90 days after you travel" not in body["final_answer"]

        built_in = next(x for x in Recording.load().scenarios["checks"] if x["draft"])
        replayed = c.post("/api/gate", json={"question": built_in["question"], "draft_answer": built_in["draft"],
                                             "as_of_date": built_in["as_of"], "doc_id": built_in["doc_id"]},
                          headers={"x-forwarded-for": "203.0.113.7"}).json()
        assert replayed["model"].startswith("replay:") and replayed["decision"] == built_in["decision"]

        db.use_schema(admin_conn, test_schema)
        used, calls, tin, tout = db.query(admin_conn, "SELECT CHECKS_USED, LLM_CALLS, INPUT_TOKENS, OUTPUT_TOKENS "
                                                      "FROM DEMO_SPEND")[0]
        assert used == 1 and calls >= 2 and tin > 0 and tout > 0
        print(f"\nlive check: {body['decision']} {body['reason_code']} in {body['latency_ms']} ms; {calls} model calls, "
              f"{tin} input and {tout} output tokens")
        assert "1 of 3" in c.get("/healthz").json()["public_demo_notice"]
