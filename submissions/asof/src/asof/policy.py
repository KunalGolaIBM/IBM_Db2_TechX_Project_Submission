"""Policy changes, change impact, the policy timeline and analytics.

Policy changes go through APPLY_POLICY_CHANGE on the editor connection only: the editor
user holds no UPDATE privilege, and the runtime user cannot call the procedure.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import date
from typing import Annotated, Any

import ibm_db
import ibm_db_dbi
from langchain_core.embeddings import Embeddings
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from . import db
from .corpus import OPEN_END
from .embeddings import clause_embedding_text

MAX_RULE_BYTES = 2000
log = logging.getLogger(__name__)


def _bytes(limit: int) -> Callable[[str], str]:
    def check(v: str) -> str:
        if len(v.encode("utf-8")) > limit:
            raise ValueError(f"must be at most {limit} bytes in UTF-8")
        return v
    return check


class PolicyChange(BaseModel):
    """A new version of one clause for a business-time period."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    clause_id: str = Field(pattern=r"^[A-Z]{3}-[0-9]{3}$")
    effective_from: date
    effective_to: date | None = Field(None, description="Exclusive end date; omit for open-ended")
    version_label: str = Field(pattern=r"^v[0-9]{1,3}$")
    clause_text: Annotated[str, Field(min_length=10, max_length=4000), AfterValidator(_bytes(4000))]
    rule: dict[str, Any]
    change_note: Annotated[str, Field(min_length=3, max_length=400), AfterValidator(_bytes(400))]

    @field_validator("effective_from", "effective_to")
    @classmethod
    def _sane(cls, v: date | None) -> date | None:
        if v is not None and not date(2020, 1, 1) <= v <= OPEN_END:
            raise ValueError("date out of range")
        return v

    @field_validator("rule")
    @classmethod
    def _flat_rule(cls, rule: dict[str, Any]) -> dict[str, Any]:
        for key, value in rule.items():
            if not (isinstance(key, str) and key.replace("_", "").isalnum() and len(key) <= 60):
                raise ValueError(f"invalid rule key {key!r}")
            ok = isinstance(value, (bool, int, float, str)) or (
                isinstance(value, list) and all(isinstance(x, (str, int, float)) for x in value))
            if key == "applies_when":
                ok = isinstance(value, dict)
            if not ok:
                raise ValueError(f"rule value for {key!r} must be a number, boolean, string or list")
        if len(json.dumps(rule).encode("utf-8")) > MAX_RULE_BYTES:
            raise ValueError(f"rule must be at most {MAX_RULE_BYTES} bytes as JSON")
        return rule

    @property
    def end(self) -> date:
        return self.effective_to or OPEN_END


def apply_change(conn: ibm_db_dbi.Connection, change: PolicyChange, embeddings: Embeddings | None,
                 schema: str = db.SCHEMA, in_db: bool | None = None, commit: bool = True) -> dict[str, Any]:
    """Apply a change as the connected user (the editor). Commits.

    The new version's embedding is made by Db2 itself inside APPLY_POLICY_CHANGE when the
    in-database model is registered (in_db=None means: use it if it exists), otherwise here.
    Returns rows split, help-centre answers flagged, and where the embedding was made.
    """
    if change.end <= change.effective_from:
        raise ValueError("effective_to must be after effective_from")
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_CLAUSE_TITLE, (change.clause_id,))
    if not rows:
        raise ValueError(f"unknown clause {change.clause_id}")
    if in_db is None:
        in_db = db.query(conn, SQL_EMBEDDER_EXISTS)[0][0] > 0
    if not in_db and embeddings is None:
        raise ValueError("no in-database embedding model, so a local embeddings model is required")

    def local_vector() -> str:
        if embeddings is None:
            raise ValueError("no local embeddings model to fall back on")
        return db.vector_literal(embeddings.embed_query(clause_embedding_text(rows[0][0], change.clause_text)))

    def call(vector: str | None) -> list[Any]:
        cur = conn.cursor()
        try:
            out = cur.callproc("APPLY_POLICY_CHANGE", (
                change.clause_id, change.effective_from, change.end, change.version_label, change.clause_text,
                json.dumps(change.rule, sort_keys=True), vector, change.change_note, 0, 0))
            if commit:
                conn.commit()
            return list(out)
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            raise db.wrap_error(exc, "APPLY_POLICY_CHANGE failed") from None
        finally:
            cur.close()

    embedded_in = "db2" if in_db else "app"
    try:
        out = call(None if in_db else local_vector())
    except db.DatabaseError as exc:
        # 75014: the in-database model failed (endpoint down, key revoked). The change still goes
        # through, with the same model run here; the response says so.
        if not (in_db and exc.sqlstate == "75014" and embeddings is not None):
            raise
        log.warning("in-database embedding failed for %s; embedding locally instead", change.clause_id)
        out, embedded_in = call(local_vector()), "app (Db2 model unavailable)"
    return {"rows_changed": int(out[8]), "published_flagged": int(out[9]), "embedded_in": embedded_in}


