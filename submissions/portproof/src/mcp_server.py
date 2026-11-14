"""PortProof as a Model Context Protocol server.

    python -m src.mcp_server            # stdio, for any MCP client

An agent that writes or converts SQL has the same problem the translator has:
nothing tells it whether the result is right. These tools let it ask Db2. They
are deliberately few, and every one of them is a question with an engine's
answer, never an action:

``check_compiles``   does Db2 accept this statement (a server side PREPARE)
``prove_statement``  translate, compile, repair, then run it against the real
                     source engine over adversarial datasets and compare
``estimate_cost``    Db2's optimizer estimate for a statement, in timerons
``ledger_summary``   what has been proved so far, and what the model has cost

Everything an agent sends is treated as hostile input: it must be one read-only
query before it reaches a connection, exactly as a model's own repair proposal
must. Nothing here can change the migration ledger except by proving something,
and the ledger is written through the same SQL PL procedures as any other run.

Db2's own agent tooling, the Genius Hub MCP server, exposes diagnostics about a
database. This is the complement for a migration: a way for an agent to check
its SQL against the engine before anybody trusts it.
"""
from __future__ import annotations

import threading
from typing import Any

from . import costgate, db
from .config import runtime_config, setup_config
from .corpus import DIALECTS, Statement
from .counterexample import FIXTURE_SCHEMA, ensure_fixture_schema
# Imported here, on the main thread, and not inside the tool that needs it.
# Measured on Windows: a tool call runs on a worker thread while another thread
# is blocked reading stdin, and the first import of a native module (numpy,
# pulled in by the fix memory's vector store) from that worker never returns.
from .pipeline import Pipeline
from .safety import UnsafeSql, check_read_only

_LOCK = threading.Lock()
_STATE: dict[str, Any] = {}


def _connections():
    if "app" not in _STATE:
        _STATE["app"] = db.connect(runtime_config(), role="app")
        _STATE["owner"] = db.connect(setup_config(), role="setup")
        db.execute(_STATE["app"], "SET CURRENT SCHEMA PORTPROOF")
    return _STATE["app"], _STATE["owner"]


def _pipeline():
    if "pipeline" not in _STATE:
        app, owner = _connections()
        # learn=False: an agent's exploratory questions must not teach the fix
        # memory or the dead-end table anything. The verdict is still recorded.
        _STATE["pipeline"] = Pipeline(app_conn=app, owner_conn=owner, learn=False)
    return _STATE["pipeline"]


def _refuse(sql: str) -> str | None:
    try:
        check_read_only(sql)
    except UnsafeSql as exc:
        return str(exc)
    return None


def check_compiles(db2_sql: str) -> dict[str, Any]:
    """Ask Db2 whether it accepts a statement, without executing it."""
    refused = _refuse(db2_sql)
    if refused:
        return {"accepted": False, "refused_before_db2": refused}
    with _LOCK:
        _, owner = _connections()
        ensure_fixture_schema(owner)
        verdict = db.compile_check(owner, db2_sql)
    return {
        "accepted": verdict.ok,
        "sqlcode": verdict.sqlcode,
        "message": (verdict.message or "")[:400],
    }


def prove_statement(source_sql: str, dialect: str, name: str = "agent/adhoc") -> dict[str, Any]:
    """Translate one statement to Db2 and prove it against its own source engine."""
    if dialect not in DIALECTS:
        return {"status": "REFUSED", "reason": f"dialect must be one of {', '.join(DIALECTS)}"}
    refused = _refuse(source_sql)
    if refused:
        return {"status": "REFUSED", "reason": refused}
    with _LOCK:
        result = _pipeline().run_statement(Statement(dialect, name[:60], source_sql))
    witness = result.semantic.witness if result.semantic else None
    out: dict[str, Any] = {
        "status": result.status,
        "db2_sql": result.db2_sql,
        "translator_raised": result.translator_raised,
        "silent_failure": result.silent_failure,
        "first_sqlcode_from_db2": result.first_sqlcode,
        "compile_repaired_by": result.repair.fixed_by if result.repair and result.repaired else None,
        "meaning_repaired_by": result.semantic_repair.rule
        if result.semantic_repair and result.semantic_repair.repaired else None,
        "evidence": result.semantic.strength if result.semantic else None,
        "proof": result.semantic.headline if result.semantic else None,
        "datasets": result.datasets_used,
        "certificate": result.semantic_cert or result.compile_cert,
    }
    if witness is not None and not witness.agreed:
        out["counterexample"] = {
            "dataset": witness.variant,
            "what_it_provokes": witness.targets,
            "source_rows": [list(r) for r in witness.source_rows[:5]],
            "db2_rows": [list(r) for r in witness.db2_rows[:5]],
        }
    if result.minimal is not None:
        out["smallest_counterexample"] = result.minimal.as_detail()
    if result.cost_ratio is not None:
        out["estimated_cost"] = {"before": result.cost_before, "after": result.cost_after}
    return out


def estimate_cost(db2_sql: str) -> dict[str, Any]:
    """Db2's optimizer estimate for a statement over the fixture schema."""
    refused = _refuse(db2_sql)
    if refused:
        return {"timerons": None, "refused_before_db2": refused}
    with _LOCK:
        _, owner = _connections()
        ensure_fixture_schema(owner)
        db.execute(owner, f"SET CURRENT SCHEMA {FIXTURE_SCHEMA}")
        cost = costgate.estimate(owner, db2_sql)
    return {
        "timerons": cost,
        "note": None if cost is not None else
        "no estimate: the statement did not compile, or the Explain tables are not installed "
        "(scripts/create_explain_tables.sh)",
    }


def ledger_summary() -> dict[str, Any]:
    """What the ledger in Db2 holds: verdicts by status, and the model's bill."""
    with _LOCK:
        app, _ = _connections()
        statuses = db.fetch_all(
            app, "SELECT STATUS, COUNT(*) FROM PORTPROOF.STATEMENT GROUP BY STATUS ORDER BY STATUS")
        try:
            cost = db.fetch_all(
                app,
                "SELECT STAGE, CALLS, PROMPT_TOKENS, COMPLETION_TOKENS FROM PORTPROOF.LLM_COST "
                "ORDER BY STAGE")
        except db.Db2Error:
            cost = []
    return {
        "statements_by_status": {str(s).strip(): int(n) for s, n in statuses},
        "model_calls_by_stage": [
            {"stage": str(s).strip(), "calls": int(c), "tokens_in": int(p or 0),
             "tokens_out": int(o or 0)}
            for s, c, p, o in cost
        ],
    }


TOOLS = (check_compiles, prove_statement, estimate_cost, ledger_summary)


def build_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(
        "portproof",
        instructions=(
            "Ask IBM Db2 whether SQL converted from PostgreSQL, MySQL, SQL Server or SQLite "
            "is valid and returns the same rows as the original. Statements are proved over "
            "PortProof's fixture tables: customers, orders, order_items, events."
        ),
    )
    for tool in TOOLS:
        server.tool()(tool)
    return server


def main() -> int:
    build_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
