"""Meta Model API provider tests that need neither Db2 nor a real key (MOCKED provider).

The real langchain-openai + openai SDK stack talks to a local fake of Meta's OpenAI-compatible
Chat Completions endpoint. These tests prove request shape, schema validity, parsing, failure mapping and
the "no silent demo fallback" rule. They are NOT evidence that Meta's model plans correctly; see the live tests.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from metricguard.config import Settings
from metricguard.planner import PlannerOutputError, PlannerUnavailableError, build_planner
from metricguard.planner.base import PlannerOutput
from metricguard.planner.llm import LangChainPlanner

KEY = "meta-test-key-0123456789-NOT-REAL"
GOOD_PLAN = {
    "intent": "analysis", "metrics": ["net_revenue"], "dimensions": ["order_month"], "filters": [],
    "start_date": "2026-01-01", "end_date": "2026-06-30", "order_by": [], "limit": None,
    "ambiguous_metric": None, "relative_time_phrase": None,
}


# ---------------------------------------------------------------------------------------
# Provider selection (pure configuration logic)
# ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("kw,expected", [
    (dict(ai_provider="meta", model_api_key=KEY), "meta"),
    (dict(ai_provider="meta", model_api_key=None, anthropic_api_key="sk-ant-x"), None),   # no silent switch
    (dict(ai_provider="meta", model_api_key="your_meta_key_here"), None),                 # placeholder = unset
    (dict(ai_provider="anthropic", anthropic_api_key="sk-ant-x", model_api_key=KEY), "anthropic"),
    (dict(ai_provider="anthropic", model_api_key=KEY), None),
    (dict(ai_provider="demo", model_api_key=KEY), "demo"),
    (dict(ai_provider="auto", model_api_key=KEY, anthropic_api_key="sk-ant-x"), "meta"),  # Meta preferred
    (dict(ai_provider="auto", anthropic_api_key="sk-ant-x"), "anthropic"),
    (dict(ai_provider="auto"), "demo"),
    (dict(), "demo"),                                                                     # nothing set: auto
    (dict(planner_mode="llm", model_api_key=KEY), "meta"),                                # deprecated alias
    (dict(planner_mode="llm"), None),
    (dict(planner_mode="demo", model_api_key=KEY), "demo"),
    (dict(ai_provider="meta", planner_mode="demo", model_api_key=KEY), "meta"),           # AI_PROVIDER wins
])
def test_provider_selection_precedence(kw, expected):
    assert Settings(_env_file=None, **kw).selected_provider == expected


def test_meta_defaults_match_official_docs():
    s = Settings(_env_file=None)
    assert s.meta_model == "muse-spark-1.3" and s.meta_base_url == "https://api.meta.ai/v1"


def test_meta_selected_without_anthropic_key_builds_a_meta_planner():
    p = build_planner(Settings(_env_file=None, ai_provider="meta", model_api_key=KEY))
    assert (p.name, p.provider, p.model, p.execution_mode) == ("langchain-meta", "meta", "muse-spark-1.3", "LLM")


def test_secrets_are_not_in_repr():
    s = Settings(_env_file=None, ai_provider="meta", model_api_key=KEY)
    assert KEY not in repr(s) and KEY not in str(s.model_dump())


# ---------------------------------------------------------------------------------------
# JSON Schema validity for Meta's strict structured output
# ---------------------------------------------------------------------------------------
def _walk(node, defs, depth, seen, problems):
    if depth > 10:
        problems.append("nesting deeper than 10")
        return
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"].split("/")[-1]
            if ref in seen:
                problems.append(f"recursive $ref {ref}")
                return
            _walk(defs[ref], defs, depth + 1, seen | {ref}, problems)
            return
        for bad in ("allOf", "oneOf", "not"):
            if bad in node:
                problems.append(f"unsupported keyword {bad}")
        if node.get("type") == "object" or "properties" in node:
            if node.get("additionalProperties") is not False:
                problems.append("object without additionalProperties:false")
            if set(node.get("required", [])) != set(node.get("properties", {})):
                problems.append("required != properties")
        for k, v in node.items():
            if k != "$defs":
                _walk(v, defs, depth + 1, seen, problems)
    elif isinstance(node, list):
        for v in node:
            _walk(v, defs, depth + 1, seen, problems)


def test_planner_output_schema_satisfies_meta_strict_subset():
    schema = PlannerOutput.model_json_schema()
    problems: list[str] = []
    assert schema["type"] == "object"
    for forbidden in ("anyOf", "oneOf", "allOf", "enum", "not"):
        assert forbidden not in schema, f"root must not use {forbidden}"
    _walk(schema, schema.get("$defs", {}), 0, frozenset(), problems)
    assert problems == []
    assert "sql" not in json.dumps(schema).lower().replace("planned", "")  # the schema has no SQL-carrying field


# ---------------------------------------------------------------------------------------
# Fake Meta server
# ---------------------------------------------------------------------------------------
class FakeMeta:
    def __init__(self):
        self.responses: list[tuple[int, dict, float]] = []
        self.requests: list[dict] = []
        self.headers: list[dict] = []
        self.paths: list[str] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                outer.requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                outer.headers.append({k.lower(): v for k, v in self.headers.items()})
                outer.paths.append(self.path)
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
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @staticmethod
    def completion(content: str | None, finish: str = "stop", refusal: str | None = None) -> dict:
        return {"id": "chatcmpl-test", "object": "chat.completion", "created": 1, "model": "muse-spark-1.3",
                "choices": [{"index": 0, "finish_reason": finish, "logprobs": None,
                             "message": {"role": "assistant", "content": content, "refusal": refusal}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}

    @staticmethod
    def error(code: str, message: str) -> dict:
        return {"error": {"message": message, "type": code, "code": code}}


@pytest.fixture()
def fake():
    f = FakeMeta()
    yield f
    f.server.shutdown()


def _planner(fake: FakeMeta, **kw) -> LangChainPlanner:
    s = Settings(_env_file=None, ai_provider="meta", model_api_key=KEY, meta_base_url=fake.url,
                 planner_max_retries=0, **kw)
    return build_planner(s)


Q = "What was net revenue by month in H1 2026?"


def test_meta_request_shape_and_parsing(fake):
    fake.responses.append((200, fake.completion(json.dumps(GOOD_PLAN)), 0))
    res = _planner(fake).plan(Q)
    assert (res.execution_mode, res.provider, res.name, res.model) == ("LLM", "meta", "langchain-meta", "muse-spark-1.3")
    assert res.output.metrics == ["net_revenue"] and str(res.output.start_date) == "2026-01-01"

    assert fake.paths == ["/v1/chat/completions"]                     # Chat Completions, not Responses
    assert fake.headers[0]["authorization"] == f"Bearer {KEY}"
    req = fake.requests[0]
    assert req["model"] == "muse-spark-1.3"
    rf = req["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["name"] == "PlannerOutput"
    schema = rf["json_schema"]["schema"]
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    # parameters Meta does not document must not be sent (reasoning_effort is opt-in, tested below)
    for absent in ("temperature", "top_p", "tools", "tool_choice", "reasoning_effort", "reasoning", "functions"):
        assert absent not in req, absent
    assert req["messages"][0]["role"] in ("system", "developer")
    assert req["messages"][-1]["content"].startswith("<question>") and "H1 2026" in req["messages"][-1]["content"]
    assert "SELECT" not in json.dumps(req["messages"][0]["content"]).upper().replace("SELECTED", "")


def test_meta_reasoning_effort_is_sent_only_when_configured(fake):
    fake.responses.append((200, fake.completion(json.dumps(GOOD_PLAN)), 0))
    p = build_planner(Settings(_env_file=None, ai_provider="meta", model_api_key=KEY, meta_base_url=fake.url,
                               meta_reasoning_effort="low", planner_max_retries=0))
    p.plan(Q)
    assert fake.requests[0]["reasoning_effort"] == "low"
    assert Settings(_env_file=None, meta_reasoning_effort="").meta_reasoning_effort is None  # empty env value = unset


@pytest.mark.parametrize("effort", ["minimal", "low", "medium", "high", "xhigh", "max"])
def test_meta_reasoning_effort_accepts_every_documented_value(effort, monkeypatch):
    # https://dev.meta.ai/docs/reasoning lists these for Muse Spark 1.3; the env var reaches the wire payload unchanged.
    from langchain_core.messages import HumanMessage

    monkeypatch.setenv("META_REASONING_EFFORT", effort)
    s = Settings(_env_file=None, ai_provider="meta", model_api_key=KEY)
    assert s.meta_reasoning_effort == effort
    chat = build_planner(s)._build_meta()
    assert chat._get_request_payload([HumanMessage("x")])["reasoning_effort"] == effort


@pytest.mark.parametrize("bad", ["none", "turbo"])
def test_meta_reasoning_effort_rejects_unsupported_values(bad):
    # "none" is documented as HTTP 400 for Muse Spark, so it is refused at startup instead of at request time.
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(_env_file=None, meta_reasoning_effort=bad)


def test_default_planner_budget_stays_below_the_browser_timeout():
    # The SDK retries a timed-out attempt, so the worst case is timeout * (retries + 1) plus backoff (<= 8 s).
    # frontend/lib/api/client.ts aborts POST /api/analyze after 90 s; the API must answer first.
    s = Settings(_env_file=None)
    assert s.planner_timeout_seconds * (s.planner_max_retries + 1) + 8 < 90


@pytest.mark.parametrize("content,finish,refusal", [
    ("this is not json", "stop", None),
    (json.dumps({**GOOD_PLAN, "intent": "execute_sql"}), "stop", None),            # value outside the enum
    (json.dumps({k: v for k, v in GOOD_PLAN.items() if k != "metrics"}), "stop", None),  # missing field
    (json.dumps({**GOOD_PLAN, "sql": "DROP TABLE METRICGUARD.ORDERS"}), "stop", None),  # extra field
    (json.dumps({**GOOD_PLAN, "start_date": "June first"}), "stop", None),          # bad date
    ('{"intent": "analysis", "metrics": ["net_rev', "length", None),                # truncated
    (None, "stop", "I can't help with that."),                                       # refusal
    ("", "content_filter", None),
    ("[]", "stop", None),                                                            # wrong JSON shape
])
def test_meta_malformed_or_refused_output_is_a_plan_error(fake, content, finish, refusal):
    fake.responses.append((200, fake.completion(content, finish, refusal), 0))
    with pytest.raises(PlannerOutputError):
        _planner(fake).plan(Q)


@pytest.mark.parametrize("status,code,must_contain", [
    (401, "invalid_api_key", "credentials"), (403, "permission_denied", "credentials"),
    (404, "model_not_found", "not available"), (400, "invalid_request_error", "rejected"),
    (429, "rate_limit_exceeded", "rate-limited"), (500, "server_error", "unavailable"), (503, "overloaded", "unavailable"),
])
def test_meta_provider_errors_are_unavailable_and_leak_nothing(fake, status, code, must_contain):
    fake.responses.append((status, fake.error(code, f"{KEY} should never be echoed"), 0))
    with pytest.raises(PlannerUnavailableError) as exc:
        _planner(fake).plan(Q)
    assert KEY not in str(exc.value) and must_contain in str(exc.value)


def test_meta_invalid_model_id_is_reported_with_the_model_name(fake):
    fake.responses.append((404, fake.error("model_not_found", "no such model"), 0))
    p = build_planner(Settings(_env_file=None, ai_provider="meta", model_api_key=KEY, meta_base_url=fake.url,
                               meta_model="muse-spark-9.9", planner_max_retries=0))
    with pytest.raises(PlannerUnavailableError) as exc:
        p.plan(Q)
    assert "muse-spark-9.9" in str(exc.value)
    assert fake.requests[0]["model"] == "muse-spark-9.9"


def test_meta_timeout_is_unavailable(fake):
    fake.responses.append((200, fake.completion(json.dumps(GOOD_PLAN)), 3))
    started = time.perf_counter()
    with pytest.raises(PlannerUnavailableError):
        _planner(fake, planner_timeout_seconds=1).plan(Q)
    assert time.perf_counter() - started < 3


def test_meta_unreachable_is_unavailable():
    s = Settings(_env_file=None, ai_provider="meta", model_api_key=KEY, meta_base_url="http://127.0.0.1:9/v1",
                 planner_max_retries=0, planner_timeout_seconds=2)
    with pytest.raises(PlannerUnavailableError):
        build_planner(s).plan(Q)


def test_missing_meta_credentials_is_unavailable_not_demo():
    s = Settings(_env_file=None, ai_provider="meta", model_api_key=None)
    assert s.selected_provider is None and build_planner(s) is None
    with pytest.raises(PlannerUnavailableError):
        LangChainPlanner(s)


# ---------------------------------------------------------------------------------------
# End to end through the API: a Meta failure is a 503, never a demo answer, and is not audited
# ---------------------------------------------------------------------------------------
def test_api_meta_failure_returns_503_without_demo_fallback(fake):
    from fastapi.testclient import TestClient

    from metricguard.analysis.pipeline import AnalysisService
    from metricguard.api.app import app, get_analysis_service, get_audit_writer

    fake.responses.append((429, fake.error("rate_limit_exceeded", "slow down"), 0))
    s = Settings(_env_file=None, ai_provider="meta", model_api_key=KEY, meta_base_url=fake.url, planner_max_retries=0)
    audits: list[dict] = []
    app.dependency_overrides[get_analysis_service] = lambda: AnalysisService(s, build_planner(s))
    app.dependency_overrides[get_audit_writer] = lambda: (lambda rec: audits.append(rec) or True)
    try:
        r = TestClient(app).post("/api/analyze", json={"question": Q})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503 and r.json()["error"]["code"] == "PLANNER_UNAVAILABLE"
    assert "answer" not in r.json() and "planner" not in r.json()
    assert audits == [] and KEY not in r.text