def preview_change(conn: ibm_db_dbi.Connection, change: PolicyChange, embeddings: Embeddings | None,
                   schema: str = db.SCHEMA) -> dict[str, Any]:
    """What a change would do, without making it.

    APPLY_POLICY_CHANGE and CHANGE_IMPACT run in one transaction, which is then rolled back: the
    impact is read from Db2's own view of the changed policy, and afterwards there is no new version,
    no history row and no flagged help-centre answer. The caller's connection must not autocommit.
    """
    if ibm_db.autocommit(conn.conn_handler):
        raise ValueError("a preview needs a connection without autocommit, or the change would be saved")
    try:
        applied = apply_change(conn, change, embeddings, schema, commit=False)
        impact = change_impact(conn, change.clause_id, schema)
    finally:
        try:
            conn.rollback()
        except Exception as exc:  # noqa: BLE001 - closing the connection then rolls the transaction back
            raise db.wrap_error(exc, "The preview could not be rolled back; close this connection") from None
    return applied | {"impact": impact, "preview": True}


SQL_PUBLISHED = ("SELECT ANSWER_ID, DOC_ID, QUESTION, ANSWER_TEXT, CITED_CLAUSE_ID, CITED_VERSION, APPLIES_FROM, "
                 "APPLIES_TO, STATUS FROM PUBLISHED_ANSWER WHERE ANSWER_ID = ?")
SQL_SUGGESTIONS = ("SELECT SUGGESTION_ID, ANSWER_ID, CLAUSE_ID, STALE_FROM, BASED_ON_VERSION, SUGGESTED_TEXT, "
                   "CHECK_DECISION, CHECK_LEDGER_ID, AGENT_TRACE, STATUS, CREATED_AT, CREATED_BY, DECIDED_AT, DECIDED_BY "
                   "FROM ANSWER_SUGGESTION WHERE (CAST(? AS VARCHAR(32)) IS NULL OR CLAUSE_ID = CAST(? AS VARCHAR(32))) "
                   "ORDER BY SUGGESTION_ID DESC FETCH FIRST 100 ROWS ONLY")
_SUGGESTION_KEYS = ("suggestion_id", "answer_id", "clause_id", "stale_from", "based_on_version", "text", "check_decision",
                    "check_ledger_id", "agent_trace", "status", "created_at", "created_by", "decided_at", "decided_by")
_PUBLISHED_KEYS = ("answer_id", "doc_id", "question", "answer_text", "cited_clause_id", "cited_version",
                   "applies_from", "applies_to", "status")


def published_answer(conn: ibm_db_dbi.Connection, answer_id: str, schema: str = db.SCHEMA) -> dict[str, Any] | None:
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_PUBLISHED, (answer_id,))
    if not rows:
        return None
    return {k: (v.strip() if isinstance(v, str) and k in ("status", "answer_id") else v)
            for k, v in zip(_PUBLISHED_KEYS, rows[0], strict=True)}


def add_suggestion(conn: ibm_db_dbi.Connection, answer_id: str, clause_id: str, stale_from: date, version: str,
                   text: str, decision: str, ledger_id: int | None, trace: list[dict[str, Any]],
                   schema: str = db.SCHEMA) -> int:
    """Store a drafted correction through ADD_SUGGESTION (the runtime user holds EXECUTE only). Commits."""
    db.use_schema(conn, schema)
    trace_json = json.dumps(trace[:12], default=str)[:8000]
    cur = conn.cursor()
    try:
        out = cur.callproc("ADD_SUGGESTION", (answer_id, clause_id, stale_from, version, text[:4000], decision,
                                               int(ledger_id or 0), trace_json, 0))  # ibm_db binds None badly here
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise db.wrap_error(exc, "ADD_SUGGESTION failed") from None
    finally:
        cur.close()
    return int(out[8])


def suggestions(conn: ibm_db_dbi.Connection, clause_id: str | None = None, schema: str = db.SCHEMA) -> list[dict[str, Any]]:
    db.use_schema(conn, schema)
    out = []
    for r in db.query(conn, SQL_SUGGESTIONS, (clause_id, clause_id)):
        d = dict(zip(_SUGGESTION_KEYS, r, strict=True))
        d["agent_trace"] = json.loads(d["agent_trace"])
        for k in ("status", "check_decision", "created_by", "decided_by"):
            d[k] = d[k].strip() if isinstance(d[k], str) else d[k]
        out.append(d)
    return out


