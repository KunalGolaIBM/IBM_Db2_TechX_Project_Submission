"""AsOf as an MCP server: any agent (Claude, an IDE assistant, watsonx Orchestrate, a LangGraph app...) can check
what it is about to tell a customer against the policy in force on the customer's date, before it says it.

    ASOF_URL=http://127.0.0.1:8000 ASOF_MCP_TOKEN=... python mcp_server/asof_mcp.py     # stdio transport

The server is a thin client of AsOf's own HTTP API. It holds no database credentials and no model key: every
call goes through the same validation, roles (ASOF_AUTH=users), rate limits, fail-closed check and hash-chained
ledger as any other caller. ASOF_MCP_TOKEN is a personal AsOf API token (python -m asof.users add agent --roles
checker,auditor); it is sent only to ASOF_URL and never logged or returned.
"""

from __future__ import annotations

import os
import re
from datetime import date
from typing import Annotated, Any, Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field

INSTRUCTIONS = """\
AsOf checks policy statements against the policy version in force on the customer's date, in IBM Db2.
Before you send a customer any answer that states a policy (a fee, a refund, eligibility, a deadline, a
required document), call check_answer with the customer's question, your draft and the date the booking or
account system gives you. Never guess the date. Send the customer only `send_this` from the result: it is your
draft if AsOf released it as written, a rewrite from the clause text if your draft contradicted the policy, or a
holding reply if AsOf could not confirm it. Do not restate the policy yourself after an ESCALATED result.
Every check is recorded in a tamper-evident ledger; `receipt` lets anyone verify the record later."""

DocId = Literal["AURELIA-CSP", "FERNHOLLOW-FEES"]
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CLAUSE_ID = re.compile(r"^[A-Z]{3}-[0-9]{3}$")
HASH = re.compile(r"^[0-9a-f]{64}$")


class AsOfError(ToolError):
    """AsOf refused the call or could not be reached. A ToolError, so the MCP SDK passes this (safe) message to the
    agent; any other exception reaches it only as a generic failure."""


def _date(value: str) -> str:
    if not ISO_DATE.match(value or ""):
        raise AsOfError("as_of_date must be an ISO date (YYYY-MM-DD) supplied by your booking or account system")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise AsOfError(f"{value} is not a calendar date") from None
    return value


