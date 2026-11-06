"""Policy changes, change impact, the policy timeline and analytics.

Policy changes go through APPLY_POLICY_CHANGE on the editor connection only: the editor
user holds no UPDATE privilege, and the runtime user cannot call the procedure.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Annotated, Any

import ibm_db_dbi
from langchain_core.embeddings import Embeddings
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from . import db
from .corpus import OPEN_END
from .embeddings import clause_embedding_text

MAX_RULE_BYTES = 2000
log = logging.getLogger(__name__)


def _bytes(limit: int):
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
                 schema: str = db.SCHEMA, in_db: bool | None = None) -> dict[str, Any]:
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
        return db.vector_literal(embeddings.embed_query(clause_embedding_text(rows[0][0], change.clause_text)))

    def call(vector: str | None) -> list:
        cur = conn.cursor()
        try:
            out = cur.callproc("APPLY_POLICY_CHANGE", (
                change.clause_id, change.effective_from, change.end, change.version_label, change.clause_text,
                json.dumps(change.rule, sort_keys=True), vector, change.change_note, 0, 0))
            conn.commit()
            return out
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


_TIMELINE_KEYS = ("clause_id", "area", "title", "version_label", "bus_start", "bus_end", "changed_by", "change_note",
                  "sys_start", "clause_text", "rule_json", "first_bag_fee_usd", "second_bag_fee_usd", "change_fee_usd",
                  "pet_fee_usd", "cancellation_fee_usd", "compensation_usd", "discount_pct", "request_window_days",
                  "free_cancel_window_hours", "min_days_before_departure", "credit_validity_months", "max_passengers",
                  "retroactive_allowed", "transfer_allowed", "changes_allowed")

# Every statement below is a literal. Names are unqualified: db.use_schema() binds the schema.
SQL_CLAUSE_TITLE = "SELECT TITLE FROM POLICY_CLAUSE WHERE CLAUSE_ID = ? FETCH FIRST 1 ROW ONLY"
SQL_EMBEDDER_EXISTS = ("SELECT COUNT(*) FROM SYSCAT.EXTERNALMODELS WHERE MODELSCHEMA = CURRENT SCHEMA "
                       "AND MODELNAME = 'EMBEDDER'")
SQL_TIMELINE = ("SELECT CLAUSE_ID, AREA, TITLE, VERSION_LABEL, BUS_START, BUS_END, CHANGED_BY, CHANGE_NOTE, SYS_START, "
                "CLAUSE_TEXT, RULE_JSON, FIRST_BAG_FEE_USD, SECOND_BAG_FEE_USD, CHANGE_FEE_USD, PET_FEE_USD, "
                "CANCELLATION_FEE_USD, COMPENSATION_USD, DISCOUNT_PCT, REQUEST_WINDOW_DAYS, FREE_CANCEL_WINDOW_HOURS, "
                "MIN_DAYS_BEFORE_DEPARTURE, CREDIT_VALIDITY_MONTHS, MAX_PASSENGERS, RETROACTIVE_ALLOWED, "
                "TRANSFER_ALLOWED, CHANGES_ALLOWED FROM V_POLICY_TIMELINE ORDER BY CLAUSE_ID, BUS_START")
SQL_HISTORY = ("SELECT VERSION_LABEL, BUS_START, BUS_END, SYS_START, SYS_END, CHANGED_BY, CHANGE_NOTE, CLAUSE_TEXT "
               "FROM POLICY_CLAUSE FOR SYSTEM_TIME FROM ? TO ? WHERE CLAUSE_ID = ? ORDER BY SYS_START, BUS_START")
SQL_DECISIONS = ("SELECT DECISION, SUM(DECISIONS), INTEGER(AVG(AVG_LATENCY_MS)) FROM V_DECISION_STATS "
                 "GROUP BY DECISION")
SQL_REASONS = "SELECT REASON_CODE, SUM(DECISIONS) FROM V_DECISION_STATS GROUP BY REASON_CODE ORDER BY 2 DESC"
SQL_AREAS = ("SELECT AREA, SUPPORTED, CONTRADICTED, NOT_COVERED, CLAIMS FROM V_CLAIM_OUTCOMES_BY_AREA "
             "ORDER BY CLAIMS DESC")
SQL_OVERRIDES = ("SELECT LEDGER_ID, AS_OF_DATE, CLAIM_TEXT, CLAUSE_ID, CLAUSE_VERSION FROM V_RULE_OVERRIDES "
                 "ORDER BY LEDGER_ID DESC FETCH FIRST 20 ROWS ONLY")


def timeline(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA) -> list[dict[str, Any]]:
    """Every clause with its versions in business-time order, key parameters from RULE_JSON."""
    db.use_schema(conn, schema)
    keys = list(_TIMELINE_KEYS)
    rows = db.query(conn, SQL_TIMELINE)
    clauses: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(zip(keys, r, strict=True))
        params = {k: (float(d[k]) if hasattr(d[k], "is_finite") else d[k]) for k in keys[11:] if d[k] is not None}
        c = clauses.setdefault(d["clause_id"], {"clause_id": d["clause_id"], "area": d["area"], "title": d["title"],
                                                "versions": []})
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
    return {
        "decisions": [{"decision": d.strip(), "count": int(n), "avg_latency_ms": int(lat or 0)} for d, n, lat in decisions],
        "reasons": [{"reason": r.strip(), "count": int(n)} for r, n in reasons],
        "areas": [{"area": a.strip(), "supported": int(s), "contradicted": int(c), "not_covered": int(nc), "claims": int(t)}
                  for a, s, c, nc, t in areas],
        "rule_overrides": [{"ledger_id": int(i), "as_of_date": d, "claim": t, "clause_id": c, "version": v}
                           for i, d, t, c, v in overrides],
    }
