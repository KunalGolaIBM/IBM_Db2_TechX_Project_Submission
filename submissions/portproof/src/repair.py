"""Stage 2: repair, as a bounded LangGraph loop over a LangChain chain.

The loop is deliberately a state machine rather than an open-ended agent:

    translate -> compile_check -> (fail) -> recall -> repair -> compile_check ...

It terminates on success or after ``MAX_REPAIR_ATTEMPTS``, so it cannot spin,
and every transition is recorded. The model's output is **never trusted**: it
goes straight back to Db2's ``PREPARE``, and a repair that does not compile is
discarded exactly like any other failed candidate.

The repair node is tiered by cost (``LLM_PROVIDER=tiered``, the default):

1. **memory** -- if Db2's vector fix-memory holds a verified repair of this
   exact failing statement, that repair is proposed. No rule runs and no model
   is called.
2. **rules** -- the deterministic rewrites in :mod:`src.llm`. Free.
3. **model** -- a language model, called only for what the first two tiers
   could not get past Db2, with Db2's own error text in the prompt.

Every tier's proposal goes through the same safety check and the same
``PREPARE``, and each attempt records which tier produced it, so "how much of
this was AI" is a column in the ledger rather than a claim.
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
from .llm import HttpRepairLLM, RuleRepairLLM, apply_rules, build_llm, build_model
from .safety import UnsafeSql, check_read_only
from .translate import normalise

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
    #: Who proposed this candidate: translator | memory | rules | model.
    tier: str = "translator"


@dataclass
class RepairOutcome:
    repaired: bool
    final_sql: str
    attempts: list[Attempt] = field(default_factory=list)
    recalled_used: list[RecalledFix] = field(default_factory=list)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def fixed_by(self) -> str:
        """The tier whose proposal Db2 accepted, or "" if none was."""
        if self.repaired and self.attempts and self.attempts[-1].ok:
            return self.attempts[-1].tier
        return ""

    @property
    def model_calls(self) -> int:
        return sum(1 for a in self.attempts if a.tier == "model")


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
    #: Which tier produced the current candidate, and which are used up.
    tier: str
    spent: list[str]
    rules_fired: list[str]


class RepairLoop:
    """Bounded translate/prove/repair state machine."""

    def __init__(
        self,
        conn,
        *,
        memory: FixMemory | None = None,
        llm: Any | None = None,
        max_attempts: int | None = None,
        tiers: tuple[str, ...] | None = None,
    ):
        self.conn = conn
        self.memory = memory
        cfg = llm_config()
        if llm is not None:
            # An explicit model is the whole policy: it is asked every time.
            self.llm = llm
            self.tiers = tiers or ("chain",)
        elif cfg.is_tiered:
            model = build_model(cfg)
            self.llm = model or RuleRepairLLM()
            self.tiers = tiers or (("memory", "rules") + (("chain",) if model else ()))
        else:
            self.llm = build_llm(cfg)
            self.tiers = tiers or ("chain",)
        self.max_attempts = max_attempts or cfg.max_repair_attempts
        self.chain = REPAIR_PROMPT | self.llm | StrOutputParser()
        self._graph = self._build_graph()

    @property
    def model(self) -> Any | None:
        """The language model behind this loop, if there is one."""
        return self.llm if isinstance(self.llm, HttpRepairLLM) else None

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
            rules_fired=list(state.get("rules_fired", []) or []) if n else [],
            recalled=len(state.get("recalled", []) or []),
            tier=state.get("tier", "translator") if n else "translator",
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

    def _propose(self, tier: str, state: _State) -> str:
        """One tier's candidate for the failing statement, or "" if it has none."""
        candidate = state["candidate"]
        state["rules_fired"] = []
        if tier == "memory":
            # Only an exact match is replayed. A similar failure is context for
            # the model (see the prompt); it is not a repair of *this* SQL.
            exact = getattr(self.memory, "exact", None)
            if callable(exact):
                return exact(bad_sql=candidate, dialect=state["dialect"]) or ""
            wanted = normalise(candidate)
            for fix in state.get("recalled", []) or []:
                if fix.dialect == state["dialect"] and normalise(fix.bad_sql) == wanted:
                    return fix.fixed_sql
            return ""
        if tier == "rules":
            repaired, fired = apply_rules(candidate)
            state["rules_fired"] = fired
            return repaired if fired else ""
        try:
            raw = self.chain.invoke(
                {
                    "dialect": state["dialect"],
                    "dialect_upper": state["dialect"].upper(),
                    "source_sql": state["source_sql"],
                    "failing_sql": candidate,
                    "sqlcode": state.get("sqlcode"),
                    "error_text": state.get("message", ""),
                    "recalled_block": _recalled_block(state.get("recalled", []) or []),
                }
            )
        except Exception as exc:
            state["message"] = f"repair model failed: {exc}"
            return ""
        state["rules_fired"] = list(getattr(self.llm, "last_rules", []) or [])
        return clean_sql(raw)

    def _node_repair(self, state: _State) -> _State:
        spent = state.setdefault("spent", [])
        proposal, used = "", ""
        for tier in self.tiers:
            if tier in spent:
                continue
            proposal = self._propose(tier, state)
            used = tier
            # Memory and rules are deterministic: asked once, they have said
            # all they will say. The model may be asked again with Db2's next
            # error, which is new information to it.
            if tier != "chain" or not proposal or proposal == state["candidate"]:
                spent.append(tier)
            if proposal and proposal != state["candidate"]:
                break
            proposal = ""
        state["tier"] = (
            ("rules" if isinstance(self.llm, RuleRepairLLM) else "model") if used == "chain" else used
        )

        # The model's output is untrusted input, and `PREPARE` alone is not a
        # sufficient guard: `DROP TABLE orders` prepares perfectly well, and a
        # repair prompt carries attacker-influenced text (the source SQL and
        # Db2's own error message) straight into a generative model. So a
        # proposal must also be a single read-only query before it is allowed
        # anywhere near the connection.
        #
        # With LLM_PROVIDER=mock the rewrite rules cannot produce DDL, which is
        # exactly why this has to be checked rather than assumed: the default is
        # safe and the configurable path is not.
        if proposal:
            try:
                check_read_only(proposal)
            except UnsafeSql as exc:
                state["message"] = f"repair rejected before execution: {exc}"
                proposal = ""

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
    def run(
        self, *, source_sql: str, db2_sql: str, dialect: str, case_name: str = ""
    ) -> RepairOutcome:
        # Clear any rule record left by the previous statement.
        if hasattr(self.llm, "last_rules"):
            object.__setattr__(self.llm, "last_rules", [])
        if hasattr(self.llm, "case_name"):
            object.__setattr__(self.llm, "case_name", case_name)
        final: _State = self._graph.invoke(
            {
                "source_sql": source_sql,
                "dialect": dialect,
                "candidate": db2_sql,
                "attempt": 0,
                "attempts": [],
                "recalled": [],
                "spent": [],
                "tier": "translator",
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
