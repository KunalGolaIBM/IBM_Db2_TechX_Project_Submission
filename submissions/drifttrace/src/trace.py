"""Lineage trace: instrument -> inspection -> lot -> shipment, plus the transactional case save.

Pure functions (classify, aggregate, apply_bound, fingerprint) are unit-tested without Db2.
Db2 functions take an open connection and use only bound parameters.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from models import (
    CROSSES,
    INSUFFICIENT_DATA,
    OUTSIDE_SCOPE,
    REVIEW_SCOPE,
    SUPPORTED_UNIT,
    WITHIN,
    Finding,
    InspectionFact,
    Scope,
    Shipment,
    Totals,
)

TS_FMT = "%Y-%m-%d %H:%M UTC"

# Server-side input limits (the UI enforces the same; save_case re-checks).
MAX_NOTICE_CHARS = 8000
MAX_RATIONALE_CHARS = 1000
MAX_BOUND_MM = Decimal("1.000")


class InputError(ValueError):
    """A draft violates server-side input limits."""


def check_limits(notice: str, rationale: str, bound: Optional[Decimal]) -> None:
    if not notice or len(notice) > MAX_NOTICE_CHARS:
        raise InputError(f"Notice must be 1-{MAX_NOTICE_CHARS} characters.")
    if not rationale or not rationale.strip() or len(rationale) > MAX_RATIONALE_CHARS:
        raise InputError(f"Window rationale must be 1-{MAX_RATIONALE_CHARS} characters.")
    if bound is not None and not (Decimal("0") <= bound <= MAX_BOUND_MM):
        raise InputError(f"Hypothetical bound must be between 0 and {MAX_BOUND_MM} mm.")


class StalePreviewError(RuntimeError):
    """Operational data changed between preview and save; the user must refresh."""


def to_utc_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def fmt_ts(dt: Optional[datetime]) -> str:
    return dt.strftime(TS_FMT) if dt else "missing"


def dec(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(value).strip())


# ---------------- pure logic ----------------

def classify(fact: InspectionFact, scope: Scope) -> tuple[str, str]:
    """Return (classification, reason). Outside scope means 'not this case', never 'safe'."""
    if fact.instrument_id is None:
        return INSUFFICIENT_DATA, "Instrument identity is missing; cannot confirm whether the failed instrument was used."
    if fact.instrument_id != scope.instrument_id:  # exact match only, never fuzzy
        return OUTSIDE_SCOPE, (
            f"Measured with a different instrument ({fact.instrument_id}); this case concerns {scope.instrument_id}. "
            "Not evaluated by this case."
        )
    if fact.function_code is None:
        return INSUFFICIENT_DATA, "Measurement function is missing; cannot confirm it matches the failed check."
    if fact.function_code != scope.function_code:
        return OUTSIDE_SCOPE, (
            f"Different measurement function ({fact.function_code}); this case concerns {scope.function_code}."
        )
    if fact.measured_at is None:
        return INSUFFICIENT_DATA, (
            f"Measured with {scope.instrument_id} but the measurement timestamp is missing; "
            "cannot place it inside or outside the review window."
        )
    missing = [
        name
        for name, val in (
            ("unit", fact.unit),
            ("recorded value", fact.recorded_value),
            ("lower limit", fact.lower_limit),
            ("upper limit", fact.upper_limit),
        )
        if val is None
    ]
    if missing:
        return INSUFFICIENT_DATA, f"Potentially relevant but missing: {', '.join(missing)}."
    if fact.unit != scope.unit:
        return INSUFFICIENT_DATA, f"Recorded in unsupported unit '{fact.unit}'; case scope is {scope.unit}."
    at = to_utc_naive(fact.measured_at)
    start, end = to_utc_naive(scope.review_start), to_utc_naive(scope.review_end)
    if at < start:
        return OUTSIDE_SCOPE, f"Measured {fmt_ts(at)}, before the confirmed review start {fmt_ts(start)}."
    if at > end:
        return OUTSIDE_SCOPE, f"Measured {fmt_ts(at)}, after the confirmed review end {fmt_ts(end)}."
    return REVIEW_SCOPE, (
        f"Measured with {scope.instrument_id} ({scope.function_code}) at {fmt_ts(at)}, inside the confirmed "
        f"window {fmt_ts(start)} to {fmt_ts(end)} (inclusive)."
    )


def apply_bound(finding: Finding, bound: Optional[Decimal]) -> None:
    """Illustrative sensitivity analysis only. Never changes classification."""
    finding.hypothetical = None
    finding.hypothetical_interval = None
    f = finding.fact
    if bound is None or finding.classification != REVIEW_SCOPE:
        return
    if bound < 0:
        raise ValueError("Bound must be >= 0")
    low, high = f.recorded_value - bound, f.recorded_value + bound
    finding.hypothetical_interval = (low, high)
    finding.hypothetical = CROSSES if (low < f.lower_limit or high > f.upper_limit) else WITHIN


def build_findings(
    facts: list[InspectionFact], shipments: list[Shipment], scope: Scope, bound: Optional[Decimal] = None
) -> list[Finding]:
    by_lot: dict[str, list[Shipment]] = {}
    for s in shipments:
        by_lot.setdefault(s.lot_id, []).append(s)
    findings = []
    for fact in sorted(facts, key=lambda x: x.inspection_id):
        cls, reason = classify(fact, scope)
        fd = Finding(fact=fact, classification=cls, reason=reason, shipments=sorted(by_lot.get(fact.lot_id, []), key=lambda s: s.shipment_id))
        apply_bound(fd, bound)
        findings.append(fd)
    return findings


def aggregate(findings: list[Finding]) -> Totals:
    """Distinct lots/shipments so multiple inspections per lot never multiply quantities."""
    def lots_for(cls: str) -> dict[str, Finding]:
        out: dict[str, Finding] = {}
        for fd in findings:
            if fd.classification == cls:
                out.setdefault(fd.fact.lot_id, fd)
        return out

    review = lots_for(REVIEW_SCOPE)
    insufficient = {k: v for k, v in lots_for(INSUFFICIENT_DATA).items() if k not in review}

    def ships(lots: dict[str, Finding]) -> dict[str, Shipment]:
        out: dict[str, Shipment] = {}
        for fd in lots.values():
            for s in fd.shipments:
                out[s.shipment_id] = s
        return out

    r_ships = ships(review)
    i_ships = ships(insufficient)
    produced = sum(fd.fact.produced_quantity or 0 for fd in review.values())
    unshipped = 0
    for lot_id, fd in review.items():
        shipped_lot = sum(s.shipped_quantity for s in r_ships.values() if s.lot_id == lot_id)
        unshipped += max((fd.fact.produced_quantity or 0) - shipped_lot, 0)
    return Totals(
        review_lots=sorted(review),
        review_shipments=sorted(r_ships),
        review_shipped_units=sum(s.shipped_quantity for s in r_ships.values()),
        review_unshipped_units=unshipped,
        review_produced_units=produced,
        insufficient_lots=sorted(insufficient),
        insufficient_shipments=sorted(i_ships),
        insufficient_shipped_units=sum(s.shipped_quantity for s in i_ships.values()),
        outside_inspections=sum(1 for fd in findings if fd.classification == OUTSIDE_SCOPE),
    )


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, datetime):
        return to_utc_naive(v).isoformat() + "Z"
    return v


def fact_dict(fact: InspectionFact) -> dict[str, Any]:
    return {k: _jsonable(v) for k, v in asdict(fact).items()}


def ship_dict(s: Shipment) -> dict[str, Any]:
    return {k: _jsonable(v) for k, v in asdict(s).items()}


def fingerprint(facts: list[InspectionFact], shipments: list[Shipment]) -> str:
    canon = {
        "facts": sorted((fact_dict(f) for f in facts), key=lambda d: d["inspection_id"]),
        "shipments": sorted((ship_dict(s) for s in shipments), key=lambda d: d["shipment_id"]),
    }
    return hashlib.sha256(json.dumps(canon, sort_keys=True).encode()).hexdigest()


def finding_snapshot(fd: Finding, bound: Optional[Decimal]) -> dict[str, Any]:
    return {
        "inspection": fact_dict(fd.fact),
        "classification": fd.classification,
        "reason": fd.reason,
        "linked_shipments": [ship_dict(s) for s in fd.shipments],
        "hypothetical_bound_mm": str(bound) if bound is not None else None,
        "hypothetical_interval_mm": [str(x) for x in fd.hypothetical_interval] if fd.hypothetical_interval else None,
        "hypothetical_result": fd.hypothetical,
        "note": "Hypothetical result is illustrative sensitivity analysis; historical error is not established.",
    }


# ---------------- Db2 access ----------------

FACTS_SQL = """
SELECT i.ID AS INSPECTION_ID, i.INSTRUMENT_ID, ins.NAME AS INSTRUMENT_NAME, i.LOT_ID,
       l.PRODUCT_NAME, l.PRODUCED_QUANTITY, i.MEASURED_AT, i.FUNCTION_CODE, i.UNIT,
       i.RECORDED_VALUE, i.LOWER_LIMIT, i.UPPER_LIMIT, i.ORIGINAL_DECISION
