"""Stage 2: repair, as a bounded LangGraph loop over a LangChain chain.

The loop is deliberately a state machine rather than an open-ended agent:

    translate -> compile_check -> (fail) -> recall -> repair -> compile_check ...

It terminates on success or after ``MAX_REPAIR_ATTEMPTS``, so it cannot spin,
and every transition is recorded. The model's output is **never trusted**: it
goes straight back to Db2's ``PREPARE``, and a repair that does not compile is
discarded exactly like any other failed candidate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import END, StateGraph

from . import db
from .config import llm_config
from .fixmemory import FixMemory, RecalledFix
from .llm import RuleRepairLLM, build_llm

REPAIR_PROMPT = PromptTemplate.from_template(
    """A SQL statement was translated from {dialect} to IBM Db2 and Db2 rejected it.

Rewrite it so Db2 accepts it, preserving the original meaning exactly.

<ORIGINAL_{dialect_upper}_SQL>
{source_sql}
</ORIGINAL_{dialect_upper}_SQL>

<FAILING_DB2_SQL>
{failing_sql}
</FAILING_DB2_SQL>

Db2 reported:
  SQLCODE = {sqlcode}
  {error_text}
{recalled_block}
Reply with the corrected Db2 SQL statement only."""
)


def _recalled_block(fixes: list[RecalledFix]) -> str:
    if not fixes:
        return ""
    lines = "\n".join(fix.as_prompt_line() for fix in fixes)
    return (
        "\nRepairs that Db2 has already accepted for similar failures:\n"
        f"{lines}\n"
    )


def clean_sql(text: str) -> str:
    """Strip the wrappers a chat model tends to add."""
    body = (text or "").strip()
    if body.startswith("```"):
        lines = [ln for ln in body.splitlines() if not ln.strip().startswith("```")]
        body = "\n".join(lines).strip()
    # Drop a leading language tag or prose line if the SQL clearly starts later.
    for keyword in ("WITH ", "SELECT ", "INSERT ", "UPDATE ", "DELETE ", "MERGE ", "CREATE "):
        index = body.upper().find(keyword)
        if index > 0 and "\n" in body[:index]:
            body = body[index:]
            break
    return body.strip().rstrip(";").strip()


@dataclass
class Attempt:
    n: int
    sql: str
    ok: bool
    sqlcode: int | None
    message: str
    rules_fired: list[str] = field(default_factory=list)
    recalled: int = 0


@dataclass
class RepairOutcome:
    repaired: bool
    final_sql: str
    attempts: list[Attempt] = field(default_factory=list)
    recalled_used: list[RecalledFix] = field(default_factory=list)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)


class _State(TypedDict, total=False):
    source_sql: str
    dialect: str
    candidate: str
    ok: bool
    sqlcode: int | None
    message: str
    attempt: int
    attempts: list[Attempt]
    recalled: list[RecalledFix]


class RepairLoop:
    """Bounded translate/prove/repair state machine."""

    def __init__(
        self,
        conn,
        *,
        memory: FixMemory | None = None,
        llm: Any | None = None,
        max_attempts: int | None = None,
    ):
        self.conn = conn
        self.memory = memory
        self.llm = llm if llm is not None else build_llm()
        self.max_attempts = max_attempts or llm_config().max_repair_attempts
        self.chain = REPAIR_PROMPT | self.llm | StrOutputParser()
        self._graph = self._build_graph()

    # -- graph nodes -----------------------------------------------------
    def _node_prove(self, state: _State) -> _State:
        result = db.compile_check(self.conn, state["candidate"])
        n = state.get("attempt", 0)
        attempt = Attempt(
            n=n,
            sql=state["candidate"],
            ok=result.ok,
            sqlcode=result.sqlcode,
            message=result.message,
            # Attempt 0 is the translator's own output, before any repair ran,
            # so no rule can be responsible for it.
            rules_fired=list(getattr(self.llm, "last_rules", []) or []) if n else [],
            recalled=len(state.get("recalled", []) or []),
        )
        state.setdefault("attempts", []).append(attempt)
        state["ok"] = result.ok
        state["sqlcode"] = result.sqlcode
        state["message"] = result.message
        return state

    def _node_recall(self, state: _State) -> _State:
        if self.memory is None:
            state["recalled"] = []
            return state
        try:
            state["recalled"] = self.memory.recall(
                bad_sql=state["candidate"],
                sqlcode=state.get("sqlcode"),
                error_text=state.get("message", ""),
                k=3,
            )
        except Exception:
            state["recalled"] = []
        return state

    def _node_repair(self, state: _State) -> _State:
        try:
            raw = self.chain.invoke(
                {
                    "dialect": state["dialect"],
                    "dialect_upper": state["dialect"].upper(),
                    "source_sql": state["source_sql"],
                    "failing_sql": state["candidate"],
                    "sqlcode": state.get("sqlcode"),
                    "error_text": state.get("message", ""),
                    "recalled_block": _recalled_block(state.get("recalled", []) or []),
                }
            )
            proposal = clean_sql(raw)
        except Exception as exc:
            proposal = ""
            state["message"] = f"repair model failed: {exc}"
        state["attempt"] = state.get("attempt", 0) + 1
        if proposal and proposal != state["candidate"]:
            state["candidate"] = proposal
        else:
            # Nothing new proposed: stop rather than loop on the same text.
            state["attempt"] = self.max_attempts + 1
        return state

    def _route(self, state: _State) -> str:
        if state.get("ok"):
            return END
        if state.get("attempt", 0) >= self.max_attempts:
            return END
        return "recall"

    def _build_graph(self):
        graph = StateGraph(_State)
        graph.add_node("prove", self._node_prove)
        graph.add_node("recall", self._node_recall)
        graph.add_node("repair", self._node_repair)
        graph.set_entry_point("prove")
        graph.add_conditional_edges("prove", self._route, {"recall": "recall", END: END})
        graph.add_edge("recall", "repair")
        graph.add_edge("repair", "prove")
        return graph.compile()

    # -- public ----------------------------------------------------------
    def run(self, *, source_sql: str, db2_sql: str, dialect: str) -> RepairOutcome:
        # Clear any rule record left by the previous statement.
        if hasattr(self.llm, "last_rules"):
            object.__setattr__(self.llm, "last_rules", [])
        final: _State = self._graph.invoke(
            {
                "source_sql": source_sql,
                "dialect": dialect,
                "candidate": db2_sql,
                "attempt": 0,
                "attempts": [],
                "recalled": [],
            },
            {"recursion_limit": 4 * (self.max_attempts + 2)},
        )
        attempts = final.get("attempts", [])
        succeeded = bool(attempts and attempts[-1].ok)
        return RepairOutcome(
            repaired=succeeded and len(attempts) > 1,
            final_sql=attempts[-1].sql if attempts else db2_sql,
            attempts=attempts,
            recalled_used=final.get("recalled", []) or [],
        )

    @property
    def uses_real_model(self) -> bool:
        return not isinstance(self.llm, RuleRepairLLM)
