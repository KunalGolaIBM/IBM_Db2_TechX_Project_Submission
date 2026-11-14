"""Agent run / step audit trail persisted in Db2 (AGENT_RUNS, AGENT_STEPS)."""
from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .db import Db2, Db2Error, get_db


def _clip(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= limit else text[: limit - 20] + "...[truncated]"


@dataclass
class RunContext:
    """Per-question context shared by all agents and tools."""

    question: str
    thread_id: str | None = None
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent: str = "router"
    on_event: Callable[[dict], None] | None = None
    db: Db2 | None = None
    persist: bool = True
    llm_calls: int = 0

    def __post_init__(self):
        if self.persist and self.db is None:
            self.db = get_db("admin")

    # -- events -------------------------------------------------------------
    def emit(self, **event: Any) -> None:
        if self.on_event:
            try:
                self.on_event(event)
            except Exception:
                pass

    def call_llm(self, make, messages):
        """Every LLM request of a run goes through here: counted, shown live, and quota-aware."""
        from .llm import invoke_llm

        self.llm_calls += 1
        self.emit(type="llm_call", n=self.llm_calls, agent=self.agent)
        return invoke_llm(make, messages, self.on_model_switch)

    def on_model_switch(self, old: str, new: str) -> None:
        """Called by the LLM fallback chain; the switch is shown live and audited in AGENT_STEPS."""
        self.emit(type="model_switch", old=old, new=new)
        self.step("llm_fallback", {"from": old, "to": new}, "daily quota exhausted", True, 0)
        if self.persist:
            try:
                self.db.execute("UPDATE AGENT_RUNS SET MODEL = ? WHERE RUN_ID = ?", (f"{old} -> {new}"[:60],
                                                                                    self.run_id))
            except Db2Error:
                pass

    # -- persistence --------------------------------------------------------
    def start(self, model: str) -> None:
        if self.persist:
            self.db.execute(
                "INSERT INTO AGENT_RUNS (RUN_ID, THREAD_ID, USER_QUESTION, MODEL) VALUES (?, ?, ?, ?)",
                (self.run_id, self.thread_id, _clip(self.question, 4000), model),
            )

    def memory(self, turns: int = 4) -> str:
        """Earlier completed turns of this conversation thread, read back from Db2."""
        if not (self.persist and self.thread_id):
            return ""
        rows = self.db.query(
            "SELECT USER_QUESTION, SUBSTR(FINAL_ANSWER, 1, 1500) AS ANSWER FROM AGENT_RUNS "
            "WHERE THREAD_ID = ? AND STATUS = 'DONE' AND RUN_ID <> ? "
            "ORDER BY STARTED_AT DESC FETCH FIRST ? ROWS ONLY",
            (self.thread_id, self.run_id, turns),
        )
        if not rows:
            return ""
        lines = [f"Manager: {r['USER_QUESTION']}\nCopilot: {r['ANSWER']}" for r in reversed(rows)]
        return "Earlier in this conversation (from Db2 memory):\n" + "\n---\n".join(lines)

    def step(self, tool: str, tool_input: Any, output: Any, ok: bool, latency_ms: int) -> None:
        self.emit(type="tool", agent=self.agent, tool=tool, input=tool_input, ok=ok,
                  latency_ms=latency_ms, output=_clip(output, 1500))
        if not self.persist:
            return
        try:
            self.db.execute(
                "INSERT INTO AGENT_STEPS (RUN_ID, AGENT, TOOL_NAME, TOOL_INPUT, TOOL_OUTPUT, OK, LATENCY_MS) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self.run_id, self.agent, tool, _clip(tool_input, 60000), _clip(output, 250000),
                 1 if ok else 0, latency_ms),
            )
        except Db2Error:
            pass  # auditing must never break the agent

    def finish(self, route: str, answer: str, status: str = "DONE") -> None:
        if self.persist:
            self.db.execute(
                "UPDATE AGENT_RUNS SET ROUTE = ?, FINAL_ANSWER = ?, STATUS = ?, FINISHED_AT = CURRENT TIMESTAMP, "
                "LLM_CALLS = ? WHERE RUN_ID = ?",
                (route, answer, status, self.llm_calls, self.run_id),
            )
            try:  # copy the new chain head outside Db2, so even a rebuilt ledger is caught later
                write_anchor(self.db, note=f"run {self.run_id[:8]}")
            except Exception:
                pass