def decide_suggestion(conn: ibm_db_dbi.Connection, suggestion_id: int, approve: bool, schema: str = db.SCHEMA) -> str:
    """Approve (publish) or reject a suggestion, as the editor. Returns the published answer ID ('' on reject)."""
    db.use_schema(conn, schema)
    cur = conn.cursor()
    try:
        out = cur.callproc("DECIDE_SUGGESTION", (int(suggestion_id), 1 if approve else 0, " " * 32))
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise db.wrap_error(exc, "DECIDE_SUGGESTION failed") from None
    finally:
        cur.close()
    return str(out[2]).strip()


_IMPACT_KEYS = ("kind", "ref_id", "for_from", "for_to", "state", "created_at", "cited_version", "current_version",
                "status", "stale_from")


def change_impact(conn: ibm_db_dbi.Connection, clause_id: str, schema: str = db.SCHEMA) -> list[dict[str, Any]]:
    db.use_schema(conn, schema)
    cur = conn.cursor()
    try:
        cur.callproc("CHANGE_IMPACT", (clause_id,))
        rows = cur.fetchall() or []
    except Exception as exc:  # noqa: BLE001
        raise db.wrap_error(exc, "CHANGE_IMPACT failed") from None
    finally:
        cur.close()
    out = []
    for r in rows:
        d = dict(zip(_IMPACT_KEYS, r, strict=True))
        for k in ("kind", "ref_id", "state", "cited_version", "current_version", "status"):
            d[k] = d[k].strip() if isinstance(d[k], str) else d[k]
        out.append(d)
    return out


_TIMELINE_KEYS = ("clause_id", "doc_id", "area", "title", "version_label", "bus_start", "bus_end", "changed_by", "change_note",
                  "sys_start", "clause_text", "rule_json", "first_bag_fee_usd", "second_bag_fee_usd", "change_fee_usd",
                  "pet_fee_usd", "cancellation_fee_usd", "compensation_usd", "discount_pct", "request_window_days",
                  "free_cancel_window_hours", "min_days_before_departure", "credit_validity_months", "max_passengers",
                  "retroactive_allowed", "transfer_allowed", "changes_allowed")

# Every statement below is a literal. Names are unqualified: db.use_schema() binds the schema.
SQL_CLAUSE_TITLE = "SELECT TITLE FROM POLICY_CLAUSE WHERE CLAUSE_ID = ? FETCH FIRST 1 ROW ONLY"
SQL_EMBEDDER_EXISTS = ("SELECT COUNT(*) FROM SYSCAT.EXTERNALMODELS WHERE MODELSCHEMA = CURRENT SCHEMA "
                       "AND MODELNAME = 'EMBEDDER'")
SQL_TIMELINE = ("SELECT CLAUSE_ID, DOC_ID, AREA, TITLE, VERSION_LABEL, BUS_START, BUS_END, CHANGED_BY, CHANGE_NOTE, "
                "SYS_START, CLAUSE_TEXT, RULE_JSON, FIRST_BAG_FEE_USD, SECOND_BAG_FEE_USD, CHANGE_FEE_USD, PET_FEE_USD, "
                "CANCELLATION_FEE_USD, COMPENSATION_USD, DISCOUNT_PCT, REQUEST_WINDOW_DAYS, FREE_CANCEL_WINDOW_HOURS, "
                "MIN_DAYS_BEFORE_DEPARTURE, CREDIT_VALIDITY_MONTHS, MAX_PASSENGERS, RETROACTIVE_ALLOWED, "
                "TRANSFER_ALLOWED, CHANGES_ALLOWED FROM V_POLICY_TIMELINE ORDER BY CLAUSE_ID, BUS_START")
SQL_HISTORY = ("SELECT VERSION_LABEL, BUS_START, BUS_END, SYS_START, SYS_END, CHANGED_BY, CHANGE_NOTE, CLAUSE_TEXT "
               "FROM POLICY_CLAUSE FOR SYSTEM_TIME FROM ? TO ? WHERE CLAUSE_ID = ? ORDER BY SYS_START, BUS_START")
# Weighted by the number of decisions in each group, not an average of averages.
SQL_DECISIONS = ("SELECT DECISION, SUM(DECISIONS), INTEGER(SUM(AVG_LATENCY_MS * DECISIONS) / NULLIF(SUM(DECISIONS), 0)) "
                 "FROM V_DECISION_STATS GROUP BY DECISION")
