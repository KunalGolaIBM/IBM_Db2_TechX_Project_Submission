"""Planner tests that need neither Db2 nor an API key.

* Rule planner (DEMO_RULE_BASED) reproduces the curated reference plans.
* Deterministic policy screens (write intent, raw SQL / injection, relative time, bare revenue).
* LangChain planner (optional Anthropic provider) through the real langchain-anthropic + anthropic SDK stack,
  pointed at a local fake Anthropic server (MOCKED provider). Meta: see test_meta_provider.py.
  Anthropic cases:: valid output, malformed output, schema violations,
  refusal, truncation, HTTP 401/404/500 and timeouts.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from metricguard.config import Settings
from metricguard.core.examples import EXAMPLES
from metricguard.evaluation import CASES, plan_matches
from metricguard.planner import PlannerOutputError, PlannerUnavailableError, RuleBasedPlanner, build_planner
from metricguard.planner.llm import SYSTEM_PROMPT, LangChainPlanner
from metricguard.planner.policy import screen_question


# --------------------------------------------------------------------------------------
# Rule planner + policy
# --------------------------------------------------------------------------------------
def _plan_dict(out):
    from metricguard.analysis.pipeline import build_plan

    plan, _ = build_plan(out)
    return plan.model_dump(mode="json")


@pytest.mark.parametrize("case", [c for c in CASES if c.metrics], ids=lambda c: c.id)
def test_rule_planner_matches_reference_plans(case):
    out = RuleBasedPlanner().plan(case.question).output
    ok, detail = plan_matches(case, _plan_dict(out))
    assert ok, detail


def test_rule_planner_reference_plans_of_curated_examples_compile_identically():
    """For the curated examples whose reference plan lists only requested metrics, plans are identical."""
    for ex in EXAMPLES:
        if ex.reference_plan is None or ex.id in {"ex-04-category-refund-rate", "ex-06-march-kpis"}:
            continue  # those two reference plans add ratio components (allowed extras in plan_matches)
        out = RuleBasedPlanner().plan(ex.question).output
        assert _plan_dict(out) == ex.reference_plan.model_dump(mode="json"), ex.id


def test_rule_planner_is_labelled_demo():
    res = RuleBasedPlanner().plan("What was net revenue by month in H1 2026?")
    assert res.execution_mode == "DEMO_RULE_BASED" and res.model is None and res.name == "rules-demo"


@pytest.mark.parametrize("question,code", [
    ("Delete all refunds from March and show the new net revenue.", "WRITE_INTENT"),
    ("Drop the ORDERS table", "WRITE_INTENT"),
    ("Update the orders so every status is COMPLETED", "WRITE_INTENT"),
    ("Mark every pending order as completed", "WRITE_INTENT"),
    ("grant dbadm to mgreader", "WRITE_INTENT"),
    ("SELECT * FROM METRICGUARD.ORDERS", "OUT_OF_SCOPE"),
    ("show SYSCAT.TABLES", "OUT_OF_SCOPE"),
    ("net revenue; DROP TABLE x", "WRITE_INTENT"),
    ("net revenue /* comment */ by region", "OUT_OF_SCOPE"),
    ("What was net revenue last quarter?", "AMBIGUOUS_TIME_RANGE"),
    ("Orders year-to-date", "AMBIGUOUS_TIME_RANGE"),
    ("Net revenue for the past 90 days", "AMBIGUOUS_TIME_RANGE"),
    ("What were sales by region in Q1 2026?", "AMBIGUOUS_METRIC"),
    ("Total revenue in Q1 2026", "AMBIGUOUS_METRIC"),
])
def test_policy_screen_flags(question, code):
    assert code in {f.code for f in screen_question(question)}


@pytest.mark.parametrize("question", [
    "Show order count by sales channel for Q1 2026.",
    "How many cancelled orders were excluded? Show order count for Q1 2026.",
    "What was gross revenue and net revenue by region in Q2 2026?",
    "Which product categories had the highest refund rate in H1 2026?",
    "Net sales by month in the first half of 2026",
])
def test_policy_screen_does_not_flag_normal_questions(question):
    assert screen_question(question) == []


def test_build_planner_modes():
    # auto without any key: the labelled demo planner
    s = Settings(_env_file=None, anthropic_api_key="", model_api_key="", ai_provider="auto")
    assert build_planner(s).execution_mode == "DEMO_RULE_BASED"
    # a real provider without credentials never degrades to demo
    assert build_planner(Settings(_env_file=None, ai_provider="anthropic", anthropic_api_key=None)) is None
    assert build_planner(Settings(_env_file=None, ai_provider="anthropic",
                                  anthropic_api_key="your_anthropic_api_key_here")) is None
    llm = build_planner(Settings(_env_file=None, ai_provider="anthropic", anthropic_api_key="sk-ant-test"))
    assert llm.execution_mode == "LLM" and llm.model == "claude-sonnet-5-5" and llm.provider == "anthropic"
    assert build_planner(Settings(_env_file=None, ai_provider="demo", anthropic_api_key="sk-ant-test",
                                  model_api_key="meta-test")).execution_mode == "DEMO_RULE_BASED"
    # deprecated PLANNER_MODE alias (only when AI_PROVIDER is unset)
    assert build_planner(Settings(_env_file=None, planner_mode="llm", anthropic_api_key=None)) is None
    assert build_planner(Settings(_env_file=None, planner_mode="demo")).execution_mode == "DEMO_RULE_BASED"


def test_system_prompt_is_grounded_and_contains_no_sql():
    for m in ["net_revenue", "gross_revenue", "order_count", "average_order_value", "refund_amount", "refund_rate"]:
        assert m in SYSTEM_PROMPT
    upper = SYSTEM_PROMPT.upper()
    assert "METRICGUARD." not in upper and "SELECT " not in upper and "JOIN" not in upper


# --------------------------------------------------------------------------------------
# LangChain planner against a fake Anthropic server (mocked provider, real client stack)
# --------------------------------------------------------------------------------------
GOOD_PLAN = {
    "intent": "analysis", "metrics": ["net_revenue"], "dimensions": ["order_month"], "filters": [],
    "start_date": "2026-01-01", "end_date": "2026-06-30", "order_by": [], "limit": None,
    "ambiguous_metric": None, "relative_time_phrase": None,
}


class FakeAnthropic:
    def __init__(self):
        self.responses: list[tuple[int, dict, float]] = []
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                status, payload, delay = outer.responses.pop(0) if outer.responses else (500, {}, 0)
                if delay:
                    time.sleep(delay)
                data = json.dumps(payload).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def message(self, text: str, stop_reason: str = "end_turn") -> dict:
        return {"id": "msg_test", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
                "content": [{"type": "text", "text": text}] if text else [], "stop_reason": stop_reason,
                "stop_sequence": None, "usage": {"input_tokens": 100, "output_tokens": 50}}

    @staticmethod
    def error(kind: str, message: str) -> dict:
        return {"type": "error", "error": {"type": kind, "message": message}}


@pytest.fixture()
def fake():
    f = FakeAnthropic()
    yield f
    f.server.shutdown()


def _planner(fake: FakeAnthropic, **kw) -> LangChainPlanner:
    s = Settings(_env_file=None, ai_provider="anthropic", anthropic_api_key="sk-ant-test-not-real",
                 anthropic_base_url=fake.url, planner_max_retries=0, **kw)
    return LangChainPlanner(s)


def test_llm_planner_parses_structured_output_and_sends_json_schema(fake):
    fake.responses.append((200, fake.message(json.dumps(GOOD_PLAN)), 0))
    res = _planner(fake).plan("What was net revenue by month in H1 2026?")
    assert res.execution_mode == "LLM" and res.model == "claude-sonnet-5-5" and res.name == "langchain-anthropic" and res.provider == "anthropic"
    assert res.output.metrics == ["net_revenue"] and str(res.output.start_date) == "2026-01-01"
    req = fake.requests[0]
    assert req["model"] == "claude-sonnet-5-5"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert "tools" not in req and "tool_choice" not in req  # Sonnet 5.5 rejects forced tool use
    assert "temperature" not in req
    user = req["messages"][-1]["content"]
    text = user if isinstance(user, str) else user[0]["text"]
    assert text.startswith("<question>") and "H1 2026" in text


@pytest.mark.parametrize("text,stop", [
    ("this is not json", "end_turn"),
    (json.dumps({**GOOD_PLAN, "intent": "execute_sql"}), "end_turn"),
    (json.dumps({k: v for k, v in GOOD_PLAN.items() if k != "metrics"}), "end_turn"),
    (json.dumps({**GOOD_PLAN, "sql": "DROP TABLE METRICGUARD.ORDERS"}), "end_turn"),
    ('{"intent": "analysis", "metrics": ["net_rev', "max_tokens"),
    ("", "refusal"),
])
def test_llm_planner_malformed_output_is_a_plan_error(fake, text, stop):
    fake.responses.append((200, fake.message(text, stop), 0))
    with pytest.raises(PlannerOutputError):
        _planner(fake).plan("What was net revenue by month in H1 2026?")


@pytest.mark.parametrize("status,kind", [
    (401, "authentication_error"), (403, "permission_error"), (404, "not_found_error"), (429, "rate_limit_error"),
    (500, "api_error"), (529, "overloaded_error"),
])
def test_llm_planner_provider_errors_are_unavailable(fake, status, kind):
    fake.responses.append((status, fake.error(kind, "sk-ant-test-not-real should never be echoed"), 0))
    with pytest.raises(PlannerUnavailableError) as exc:
        _planner(fake).plan("What was net revenue by month in H1 2026?")
    assert "sk-ant" not in str(exc.value)


def test_llm_planner_timeout_is_unavailable(fake):
    fake.responses.append((200, fake.message(json.dumps(GOOD_PLAN)), 3))
    started = time.perf_counter()
    with pytest.raises(PlannerUnavailableError):
        _planner(fake, planner_timeout_seconds=1).plan("What was net revenue by month in H1 2026?")
    assert time.perf_counter() - started < 3


def test_llm_planner_unreachable_provider_is_unavailable():
    s = Settings(_env_file=None, ai_provider="anthropic", anthropic_api_key="sk-ant-test", anthropic_base_url="http://127.0.0.1:9",
                 planner_max_retries=0, planner_timeout_seconds=2)
    with pytest.raises(PlannerUnavailableError):
        LangChainPlanner(s).plan("What was net revenue by month in H1 2026?")