CHAIN_SQL = """
WITH S AS (
  SELECT STEP_ID, ROW_HASH,
         HEX(HASH(COALESCE(LAG(ROW_HASH) OVER (ORDER BY STEP_ID), 'GENESIS')
                  || '|' || TRIM(CHAR(STEP_ID)) || '|' || RUN_ID || '|' || AGENT || '|' || TOOL_NAME
                  || '|' || TRIM(CHAR(OK))
                  || '|' || CAST(SUBSTR(COALESCE(TOOL_INPUT, ''), 1, 2000) AS VARCHAR(8000))
                  || '|' || CAST(SUBSTR(COALESCE(TOOL_OUTPUT, ''), 1, 2000) AS VARCHAR(8000)), 2)) AS EXPECTED
    FROM AGENT_STEPS)
SELECT COUNT(*) AS STEPS,
       COALESCE(SUM(CASE WHEN ROW_HASH = EXPECTED THEN 0 ELSE 1 END), 0) AS BROKEN,
       MIN(CASE WHEN ROW_HASH <> EXPECTED OR ROW_HASH IS NULL THEN STEP_ID END) AS FIRST_BROKEN_STEP
  FROM S"""


def verify_audit_chain(db: Db2 | None = None) -> dict:
    """Recompute the SHA-256 hash chain of AGENT_STEPS inside Db2 and report where it breaks, if anywhere."""
    row = (db or get_db("admin")).query(CHAIN_SQL)[0]
    row["INTACT"] = row["BROKEN"] == 0 and row["FIRST_BROKEN_STEP"] is None
    return row


def simulate_tampering(step_id: int | None = None) -> dict:
    """Quietly edit one past agent step inside a transaction, let Db2 re-verify the chain, then roll back.

    Even a DBA-level edit of a single recorded tool output is detected at exactly that step, because every
    ROW_HASH covers the previous hash. Nothing is persisted: the edit is rolled back before returning.
    """
    import ibm_db

    from .config import load_settings

    s = load_settings().db2
    db = Db2(s.conn_str(s.admin_user, s.admin_password), "tamper-demo")
    try:
        if step_id is None:  # pick a step in the middle of the trail, like an insider covering their tracks
            step_id = db.scalar("SELECT STEP_ID FROM (SELECT STEP_ID, ROW_NUMBER() OVER (ORDER BY STEP_ID) AS RN, "
                                "COUNT(*) OVER () AS N FROM AGENT_STEPS) T WHERE RN = N / 2 + 1")
        if step_id is None:
            raise ValueError("no agent steps recorded yet")
        step = db.query("SELECT STEP_ID, RUN_ID, AGENT, TOOL_NAME, SUBSTR(TOOL_OUTPUT, 1, 160) AS OUTPUT "
                        "FROM AGENT_STEPS WHERE STEP_ID = ?", (int(step_id),))[0]
        ibm_db.autocommit(db.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        try:
            db.execute("UPDATE AGENT_STEPS SET TOOL_OUTPUT = ? WHERE STEP_ID = ?",
                       ('{"note": "quietly edited after the fact"}', int(step_id)))
            tampered = verify_audit_chain(db)
        finally:
            ibm_db.rollback(db.conn)
            ibm_db.autocommit(db.conn, ibm_db.SQL_AUTOCOMMIT_ON)
        restored = verify_audit_chain(db)
    finally:
        db.close()
    return {"step": step, "tampered": tampered, "restored": restored}


# --------------------------------------------------------------------------- external anchors
# The hash chain is tamper-evident, not tamper-proof: an insider with DBA rights could edit a step and
# recompute every later hash, and the chain would verify again. Anchors close that gap: after each run the
# current chain head (step id + hash) is copied to a file outside Db2. A rebuilt ledger no longer matches it.
ANCHOR_FILE = Path(os.getenv("AUDIT_ANCHOR_FILE", str(Path.home() / ".hotelops" / "audit_anchors.jsonl")))

REHASH_SQL = (
    "UPDATE AGENT_STEPS SET ROW_HASH = HEX(HASH(CAST(? AS VARCHAR(64)) || '|' || TRIM(CHAR(STEP_ID)) || '|' || "
    "RUN_ID || '|' || AGENT || '|' || TOOL_NAME || '|' || TRIM(CHAR(OK)) || '|' || "
    "CAST(SUBSTR(COALESCE(TOOL_INPUT, ''), 1, 2000) AS VARCHAR(8000)) || '|' || "
    "CAST(SUBSTR(COALESCE(TOOL_OUTPUT, ''), 1, 2000) AS VARCHAR(8000)), 2)) WHERE STEP_ID = ?"
)


def chain_head(db: Db2 | None = None) -> dict | None:
    rows = (db or get_db("admin")).query(
        "SELECT STEP_ID, ROW_HASH, (SELECT COUNT(*) FROM AGENT_STEPS) AS STEPS FROM AGENT_STEPS "
        "ORDER BY STEP_ID DESC FETCH FIRST 1 ROW ONLY")
    return rows[0] if rows else None


def write_anchor(db: Db2 | None = None, note: str = "", path: Path | None = None) -> dict | None:
    """Append the current chain head to the anchor file (outside Db2). Returns the anchor written."""
    import datetime as dt

    head = chain_head(db)
    if not head:
        return None
    anchor = {"anchored_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "step_id": int(head["STEP_ID"]), "row_hash": head["ROW_HASH"], "steps": int(head["STEPS"]),
              "note": note}
    target = path or ANCHOR_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(anchor) + "\n")
    return anchor