# Decisions made in replay mode (no model time in their latency), so the screen can say so.
SQL_REPLAYED = "SELECT COUNT(*) FROM ANSWER_LEDGER WHERE MODEL_INFO LIKE 'replay:%'"
SQL_REASONS = "SELECT REASON_CODE, SUM(DECISIONS) FROM V_DECISION_STATS GROUP BY REASON_CODE ORDER BY 2 DESC"
SQL_AREAS = ("SELECT AREA, SUPPORTED, CONTRADICTED, NOT_COVERED, CLAIMS FROM V_CLAIM_OUTCOMES_BY_AREA "
             "ORDER BY CLAIMS DESC")
SQL_OVERRIDES = ("SELECT LEDGER_ID, AS_OF_DATE, CLAIM_TEXT, CLAUSE_ID, CLAUSE_VERSION FROM V_RULE_OVERRIDES "
                 "ORDER BY LEDGER_ID DESC FETCH FIRST 20 ROWS ONLY")
# What the deterministic rule check said about every claim in a draft (pass 1), next to the judge's verdict.
SQL_RULE_CHECKS = ("SELECT RULE_CHECK, COALESCE(LLM_VERDICT, 'NONE'), COUNT(*) FROM CLAIM_CITATION "
                   "WHERE PASS_NO = 1 GROUP BY RULE_CHECK, COALESCE(LLM_VERDICT, 'NONE')")


def timeline(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA, doc_id: str | None = None) -> list[dict[str, Any]]:
    """Every clause (of one document, if given) with its versions in business-time order, key parameters
    from RULE_JSON."""
    db.use_schema(conn, schema)
    keys = list(_TIMELINE_KEYS)
    rows = db.query(conn, SQL_TIMELINE)
    clauses: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(zip(keys, r, strict=True))
        if doc_id and d["doc_id"] != doc_id:
            continue
        params = {k: (float(d[k]) if hasattr(d[k], "is_finite") else d[k]) for k in keys[12:] if d[k] is not None}
        c = clauses.setdefault(d["clause_id"], {"clause_id": d["clause_id"], "doc_id": d["doc_id"], "area": d["area"],
                                                "title": d["title"], "versions": []})
        c["title"] = d["title"]
        c["versions"].append({"version": d["version_label"], "from": d["bus_start"], "to": d["bus_end"],
                              "changed_by": d["changed_by"].strip(), "change_note": d["change_note"],
                              "recorded_at": d["sys_start"], "text": d["clause_text"],
                              "rule": json.loads(d["rule_json"]), "params": params})
    return list(clauses.values())


def history(conn: ibm_db_dbi.Connection, clause_id: str, schema: str = db.SCHEMA) -> list[dict[str, Any]]:
    """Every row this database has ever held for a clause (FOR SYSTEM_TIME FROM ... TO ...)."""
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_HISTORY, ("0001-01-01-00.00.00", "9999-12-30-00.00.00", clause_id))
    keys = ("version", "from", "to", "recorded_at", "superseded_at", "changed_by", "change_note", "text")
    out = []
    for r in rows:
        d = dict(zip(keys, r, strict=True))
        d["changed_by"] = d["changed_by"].strip()
        d["current"] = d["superseded_at"].year >= 9999
        out.append(d)
    return out


def analytics(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA) -> dict[str, Any]:
    db.use_schema(conn, schema)
    decisions = db.query(conn, SQL_DECISIONS)
    reasons = db.query(conn, SQL_REASONS)
    areas = db.query(conn, SQL_AREAS)
    overrides = db.query(conn, SQL_OVERRIDES)
    replayed = int(db.query(conn, SQL_REPLAYED)[0][0])
    rule_checks = {"match": 0, "mismatch": 0, "mismatch_judge_agreed": 0, "not_applicable": 0}
    for status, judged, n in db.query(conn, SQL_RULE_CHECKS):
        key = status.strip().lower()
        if key in rule_checks:
            rule_checks[key] += int(n)
        if key == "mismatch" and judged.strip() == "CONTRADICTED":
            rule_checks["mismatch_judge_agreed"] += int(n)
    return {
        "replayed_decisions": replayed,
        "decisions": [{"decision": d.strip(), "count": int(n), "avg_latency_ms": int(lat or 0)} for d, n, lat in decisions],
        "reasons": [{"reason": r.strip(), "count": int(n)} for r, n in reasons],
        "areas": [{"area": a.strip(), "supported": int(s), "contradicted": int(c), "not_covered": int(nc), "claims": int(t)}
                  for a, s, c, nc, t in areas],
        "rule_overrides": [{"ledger_id": int(i), "as_of_date": d, "claim": t, "clause_id": c, "version": v}
                           for i, d, t, c, v in overrides],
        "rule_checks": rule_checks,
    }