class AsOfAPI:
    """The few AsOf endpoints the tools use, with a deadline on every call."""

    def __init__(self, base_url: str, token: str | None = None, transport: httpx.BaseTransport | None = None,
                 timeout_s: float = 330.0):
        if not re.match(r"^https?://[^\s/]+(:\d+)?/?$", base_url):
            raise ValueError("ASOF_URL must be the http(s) address of an AsOf server, such as http://127.0.0.1:8000")
        headers = {"user-agent": "asof-mcp"}
        if token:
            headers["authorization"] = f"Bearer {token}"
        # A check may take minutes on a local model; AsOf itself fails closed after ASOF_CHECK_DEADLINE_S (300 s).
        self._http = httpx.Client(base_url=base_url.rstrip("/"), headers=headers, transport=transport,
                                  timeout=httpx.Timeout(timeout_s, connect=5.0), follow_redirects=False)

    def _call(self, method: str, path: str, json: dict[str, Any] | None = None, held_ok: bool = False) -> Any:
        try:
            r = self._http.request(method, path, json=json)
        except httpx.HTTPError as exc:
            raise AsOfError(f"AsOf could not be reached ({type(exc).__name__})") from None
        try:
            body = r.json()
        except ValueError:
            body = None
        if r.status_code == 503 and held_ok and isinstance(body, dict) and body.get("decision"):
            return body  # a held answer: a decision, not an error
        if r.status_code >= 400:
            if r.status_code in (401, 403):
                raise AsOfError("AsOf refused this token for that action (it needs the checker role to check answers "
                                "and the auditor role for ledger and impact lookups)")
            detail = body.get("error") or body.get("detail") if isinstance(body, dict) else None
            raise AsOfError(f"AsOf answered {r.status_code}: {detail if isinstance(detail, str) else 'request refused'}")
        return body

    def gate(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _json_object(self._call("POST", "/api/gate", payload, held_ok=True))

    def timeline(self, doc_id: str) -> list[dict[str, Any]]:
        return _json_list(self._call("GET", f"/api/policy/timeline?doc_id={doc_id}"))

    def impact(self, clause_id: str) -> list[dict[str, Any]]:
        return _json_list(self._call("GET", f"/api/impact/{clause_id}"))

    def receipt(self, ledger_id: int, row_hash: str) -> dict[str, Any]:
        return _json_object(self._call("POST", "/api/ledger/receipt", {"ledger_id": ledger_id, "row_hash": row_hash}))


def _json_object(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise AsOfError("AsOf returned an unexpected response")
    return body


def _json_list(body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, list) or not all(isinstance(x, dict) for x in body):
        raise AsOfError("AsOf returned an unexpected response")
    return body


def build_server(api: AsOfAPI) -> MCPServer:
    server = MCPServer("asof", title="AsOf", instructions=INSTRUCTIONS, version="1.0",
                       website_url="https://github.com/JustJay7/asof")

    @server.tool(annotations=ToolAnnotations(title="Check an answer against the policy in force", readOnlyHint=False,
                                             destructiveHint=False, idempotentHint=False, openWorldHint=False))
    def check_answer(
        question: Annotated[str, Field(min_length=1, max_length=2000, description="The customer's question, as asked.")],
        draft_answer: Annotated[str, Field(min_length=1, max_length=4000, description="The answer you intend to send.")],
        as_of_date: Annotated[str, Field(description="YYYY-MM-DD from the booking or account system (booking date, "
                                                     "travel date or statement date). Never guessed.")],
        doc_id: Annotated[DocId, Field(description="The policy document: AURELIA-CSP (airline) or FERNHOLLOW-FEES (bank).")]
        = "AURELIA-CSP",
    ) -> dict[str, Any]:
        """Check every policy claim in a draft answer against the clause versions in force on as_of_date. Returns the
        decision (PASS, CORRECTED or ESCALATED), the text to send, the clauses each claim was checked against, and a
        ledger receipt. Send the customer only `send_this`."""
        r = api.gate({"question": question, "draft_answer": draft_answer, "as_of_date": _date(as_of_date),
                      "doc_id": doc_id, "channel": "api"})
        final_pass = 2 if r.get("decision") == "CORRECTED" else 1
        return {
            "decision": r.get("decision"),
            "send_this": r.get("final_answer"),
            "released_as_written": r.get("decision") == "PASS",
            "reason": r.get("reason_code"),
            "claims": [{"claim": c["text"], "verdict": c["verdict"], "clause": c.get("clause_id"),
                        "version": c.get("clause_version"), "in_force_from": c.get("effective_from"),
                        "in_force_to": c.get("effective_to"), "rule_check": c.get("rule_check")}
                       for c in r.get("claims", []) if c.get("pass_no") == final_pass],
            "ledger_id": r.get("ledger_id"),
            "receipt": r.get("row_hash"),
        }

    @server.tool(annotations=ToolAnnotations(title="Policy clauses in force on a date", readOnlyHint=True,
                                             openWorldHint=False))
    def policy_in_force(
        as_of_date: Annotated[str, Field(description="YYYY-MM-DD.")],
        doc_id: Annotated[DocId, Field(description="AURELIA-CSP or FERNHOLLOW-FEES.")] = "AURELIA-CSP",
        area: Annotated[str | None, Field(max_length=40, description="Optional policy area, such as bereavement, "
                                                                     "baggage, refund or overdraft.")] = None,
    ) -> dict[str, Any]:
        """The version of every clause that applied on as_of_date (Db2 business time), with its text and period."""
        on = _date(as_of_date)
        out = []
        for c in api.timeline(doc_id):
            if area and c.get("area") != area:
                continue
            v = next((v for v in c["versions"] if str(v["from"]) <= on < str(v["to"])), None)
            if v:
                out.append({"clause": c["clause_id"], "title": c["title"], "area": c["area"], "version": v["version"],
                            "in_force_from": v["from"], "in_force_to": v["to"], "text": v["text"]})
        return {"as_of_date": on, "doc_id": doc_id, "clauses": out}

    @server.tool(annotations=ToolAnnotations(title="What a policy change made stale", readOnlyHint=True,
                                             openWorldHint=False))
    def change_impact(clause_id: Annotated[str, Field(description="A clause ID such as BRV-002.")]) -> dict[str, Any]:
        """Every released answer and help-centre answer that relied on a clause, judged against the policy as it
        stands now: STALE (the customer was told a version that no longer covers their date) or HISTORICALLY_VALID."""
        if not CLAUSE_ID.match(clause_id or ""):
            raise AsOfError("clause_id looks like BRV-002")
        rows = api.impact(clause_id)

        def count(kind: str, status: str) -> int:
            return sum(1 for r in rows if r["kind"] == kind and r["status"] == status)

        return {"stale_answers": count("ANSWER", "STALE"), "still_valid_answers": count("ANSWER", "HISTORICALLY_VALID"),
                "help_centre_needing_review": count("PUBLISHED", "NEEDS_REVIEW"), "rows": rows}

    @server.tool(annotations=ToolAnnotations(title="Verify a ledger receipt", readOnlyHint=True, openWorldHint=False))
    def verify_receipt(ledger_id: Annotated[int, Field(ge=1, le=10**12)],
                       receipt: Annotated[str, Field(description="The 64-character receipt check_answer returned.")],
                       ) -> dict[str, Any]:
        """Does the ledger still hold exactly the decision this receipt was issued for? Re-verifies the hash chain."""
        if not HASH.match(receipt or ""):
            raise AsOfError("a receipt is 64 lowercase hexadecimal characters")
        return api.receipt(ledger_id, receipt)

    return server


def main() -> None:
    api = AsOfAPI(os.environ.get("ASOF_URL", "http://127.0.0.1:8000"), os.environ.get("ASOF_MCP_TOKEN") or None)
    build_server(api).run("stdio")


if __name__ == "__main__":
    main()