def latest_anchor(path: Path | None = None) -> dict | None:
    target = path or ANCHOR_FILE
    if not target.exists():
        return None
    lines = [ln for ln in target.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return json.loads(lines[-1]) if lines else None


def check_anchor(db: Db2 | None = None, anchor: dict | None = None) -> dict:
    """Does Db2 still hold the exact hash we copied out at the anchored step?"""
    anchor = anchor or latest_anchor()
    if not anchor:
        return {"ok": None, "reason": "no anchor written yet"}
    stored = (db or get_db("admin")).scalar("SELECT ROW_HASH FROM AGENT_STEPS WHERE STEP_ID = ?",
                                            (anchor["step_id"],))
    if stored is None:
        return {"ok": False, "reason": f"step {anchor['step_id']} is gone", "anchor": anchor}
    ok = stored.strip() == anchor["row_hash"].strip()
    return {"ok": ok, "anchor": anchor, "stored_hash": stored.strip(),
            "reason": "matches the hash copied out of Db2" if ok else "Db2 hash differs from the external anchor"}


def simulate_rebuilt_ledger(step_id: int | None = None) -> dict:
    """An insider edits one step AND recomputes every later hash, inside a transaction that is rolled back.

    The in-database chain check then passes (the ledger was rebuilt consistently), but the external anchor
    no longer matches. Needs an anchor; one is written first if there is none.
    """
    import ibm_db

    from .config import load_settings

    s = load_settings().db2
    db = Db2(s.conn_str(s.admin_user, s.admin_password), "rebuild-demo")
    try:
        anchor = latest_anchor()
        head = chain_head(db)
        if not anchor or (head and anchor["step_id"] != int(head["STEP_ID"])):
            anchor = write_anchor(db, note="anchor before rebuild demo")
        if step_id is None:
            step_id = db.scalar("SELECT STEP_ID FROM (SELECT STEP_ID, ROW_NUMBER() OVER (ORDER BY STEP_ID) AS RN, "
                                "COUNT(*) OVER () AS N FROM AGENT_STEPS) T WHERE RN = N / 2 + 1")
        ids = [r["STEP_ID"] for r in db.query("SELECT STEP_ID FROM AGENT_STEPS WHERE STEP_ID >= ? ORDER BY STEP_ID",
                                               (int(step_id),))]
        ibm_db.autocommit(db.conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        try:
            db.execute("UPDATE AGENT_STEPS SET TOOL_OUTPUT = ? WHERE STEP_ID = ?",
                       ('{"note": "quietly edited after the fact"}', int(step_id)))
            prev = db.scalar("SELECT COALESCE((SELECT ROW_HASH FROM AGENT_STEPS WHERE STEP_ID < ? "
                             "ORDER BY STEP_ID DESC FETCH FIRST 1 ROW ONLY), 'GENESIS') FROM SYSIBM.SYSDUMMY1",
                             (int(step_id),))
            for sid in ids:  # recompute the whole tail of the chain, as a careful insider would
                db.execute(REHASH_SQL, (prev.strip(), int(sid)))
                prev = db.scalar("SELECT ROW_HASH FROM AGENT_STEPS WHERE STEP_ID = ?", (int(sid),))
            chain = verify_audit_chain(db)
            anchored = check_anchor(db, anchor)
        finally:
            ibm_db.rollback(db.conn)
            ibm_db.autocommit(db.conn, ibm_db.SQL_AUTOCOMMIT_ON)
        restored = check_anchor(db, anchor)
    finally:
        db.close()
    return {"step_id": int(step_id), "rehashed": len(ids), "chain_after_rebuild": chain,
            "anchor_after_rebuild": anchored, "anchor_after_rollback": restored}