FROM DT_INSPECTIONS i
LEFT JOIN DT_INSTRUMENTS ins ON ins.ID = i.INSTRUMENT_ID
LEFT JOIN DT_LOTS l ON l.ID = i.LOT_ID
WHERE i.INSTRUMENT_ID = ? OR i.FUNCTION_CODE = ?
ORDER BY i.ID
"""

SHIPMENTS_SQL = """
SELECT s.ID AS SHIPMENT_ID, s.LOT_ID, s.CUSTOMER_NAME, s.SHIPPED_QUANTITY, s.SHIPPED_AT
FROM DT_SHIPMENTS s
WHERE s.LOT_ID IN (
  SELECT DISTINCT i.LOT_ID FROM DT_INSPECTIONS i WHERE i.INSTRUMENT_ID = ? OR i.FUNCTION_CODE = ?
)
ORDER BY s.ID
"""


def fetch_instruments(conn: Any) -> list[dict[str, Any]]:
    from db import query
    return query(conn, "SELECT ID, NAME, LAST_VERIFIED_AT, VERIFICATION_REF FROM DT_INSTRUMENTS ORDER BY ID")


def fetch_trace_inputs(conn: Any, instrument_id: str, function_code: str) -> tuple[list[InspectionFact], list[Shipment]]:
    from db import query
    facts = [
        InspectionFact(
            inspection_id=r["INSPECTION_ID"],
            instrument_id=r["INSTRUMENT_ID"],
            instrument_name=r["INSTRUMENT_NAME"],
            lot_id=r["LOT_ID"],
            product_name=r["PRODUCT_NAME"],
            produced_quantity=r["PRODUCED_QUANTITY"],
            measured_at=r["MEASURED_AT"],
            function_code=r["FUNCTION_CODE"],
            unit=r["UNIT"],
            recorded_value=dec(r["RECORDED_VALUE"]),
            lower_limit=dec(r["LOWER_LIMIT"]),
            upper_limit=dec(r["UPPER_LIMIT"]),
            original_decision=r["ORIGINAL_DECISION"],
        )
        for r in query(conn, FACTS_SQL, (instrument_id, function_code))
    ]
    shipments = [
        Shipment(
            shipment_id=r["SHIPMENT_ID"],
            lot_id=r["LOT_ID"],
            customer_name=r["CUSTOMER_NAME"],
            shipped_quantity=int(r["SHIPPED_QUANTITY"]),
            shipped_at=r["SHIPPED_AT"],
        )
        for r in query(conn, SHIPMENTS_SQL, (instrument_id, function_code))
    ]
    return facts, shipments


def db2_crosscheck(conn: Any, totals: Totals) -> dict[str, Any]:
    """Recompute review-lot exposure inside Db2 (DT_LOT_EXPOSURE_V) and compare with the app totals."""
    from db import query
    lots = totals.review_lots
    if not lots:
        return {"lots": 0, "shipped": 0, "unshipped": 0, "matches": True}
    placeholders = ",".join("?" for _ in lots)  # count only; values are bound
    row = query(
        conn,
        "SELECT COUNT(*) AS LOTS, COALESCE(SUM(SHIPPED_QUANTITY),0) AS SHIPPED, "
        "COALESCE(SUM(CASE WHEN PRODUCED_QUANTITY > SHIPPED_QUANTITY THEN PRODUCED_QUANTITY - SHIPPED_QUANTITY ELSE 0 END),0) AS UNSHIPPED, "
        "COALESCE(SUM(SHIPMENT_COUNT),0) AS SHIPMENTS "
        f"FROM DT_LOT_EXPOSURE_V WHERE LOT_ID IN ({placeholders})",  # nosec B608 - only '?' markers are interpolated
        lots,
    )[0]
    result = {"lots": int(row["LOTS"]), "shipments": int(row["SHIPMENTS"]), "shipped": int(row["SHIPPED"]), "unshipped": int(row["UNSHIPPED"])}
    result["matches"] = (result["lots"], result["shipments"], result["shipped"], result["unshipped"]) == (
        len(lots), len(totals.review_shipments), totals.review_shipped_units, totals.review_unshipped_units)
    return result


def run_trace(conn: Any, scope: Scope, bound: Optional[Decimal]) -> tuple[list[Finding], Totals, str]:
    facts, shipments = fetch_trace_inputs(conn, scope.instrument_id, scope.function_code)
    findings = build_findings(facts, shipments, scope, bound)
    return findings, aggregate(findings), fingerprint(facts, shipments)


def find_case_by_submission(conn: Any, client_submission_id: str) -> Optional[str]:
    from db import query
    rows = query(conn, "SELECT ID FROM DT_CASES WHERE CLIENT_SUBMISSION_ID = ?", (client_submission_id,))
    return rows[0]["ID"] if rows else None


def save_case(
    draft: dict[str, Any],
    connect_fn: Optional[Callable[..., Any]] = None,
    _fail_after_findings: bool = False,
) -> tuple[str, bool]:
    """Persist case + finding snapshots + audit event in ONE transaction.

    Returns (case_id, created). A repeated client_submission_id returns the existing case.
    Raises StalePreviewError if operational data no longer matches the previewed fingerprint.
    """
    import ibm_db
    from db import connect, execute, query

    connect_fn = connect_fn or connect
    scope: Scope = draft["scope"]
    bound: Optional[Decimal] = draft.get("bound")
    sub_id: str = draft["client_submission_id"]
    check_limits(draft.get("notice_text", ""), draft.get("rationale", ""), bound)

    with connect_fn(autocommit=False) as conn:
        existing = find_case_by_submission(conn, sub_id)
        if existing:
            return existing, False
        findings, totals, fp = run_trace(conn, scope, bound)
        if fp != draft["preview_fingerprint"]:
            raise StalePreviewError("Operational records changed since the preview. Refresh the trace before saving.")
        crosscheck = db2_crosscheck(conn, totals)
        if not crosscheck["matches"]:
            raise RuntimeError("Db2 aggregate cross-check disagrees with application totals; not saving.")
        db_user = query(conn, "SELECT SESSION_USER AS U FROM SYSIBM.SYSDUMMY1")[0]["U"].strip()
        case_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
        scope_doc = {
            "instrument_id": scope.instrument_id,
            "function_code": scope.function_code,
            "unit": scope.unit,
            "review_start": _jsonable(scope.review_start),
            "review_end": _jsonable(scope.review_end),
            "window_rationale": draft.get("rationale", ""),
            "assumption_bound_mm": str(bound) if bound is not None else None,
            "assumption_accepted": bool(draft.get("bound_accepted")),
            "intake_mode": draft.get("intake_mode"),
            "provider": draft.get("provider"),
            "model": draft.get("model"),
            "data_fingerprint": fp,
            "totals": asdict(totals),
            "db2_crosscheck": crosscheck,
            "limitations": [
                "Review worklist only; no defect, safety or release determination.",
                "Totals cover recorded Db2 data only.",
                "Hypothetical bound is illustrative; historical error is not established.",
            ],
        }
        try:
            execute(
                conn,
                "INSERT INTO DT_CASES (ID, CLIENT_SUBMISSION_ID, NOTICE_TEXT, EXTRACTED_JSON, INSTRUMENT_ID, FUNCTION_CODE, "
                "REVIEW_START, REVIEW_END, ASSUMPTION_BOUND, SCOPE_JSON, CREATED_AT) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    case_id,
                    sub_id,
                    draft["notice_text"],
                    json.dumps(draft.get("extraction") or {}, sort_keys=True),
                    scope.instrument_id,
                    scope.function_code,
                    to_utc_naive(scope.review_start),
                    to_utc_naive(scope.review_end),
                    bound,
                    json.dumps(scope_doc, sort_keys=True),
                    now,
                ),
            )
            for fd in findings:
                execute(
                    conn,
                    "INSERT INTO DT_FINDINGS (CASE_ID, INSPECTION_ID, CLASSIFICATION, REASON, EVIDENCE_SNAPSHOT) VALUES (?,?,?,?,?)",
                    (case_id, fd.fact.inspection_id, fd.classification, fd.reason[:400],
                     json.dumps(finding_snapshot(fd, bound), sort_keys=True)),
                )
            if _fail_after_findings:
                raise RuntimeError("Forced failure after findings (test hook)")
            execute(
                conn,
                "INSERT INTO DT_AUDIT (ID, CASE_ID, EVENT_TYPE, DETAILS, CREATED_AT) VALUES (?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    case_id,
                    "CASE_CREATED",
                    json.dumps({
                        "client_submission_id": sub_id,
                        "findings": len(findings),
                        "review_scope": sum(1 for f in findings if f.classification == REVIEW_SCOPE),
                        "intake_mode": draft.get("intake_mode"),
                        "model": draft.get("model"),
                        "data_fingerprint": fp,
                        "db2_session_user": db_user,
                        "db2_crosscheck_matches": crosscheck["matches"],
                    }, sort_keys=True),
                    now,
                ),
            )
            ibm_db.commit(conn)
            return case_id, True
        except Exception as exc:
            ibm_db.rollback(conn)
            if "23505" in str(exc) or "23505" in (ibm_db.stmt_errormsg() or ""):
                again = find_case_by_submission(conn, sub_id)
                if again:
                    return again, False
            raise


def list_cases(conn: Any, limit: int = 20) -> list[dict[str, Any]]:
    from db import query
    return query(
        conn,
        "SELECT ID, CLIENT_SUBMISSION_ID, INSTRUMENT_ID, FUNCTION_CODE, REVIEW_START, REVIEW_END, ASSUMPTION_BOUND, CREATED_AT "
        "FROM DT_CASES ORDER BY CREATED_AT DESC FETCH FIRST ? ROWS ONLY",
        (int(limit),),
    )


def load_case(conn: Any, case_id: str) -> Optional[dict[str, Any]]:
    """Return the stored snapshot exactly as saved; nothing is recomputed."""
    from db import query
    rows = query(conn, "SELECT * FROM DT_CASES WHERE ID = ?", (case_id,))
    if not rows:
        return None
    case = rows[0]
    case["SCOPE"] = json.loads(case["SCOPE_JSON"])
    case["EXTRACTED"] = json.loads(case["EXTRACTED_JSON"])
    case["FINDINGS"] = [
        {**r, "SNAPSHOT": json.loads(r["EVIDENCE_SNAPSHOT"])}
        for r in query(conn, "SELECT INSPECTION_ID, CLASSIFICATION, REASON, EVIDENCE_SNAPSHOT FROM DT_FINDINGS WHERE CASE_ID = ? ORDER BY INSPECTION_ID", (case_id,))
    ]
    case["REVIEWS"] = query(
        conn, "SELECT ID, INSPECTION_ID, DISPOSITION, REMEASURED_VALUE, NOTE, REVIEWER, CREATED_AT FROM DT_REVIEW_EVENTS "
              "WHERE CASE_ID = ? ORDER BY CREATED_AT, ID", (case_id,))
    case["AUDIT"] = [
        {**r, "DETAILS": json.loads(r["DETAILS"])}
        for r in query(conn, "SELECT ID, EVENT_TYPE, DETAILS, CREATED_AT FROM DT_AUDIT WHERE CASE_ID = ? ORDER BY CREATED_AT", (case_id,))
    ]
    return case


# ---------------- review dispositions ----------------

DISPOSITIONS = {
    "REMEASURED_CONFORMS": "Re-measured with a verified instrument: within limits",
    "REMEASURED_NONCONFORMING": "Re-measured with a verified instrument: outside limits",
    "NOT_AVAILABLE_FOR_REMEASURE": "Parts not available to re-measure (e.g. shipped)",
    "REVIEWED_NO_FURTHER_ACTION": "Reviewed by manager; no further action recorded",
}
OPEN_CLASSES = (REVIEW_SCOPE, INSUFFICIENT_DATA)
MAX_NOTE_CHARS = 500
MAX_REVIEWER_CHARS = 80


def validate_disposition(disposition: str, value: Optional[Decimal], lower: Optional[Decimal],
                         upper: Optional[Decimal], note: str, reviewer: str) -> None:
    """Deterministic consistency: a re-measured verdict must agree with the stored spec limits."""
    if disposition not in DISPOSITIONS:
        raise InputError("Unknown disposition.")
    if not note.strip() or len(note) > MAX_NOTE_CHARS:
        raise InputError(f"Note must be 1-{MAX_NOTE_CHARS} characters.")
    if not reviewer.strip() or len(reviewer) > MAX_REVIEWER_CHARS:
        raise InputError(f"Reviewer must be 1-{MAX_REVIEWER_CHARS} characters.")
    remeasured = disposition.startswith("REMEASURED_")
    if remeasured != (value is not None):
        raise InputError("A re-measured value is required for re-measured dispositions and not allowed otherwise.")
    if remeasured:
        if lower is None or upper is None:
            raise InputError("Specification limits are missing for this inspection; record a non-measurement disposition.")
        within = lower <= value <= upper
        if within != (disposition == "REMEASURED_CONFORMS"):
            raise InputError(f"Re-measured value {value} is {'within' if within else 'outside'} limits {lower}-{upper}; "
                             "the disposition must match.")


def record_review(case_id: str, inspection_id: str, disposition: str, note: str, reviewer: str,
                  value: Optional[Decimal] = None) -> str:
    """Append a review event + audit event in one transaction. Never edits earlier events."""
    import ibm_db
    from db import connect, execute, query

    with connect(autocommit=False) as conn:
        rows = query(conn, "SELECT f.CLASSIFICATION, i.LOWER_LIMIT, i.UPPER_LIMIT FROM DT_FINDINGS f "
                           "JOIN DT_INSPECTIONS i ON i.ID = f.INSPECTION_ID WHERE f.CASE_ID = ? AND f.INSPECTION_ID = ?",
                     (case_id, inspection_id))
        if not rows:
            raise InputError("Finding not found in this case.")
        if rows[0]["CLASSIFICATION"] not in OPEN_CLASSES:
            raise InputError("Only review-scope or insufficient-data findings take a disposition.")
        validate_disposition(disposition, value, dec(rows[0]["LOWER_LIMIT"]), dec(rows[0]["UPPER_LIMIT"]), note, reviewer)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        event_id = str(uuid.uuid4())
        try:
            execute(conn, "INSERT INTO DT_REVIEW_EVENTS (ID, CASE_ID, INSPECTION_ID, DISPOSITION, REMEASURED_VALUE, NOTE, REVIEWER, CREATED_AT) "
                          "VALUES (?,?,?,?,?,?,?,?)",
                    (event_id, case_id, inspection_id, disposition, value, note.strip(), reviewer.strip(), now))
            execute(conn, "INSERT INTO DT_AUDIT (ID, CASE_ID, EVENT_TYPE, DETAILS, CREATED_AT) VALUES (?,?,?,?,?)",
                    (str(uuid.uuid4()), case_id, "REVIEW_RECORDED",
                     json.dumps({"inspection_id": inspection_id, "disposition": disposition,
                                 "remeasured_value": str(value) if value is not None else None,
                                 "reviewer": reviewer.strip(), "review_event_id": event_id}, sort_keys=True), now))
            ibm_db.commit(conn)
        except Exception:
            ibm_db.rollback(conn)
            raise
    return event_id


def review_status(case: dict[str, Any]) -> dict[str, Any]:
    """Latest disposition per open finding (computed from the append-only history)."""
    latest: dict[str, dict[str, Any]] = {}
    for ev in case.get("REVIEWS", []):
        latest[ev["INSPECTION_ID"]] = ev  # REVIEWS ordered by CREATED_AT
    open_ids = [f["INSPECTION_ID"] for f in case["FINDINGS"] if f["CLASSIFICATION"] in OPEN_CLASSES]
    return {"open_ids": open_ids, "latest": latest,
            "remaining": [i for i in open_ids if i not in latest]}
