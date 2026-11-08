"""The AsOf MCP server, through a real MCP client session (in memory) against a stand-in AsOf API.

    .venv-mcp/bin/python -m pytest -q mcp_server/tests
    ASOF_MCP_LIVE_URL=http://127.0.0.1:8000 ...  # also runs one check through a live AsOf (records a ledger row)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import anyio
import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from asof_mcp import AsOfAPI, build_server  # noqa: E402
from mcp.client.client import Client  # noqa: E402

TOKEN = "asof_" + "x" * 43
RECEIPT = "ab" * 32


def claim(pass_no, text, verdict, clause="BRV-002", version="v1"):
    return {"pass_no": pass_no, "claim_no": 1, "text": text, "verdict": verdict, "clause_id": clause,
            "clause_version": version, "effective_from": "2026-01-01", "effective_to": "2026-05-01", "rule_check": "MATCH"}


GATE = {
    "2026-03-10": (200, {"decision": "CORRECTED", "final_answer": "Bereavement fares must be requested before travel.",
                         "reason_code": "CORRECTED_AND_RECHECKED", "ledger_id": 41, "row_hash": RECEIPT,
                         "claims": [claim(1, "You can claim it after travel.", "CONTRADICTED"),
                                    claim(2, "Bereavement fares must be requested before travel.", "SUPPORTED")]}),
    "2026-09-14": (503, {"decision": "ESCALATED", "final_answer": "A specialist will confirm this for you.",
                         "reason_code": "NOT_COVERED", "ledger_id": 42, "row_hash": RECEIPT,
                         "claims": [claim(1, "Credits pay for lounges.", "NOT_COVERED", None, None)]}),
}
TIMELINE = [{"clause_id": "BRV-002", "title": "Bereavement fare requests", "area": "bereavement", "versions": [
    {"version": "v1", "from": "2026-01-01", "to": "2026-05-01", "text": "Before travel only."},
    {"version": "v2", "from": "2026-05-01", "to": "9999-12-31", "text": "Retroactive within 90 days."}]},
    {"clause_id": "BAG-001", "title": "First checked bag fee", "area": "baggage", "versions": [
        {"version": "v2", "from": "2026-06-01", "to": "9999-12-31", "text": "$40 each way."}]}]


def fake_asof(seen: list):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx.Response(401, json={"error": "needs a token"})
        if request.url.path == "/api/gate":
            body = json.loads(request.content)
            status, out = GATE[body["as_of_date"]]
            return httpx.Response(status, json=out)
        if request.url.path == "/api/policy/timeline":
            return httpx.Response(200, json=TIMELINE)
        if request.url.path == "/api/impact/BRV-002":
            return httpx.Response(200, json=[{"kind": "ANSWER", "status": "STALE"},
                                             {"kind": "ANSWER", "status": "HISTORICALLY_VALID"},
                                             {"kind": "PUBLISHED", "status": "NEEDS_REVIEW"}])
        if request.url.path == "/api/ledger/receipt":
            return httpx.Response(200, json={"verdict": "INTACT", "found": True, "matches": True, "chain_status": "OK"})
        return httpx.Response(404, json={"detail": "no such route"})
    return httpx.MockTransport(handler)


def run(coro_fn, token=TOKEN):
    seen: list = []
    server = build_server(AsOfAPI("http://asof.test", token, transport=fake_asof(seen)))

    async def go():
        async with Client(server) as client:
            return await coro_fn(client)

    return anyio.run(go), seen


def payload(result):
    assert not result.is_error, result.content
    return json.loads(result.content[0].text)


def test_the_server_lists_four_tools_and_tells_agents_when_to_check():
    async def go(c):
        return await c.list_tools()

    tools, _ = run(go)
    by_name = {t.name: t for t in tools.tools}
    assert set(by_name) == {"check_answer", "policy_in_force", "change_impact", "verify_receipt"}
    assert by_name["check_answer"].input_schema["required"] == ["question", "draft_answer", "as_of_date"]
    assert by_name["check_answer"].annotations.read_only_hint is False
    assert all(by_name[n].annotations.read_only_hint for n in ("policy_in_force", "change_impact", "verify_receipt"))
    from asof_mcp import INSTRUCTIONS
    assert "Never guess the date" in INSTRUCTIONS and "send_this" in INSTRUCTIONS


def test_a_contradicted_draft_comes_back_corrected_with_the_clause_it_was_checked_against():
    async def go(c):
        return await c.call_tool("check_answer", {"question": "Can I claim the bereavement fare after I travel?",
                                                  "draft_answer": "Yes, after travel.", "as_of_date": "2026-03-10"})

    result, seen = run(go)
    out = payload(result)
    assert out["decision"] == "CORRECTED" and out["send_this"].startswith("Bereavement fares must be requested")
    assert out["claims"] == [{"claim": "Bereavement fares must be requested before travel.", "verdict": "SUPPORTED",
                              "clause": "BRV-002", "version": "v1", "in_force_from": "2026-01-01",
                              "in_force_to": "2026-05-01", "rule_check": "MATCH"}]  # the re-checked rewrite
    assert out["ledger_id"] == 41 and out["receipt"] == RECEIPT
    sent = json.loads(seen[0].content)
    assert sent["channel"] == "api" and sent["doc_id"] == "AURELIA-CSP"


def test_a_held_answer_is_a_decision_not_an_error():
    async def go(c):
        return await c.call_tool("check_answer", {"question": "Credits for lounges?", "draft_answer": "Yes.",
                                                  "as_of_date": "2026-09-14"})

    out = payload(run(go)[0])
    assert out["decision"] == "ESCALATED" and out["send_this"] == "A specialist will confirm this for you."


@pytest.mark.parametrize("bad", ["next tuesday", "2026-02-30", "10/03/2026", ""])
def test_a_date_that_is_not_a_calendar_date_never_reaches_asof(bad):
    async def go(c):
        return await c.call_tool("check_answer", {"question": "q", "draft_answer": "d", "as_of_date": bad})

    result, seen = run(go)
    assert result.is_error and not seen


def test_inputs_beyond_asofs_limits_are_refused_by_the_tool_schema():
    async def go(c):
        return await c.call_tool("check_answer", {"question": "q" * 2001, "draft_answer": "d", "as_of_date": "2026-03-10"})

    result, seen = run(go)
    assert result.is_error and not seen


def test_policy_in_force_returns_the_version_that_applied_on_the_date():
    async def go(c):
        march = await c.call_tool("policy_in_force", {"as_of_date": "2026-03-10", "area": "bereavement"})
        june = await c.call_tool("policy_in_force", {"as_of_date": "2026-06-02"})
        return march, june

    (march, june), _ = run(go)
    assert [(r["clause"], r["version"]) for r in payload(march)["clauses"]] == [("BRV-002", "v1")]
    assert {(r["clause"], r["version"]) for r in payload(june)["clauses"]} == {("BRV-002", "v2"), ("BAG-001", "v2")}


def test_change_impact_and_receipts_are_summarised():
    async def go(c):
        impact = await c.call_tool("change_impact", {"clause_id": "BRV-002"})
        receipt = await c.call_tool("verify_receipt", {"ledger_id": 41, "receipt": RECEIPT})
        bad = await c.call_tool("change_impact", {"clause_id": "../ledger"})
        return impact, receipt, bad

    (impact, receipt, bad), _ = run(go)
    out = payload(impact)
    assert (out["stale_answers"], out["still_valid_answers"], out["help_centre_needing_review"]) == (1, 1, 1)
    assert payload(receipt)["verdict"] == "INTACT"
    assert bad.is_error


def test_the_token_goes_only_in_the_authorization_header_and_a_refusal_is_explained():
    async def go(c):
        return await c.call_tool("policy_in_force", {"as_of_date": "2026-03-10"})

    result, seen = run(go, token="asof_" + "y" * 43)
    assert result.is_error and "checker role" in result.content[0].text
    assert TOKEN not in result.content[0].text and "y" * 43 not in result.content[0].text
    assert seen[0].headers["authorization"].startswith("Bearer asof_")


def test_only_an_http_address_is_accepted_for_asof():
    for url in ("file:///etc/passwd", "http://host/path?x=1", "javascript:alert(1)"):
        with pytest.raises(ValueError):
            AsOfAPI(url)


@pytest.mark.skipif(not os.environ.get("ASOF_MCP_LIVE_URL"), reason="set ASOF_MCP_LIVE_URL to a running AsOf to run")
def test_one_check_through_a_live_asof():
    server = build_server(AsOfAPI(os.environ["ASOF_MCP_LIVE_URL"], os.environ.get("ASOF_MCP_TOKEN")))

    async def go():
        async with Client(server) as c:
            r = await c.call_tool("check_answer", {
                "question": "How much is the first checked bag?", "as_of_date": "2026-07-15",
                "draft_answer": "The first checked bag costs $35 each way on Economy fares."})
            out = payload(r)
            receipt = payload(await c.call_tool("verify_receipt", {"ledger_id": out["ledger_id"], "receipt": out["receipt"]}))
            return out, receipt

    out, receipt = anyio.run(go)
    assert out["decision"] in ("CORRECTED", "ESCALATED") and "$35" not in out["send_this"]
    assert receipt["verdict"] == "INTACT"


def test_the_stdio_server_starts_as_an_agent_launches_it():
    from mcp.client.stdio import StdioServerParameters

    script = Path(__file__).resolve().parents[1] / "asof_mcp.py"
    params = StdioServerParameters(command=sys.executable, args=[str(script)],
                                   env={"ASOF_URL": "http://127.0.0.1:9", "PATH": os.environ.get("PATH", "")})

    async def go():
        async with Client(params) as c:
            tools = await c.list_tools()
            unreachable = await c.call_tool("policy_in_force", {"as_of_date": "2026-03-10"})
            return tools, unreachable

    tools, unreachable = anyio.run(go)
    assert {t.name for t in tools.tools} == {"check_answer", "policy_in_force", "change_impact", "verify_receipt"}
    assert unreachable.is_error and "could not be reached" in unreachable.content[0].text
