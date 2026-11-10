"""IBM Db2 persistence for investigations, evidence, recommendations and human review.

Integrity is enforced twice: by explicit checks here (good error messages) and by Db2
constraints (composite foreign key on evidence, unique index on decisions, CHECK lists),
so a bug or bypass in application code cannot store fabricated evidence or two decisions.
All SQL is static; values are bound parameters. Placeholder lists are built only from the
*count* of an already length-bounded list.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from civiclens.db import repository as repo
from civiclens.db.connection import Db2Session
from civiclens.domain.errors import (
    ConflictError,
    ForbiddenError,
    InvalidEvidenceError,
    NotFoundError,
)
from civiclens.domain.investigation_models import (
    MAX_EVIDENCE_PER_RECOMMENDATION,
    AuditEntry,
    EvidenceItem,
    GeneratorType,
    Investigation,
    InvestigationStatus,
    Recommendation,
    RecommendationDraft,
    RecommendationListItem,
    RecommendationStatus,
    ReviewDecision,
)
from civiclens.domain.models import Category

MAX_LIST = 100
_INV_COLUMNS = "INVESTIGATION_ID, TITLE, QUESTION, STATUS, CREATED_BY, CREATED_AT, CLOSED_AT"


def _f(value: Any) -> float:
    return float(Decimal(str(value))) if value is not None else 0.0


def _placeholders(n: int) -> str:
    if not 1 <= n <= MAX_EVIDENCE_PER_RECOMMENDATION:
        raise ValueError("unexpected id list size")
    return ", ".join("?" * n)


def _is_unique_violation(exc: Exception) -> bool:
    return "SQL0803N" in str(exc)


# ----------------------------------------------------------------------------- investigations
def _inv(row: dict[str, Any]) -> Investigation:
    return Investigation(
        investigation_id=int(row["investigation_id"]),
        title=row["title"],
        question=row["question"],
        status=InvestigationStatus(row["status"]),
        created_by=row["created_by"],
        created_at=row["created_at"],
        closed_at=row["closed_at"],
    )


def create_investigation(db: Db2Session, *, title: str, question: str, created_by: str) -> Investigation:
    with db.transaction():
        inv_id = repo.create_investigation(db, title=title, question=question, created_by=created_by)
        repo.write_audit(
            db,
            actor_type="USER",
            actor_id=created_by,
            action="INVESTIGATION_CREATED",
            investigation_id=inv_id,
            input_payload={"title": title},
            output_summary="status=OPEN",
        )
    return require_investigation(db, inv_id)


def get_investigation(db: Db2Session, investigation_id: int) -> Investigation | None:
    row = db.fetch_one(
        f"SELECT {_INV_COLUMNS} FROM {{schema}}.INVESTIGATIONS WHERE INVESTIGATION_ID = ?",
        (investigation_id,),
    )
    return _inv(row) if row else None


def require_investigation(db: Db2Session, investigation_id: int) -> Investigation:
    inv = get_investigation(db, investigation_id)
    if inv is None:
        raise NotFoundError("Investigation not found.", code="INVESTIGATION_NOT_FOUND")
    return inv


def list_investigations(
    db: Db2Session, *, status: InvestigationStatus | None = None, limit: int = 50
) -> list[Investigation]:
    limit = max(1, min(int(limit), MAX_LIST))
    where, params = ("WHERE STATUS = ?", (status.value,)) if status else ("", ())
    rows = db.fetch_all(
        f"SELECT {_INV_COLUMNS} FROM {{schema}}.INVESTIGATIONS {where} "
        f"ORDER BY INVESTIGATION_ID DESC FETCH FIRST {limit} ROWS ONLY",
        params,
    )
    return [_inv(r) for r in rows]


def transition_status(
    db: Db2Session,
    investigation_id: int,
    *,
    from_statuses: Sequence[InvestigationStatus],
    to_status: InvestigationStatus,
) -> bool:
    """Atomic compare-and-set on the status column. True if this call performed the change."""
    marks = ", ".join("?" * len(from_statuses))
    closed = ", CLOSED_AT = CURRENT TIMESTAMP" if to_status is InvestigationStatus.CLOSED else ""
    n = db.execute(
        f"UPDATE {{schema}}.INVESTIGATIONS SET STATUS = ?{closed} "
        f"WHERE INVESTIGATION_ID = ? AND STATUS IN ({marks})",
        (to_status.value, investigation_id, *[s.value for s in from_statuses]),
    )
    return n == 1


# ----------------------------------------------------------------------------- evidence
def existing_complaint_ids(db: Db2Session, ids: Sequence[int]) -> set[int]:
    rows = db.fetch_all(
        f"SELECT COMPLAINT_ID FROM {{schema}}.COMPLAINTS WHERE COMPLAINT_ID IN ({_placeholders(len(ids))})",
        tuple(ids),
    )
    return {int(r["complaint_id"]) for r in rows}


def attached_evidence_ids(db: Db2Session, investigation_id: int, ids: Sequence[int]) -> set[int]:
    rows = db.fetch_all(
        "SELECT COMPLAINT_ID FROM {schema}.INVESTIGATION_EVIDENCE WHERE INVESTIGATION_ID = ? "
        f"AND COMPLAINT_ID IN ({_placeholders(len(ids))})",
        (investigation_id, *ids),
    )
    return {int(r["complaint_id"]) for r in rows}


def add_evidence(
    db: Db2Session,
    investigation_id: int,
    complaint_ids: Sequence[int],
    *,
    relevance: float = 1.0,
    note: str | None = None,
) -> int:
    """Attach existing complaints to an investigation. Unknown ids are rejected, not ignored."""
    ids = sorted(set(complaint_ids))
    unknown = sorted(set(ids) - existing_complaint_ids(db, ids))
    if unknown:
        raise InvalidEvidenceError(
            "Some complaint ids do not exist.", code="UNKNOWN_COMPLAINT_IDS", unknown_ids=unknown
        )
    inv = require_investigation(db, investigation_id)
    if inv.status is InvestigationStatus.CLOSED:
        raise ConflictError("Investigation is closed.", code="INVESTIGATION_CLOSED")
    inserted = 0
    with db.transaction():
        for cid in ids:
            inserted += db.execute(
                """
                INSERT INTO {schema}.INVESTIGATION_EVIDENCE
                    (INVESTIGATION_ID, COMPLAINT_ID, RELEVANCE, NOTE)
                SELECT CAST(? AS BIGINT), C.COMPLAINT_ID, CAST(? AS DECIMAL(4,3)), CAST(? AS VARCHAR(1000))
                FROM {schema}.COMPLAINTS C
                WHERE C.COMPLAINT_ID = ?
                  AND NOT EXISTS (SELECT 1 FROM {schema}.INVESTIGATION_EVIDENCE E
                                  WHERE E.INVESTIGATION_ID = ? AND E.COMPLAINT_ID = C.COMPLAINT_ID)
                """,
                (investigation_id, f"{max(0.0, min(1.0, relevance)):.3f}", note, cid, investigation_id),
            )
    return inserted


def list_evidence(db: Db2Session, investigation_id: int) -> list[EvidenceItem]:
    rows = db.fetch_all(
        """
        SELECT E.INVESTIGATION_ID, E.COMPLAINT_ID, E.RELEVANCE, E.NOTE, E.ADDED_AT,
               C.TITLE, C.CATEGORY, C.GEO_CELL, C.SEVERITY, C.REPORTED_AT, C.IS_SYNTHETIC
        FROM {schema}.INVESTIGATION_EVIDENCE E
        JOIN {schema}.COMPLAINTS C ON C.COMPLAINT_ID = E.COMPLAINT_ID
        WHERE E.INVESTIGATION_ID = ?
        ORDER BY E.RELEVANCE DESC, E.COMPLAINT_ID
        """,
        (investigation_id,),
    )
    return [
        EvidenceItem(
            investigation_id=int(r["investigation_id"]),
            complaint_id=int(r["complaint_id"]),
            relevance=_f(r["relevance"]),
            note=r["note"],
            added_at=r["added_at"],
            title=r["title"],
            category=Category(r["category"]),
            geo_cell=r["geo_cell"],
            severity=int(r["severity"]),
            reported_at=r["reported_at"],
            is_synthetic=bool(r["is_synthetic"]),
        )
        for r in rows
    ]


# ----------------------------------------------------------------------------- recommendations
def validate_evidence(db: Db2Session, investigation_id: int, evidence_ids: Sequence[int]) -> None:
    """Every cited id must be a real complaint attached to this investigation."""
    ids = sorted(set(evidence_ids))
    if not ids:
        raise InvalidEvidenceError("A recommendation needs at least one evidence id.", code="NO_EVIDENCE")
    unknown = sorted(set(ids) - existing_complaint_ids(db, ids))
    if unknown:
        raise InvalidEvidenceError(
            "Evidence ids do not exist in the complaint database.",
            code="UNKNOWN_COMPLAINT_IDS",
            unknown_ids=unknown,
        )
    detached = sorted(set(ids) - attached_evidence_ids(db, investigation_id, ids))
    if detached:
        raise InvalidEvidenceError(
            "Evidence ids are not attached to this investigation.",
            code="EVIDENCE_NOT_ATTACHED",
            unattached_ids=detached,
        )


def create_recommendation(
    db: Db2Session,
    investigation_id: int,
    draft: RecommendationDraft,
    *,
    generator: GeneratorType,
    model_name: str | None,
    actor_id: str,
) -> int:
    """Store a PROPOSED recommendation plus its evidence links in one transaction.

    The status is a SQL literal: no caller (and no model output) can create a recommendation
    in any other state.
    """
    with db.transaction():
        inv = require_investigation(db, investigation_id)
        if inv.status in (InvestigationStatus.CLOSED, InvestigationStatus.FAILED):
            raise ConflictError(f"Investigation is {inv.status.value}.", code="INVESTIGATION_NOT_ACCEPTING")
        validate_evidence(db, investigation_id, draft.evidence_ids)
        row = db.fetch_one(
            """
            SELECT RECOMMENDATION_ID FROM FINAL TABLE (
                INSERT INTO {schema}.RECOMMENDATIONS
                    (INVESTIGATION_ID, SUMMARY, RATIONALE, PRIORITY, CONFIDENCE, EVIDENCE_IDS,
                     MODEL_NAME, GENERATOR_TYPE, STATUS)
                VALUES (?, ?, ?, ?, CAST(? AS DECIMAL(4,3)), ?, ?, ?, 'PROPOSED')
            )
            """,
            (
                investigation_id,
                draft.summary,
                draft.rationale,
                draft.priority,
                f"{draft.confidence:.3f}",
                ",".join(str(i) for i in draft.evidence_ids),
                model_name[:128] if model_name else None,
                generator.value,
            ),
        )
        assert row is not None
        rec_id = int(row["recommendation_id"])
        for cid in draft.evidence_ids:
            db.execute(
                "INSERT INTO {schema}.RECOMMENDATION_EVIDENCE "
                "(RECOMMENDATION_ID, INVESTIGATION_ID, COMPLAINT_ID) VALUES (?, ?, ?)",
                (rec_id, investigation_id, cid),
            )
        repo.write_audit(
            db,
            actor_type="AGENT" if generator is not GeneratorType.MANUAL else "USER",
            actor_id=actor_id,
            action="RECOMMENDATION_PROPOSED",
            investigation_id=investigation_id,
            input_payload={"recommendation_id": rec_id, "evidence_ids": draft.evidence_ids},
            output_summary=f"priority={draft.priority} generator={generator.value}",
        )
    return rec_id


_REC_SQL = """
    SELECT R.RECOMMENDATION_ID, R.INVESTIGATION_ID, R.SUMMARY, R.RATIONALE, R.PRIORITY, R.CONFIDENCE,
           R.GENERATOR_TYPE, R.MODEL_NAME, R.STATUS, R.CREATED_AT,
           D.DECISION_ID, D.REVIEWER, D.DECISION, D.COMMENT, D.DECIDED_AT
    FROM {schema}.RECOMMENDATIONS R
    LEFT JOIN {schema}.REVIEW_DECISIONS D ON D.RECOMMENDATION_ID = R.RECOMMENDATION_ID
"""


def _rec(row: dict[str, Any], evidence_ids: list[int]) -> Recommendation:
    review = None
    if row["decision_id"] is not None:
        review = ReviewDecision(
            decision_id=int(row["decision_id"]),
            recommendation_id=int(row["recommendation_id"]),
            reviewer=row["reviewer"],
            decision=row["decision"],
            comment=row["comment"],
            decided_at=row["decided_at"],
        )
    return Recommendation(
        recommendation_id=int(row["recommendation_id"]),
        investigation_id=int(row["investigation_id"]),
        summary=row["summary"],
        rationale=row["rationale"],
        priority=int(row["priority"]),
        confidence=_f(row["confidence"]),
        evidence_ids=evidence_ids,
        generator_type=GeneratorType(row["generator_type"]),
        model_name=row["model_name"],
        status=RecommendationStatus(row["status"]),
        created_at=row["created_at"],
        review=review,
    )


def list_recommendations(db: Db2Session, investigation_id: int) -> list[Recommendation]:
    rows = db.fetch_all(
        _REC_SQL + " WHERE R.INVESTIGATION_ID = ? ORDER BY R.PRIORITY, R.RECOMMENDATION_ID",
        (investigation_id,),
    )
    ev: dict[int, list[int]] = {}
    for e in db.fetch_all(
        "SELECT RE.RECOMMENDATION_ID, RE.COMPLAINT_ID FROM {schema}.RECOMMENDATION_EVIDENCE RE "
        "WHERE RE.INVESTIGATION_ID = ? ORDER BY RE.RECOMMENDATION_ID, RE.COMPLAINT_ID",
        (investigation_id,),
    ):
        ev.setdefault(int(e["recommendation_id"]), []).append(int(e["complaint_id"]))
    return [_rec(r, ev.get(int(r["recommendation_id"]), [])) for r in rows]


MAX_REC_LIST = 100


def list_recommendations_all(
    db: Db2Session,
    *,
    status: RecommendationStatus | None = None,
    generator: GeneratorType | None = None,
    investigation_id: int | None = None,
    limit: int = 50,
) -> list[RecommendationListItem]:
    """Recommendations across investigations (pending first, then by priority), with context."""
    limit = max(1, min(int(limit), MAX_REC_LIST))
    clauses: list[str] = []
    params: list[Any] = []
    if status is not None:
        clauses.append("R.STATUS = ?")
        params.append(status.value)
    if generator is not None:
        clauses.append("R.GENERATOR_TYPE = ?")
        params.append(generator.value)
    if investigation_id is not None:
        clauses.append("R.INVESTIGATION_ID = ?")
        params.append(investigation_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = db.fetch_all(
        """
        SELECT R.RECOMMENDATION_ID, R.INVESTIGATION_ID, R.SUMMARY, R.RATIONALE, R.PRIORITY, R.CONFIDENCE,
               R.GENERATOR_TYPE, R.MODEL_NAME, R.STATUS, R.CREATED_AT,
               D.DECISION_ID, D.REVIEWER, D.DECISION, D.COMMENT, D.DECIDED_AT,
               I.TITLE AS INVESTIGATION_TITLE, I.STATUS AS INVESTIGATION_STATUS,
               I.CREATED_BY AS INVESTIGATION_CREATED_BY
        FROM {schema}.RECOMMENDATIONS R
        JOIN {schema}.INVESTIGATIONS I ON I.INVESTIGATION_ID = R.INVESTIGATION_ID
        LEFT JOIN {schema}.REVIEW_DECISIONS D ON D.RECOMMENDATION_ID = R.RECOMMENDATION_ID
        """
        + where
        + " ORDER BY CASE WHEN R.STATUS = 'PROPOSED' THEN 0 ELSE 1 END, R.PRIORITY, R.RECOMMENDATION_ID DESC"
        + f" FETCH FIRST {limit} ROWS ONLY",
        params,
    )
    if not rows:
        return []
    ids = [int(r["recommendation_id"]) for r in rows]
    evidence: dict[int, list[int]] = {}
    for e in db.fetch_all(
        "SELECT RECOMMENDATION_ID, COMPLAINT_ID FROM {schema}.RECOMMENDATION_EVIDENCE "
        f"WHERE RECOMMENDATION_ID IN ({', '.join('?' * len(ids))}) ORDER BY RECOMMENDATION_ID, COMPLAINT_ID",
        ids,
    ):
        evidence.setdefault(int(e["recommendation_id"]), []).append(int(e["complaint_id"]))
    return [
        RecommendationListItem(
            **_rec(r, evidence.get(int(r["recommendation_id"]), [])).model_dump(),
            investigation_title=r["investigation_title"],
            investigation_status=InvestigationStatus(r["investigation_status"]),
            investigation_created_by=r["investigation_created_by"],
        )
        for r in rows
    ]


def get_recommendation(db: Db2Session, recommendation_id: int) -> Recommendation | None:
    row = db.fetch_one(_REC_SQL + " WHERE R.RECOMMENDATION_ID = ?", (recommendation_id,))
    if row is None:
        return None
    ids = [
        int(e["complaint_id"])
        for e in db.fetch_all(
            "SELECT COMPLAINT_ID FROM {schema}.RECOMMENDATION_EVIDENCE WHERE RECOMMENDATION_ID = ? "
            "ORDER BY COMPLAINT_ID",
            (recommendation_id,),
        )
    ]
    return _rec(row, ids)


# ----------------------------------------------------------------------------- human review
def decide(
    db: Db2Session,
    recommendation_id: int,
    *,
    reviewer: str,
    decision: str,
    comment: str | None,
) -> Recommendation:
    """Record an approve/reject decision atomically.

    One Db2 transaction updates the recommendation status, inserts the decision row, writes the
    audit entry and (when nothing is left to review) closes the investigation. Any failure rolls
    all of it back. Guards:
      * reviewer may not review an investigation they created (four-eyes principle)
      * the status flip is a compare-and-set on STATUS='PROPOSED' (only one writer can win)
      * a unique index on REVIEW_DECISIONS(RECOMMENDATION_ID) is the database backstop
      * the recommendation's evidence must still exist
    """
    if decision not in ("APPROVED", "REJECTED"):
        raise ConflictError("Unsupported decision.", code="INVALID_DECISION")
    with db.transaction():
        meta = db.fetch_one(
            "SELECT R.INVESTIGATION_ID, R.STATUS, I.CREATED_BY, I.STATUS AS INV_STATUS "
            "FROM {schema}.RECOMMENDATIONS R "
            "JOIN {schema}.INVESTIGATIONS I ON I.INVESTIGATION_ID = R.INVESTIGATION_ID "
            "WHERE R.RECOMMENDATION_ID = ?",
            (recommendation_id,),
        )
        if meta is None:
            raise NotFoundError("Recommendation not found.", code="RECOMMENDATION_NOT_FOUND")
        inv_id = int(meta["investigation_id"])
        if meta["created_by"] == reviewer:
            raise ForbiddenError(
                "Reviewers may not review recommendations on investigations they created.",
                code="SELF_REVIEW_FORBIDDEN",
                investigation_id=inv_id,
            )
        if meta["status"] != "PROPOSED":
            raise ConflictError(f"Recommendation was already {meta['status']}.", code="ALREADY_DECIDED")
        if meta["inv_status"] != InvestigationStatus.PENDING_REVIEW.value:
            raise ConflictError("Investigation is not awaiting review.", code="INVESTIGATION_NOT_REVIEWABLE")
        linked = db.fetch_one(
            "SELECT COUNT(*) AS N FROM {schema}.RECOMMENDATION_EVIDENCE WHERE RECOMMENDATION_ID = ?",
            (recommendation_id,),
        )
        if not linked or int(linked["n"]) == 0:
            raise ConflictError("Recommendation has no evidence left.", code="EVIDENCE_MISSING")

        changed = db.execute(
            "UPDATE {schema}.RECOMMENDATIONS SET STATUS = ? "
            "WHERE RECOMMENDATION_ID = ? AND STATUS = 'PROPOSED'",
            (decision, recommendation_id),
        )
        if changed != 1:
            raise ConflictError("Recommendation was decided concurrently.", code="ALREADY_DECIDED")
        try:
            db.execute(
                "INSERT INTO {schema}.REVIEW_DECISIONS (RECOMMENDATION_ID, REVIEWER, DECISION, COMMENT) "
                "VALUES (?, ?, ?, ?)",
                (recommendation_id, reviewer, decision, comment),
            )
        except Exception as exc:
            if _is_unique_violation(exc):
                raise ConflictError(
                    "A decision already exists for this recommendation.", code="ALREADY_DECIDED"
                ) from None
            raise
        repo.write_audit(
            db,
            actor_type="USER",
            actor_id=reviewer,
            action=f"REVIEW_{decision}",
            investigation_id=inv_id,
            input_payload={"recommendation_id": recommendation_id, "has_comment": bool(comment)},
            output_summary=f"recommendation {recommendation_id} -> {decision}",
        )
        pending = db.fetch_one(
            "SELECT COUNT(*) AS N FROM {schema}.RECOMMENDATIONS "
            "WHERE INVESTIGATION_ID = ? AND STATUS = 'PROPOSED'",
            (inv_id,),
        )
        if pending is not None and int(pending["n"]) == 0:
            transition_status(
                db,
                inv_id,
                from_statuses=[InvestigationStatus.PENDING_REVIEW],
                to_status=InvestigationStatus.CLOSED,
            )
    result = get_recommendation(db, recommendation_id)
    assert result is not None
    return result


# ----------------------------------------------------------------------------- audit
def audit_history(db: Db2Session, investigation_id: int, *, limit: int = 200) -> list[AuditEntry]:
    limit = max(1, min(int(limit), 500))
    rows = db.fetch_all(
        "SELECT AUDIT_ID, ACTOR_TYPE, ACTOR_ID, ACTION, TOOL_NAME, INPUT_JSON, OUTPUT_SUMMARY, "
        "SUCCESS, CREATED_AT FROM {schema}.AUDIT_LOG WHERE INVESTIGATION_ID = ? "
        f"ORDER BY AUDIT_ID FETCH FIRST {limit} ROWS ONLY",
        (investigation_id,),
    )
    return [
        AuditEntry(
            audit_id=int(r["audit_id"]),
            actor_type=r["actor_type"],
            actor_id=r["actor_id"],
            action=r["action"],
            tool_name=r["tool_name"],
            input_json=r["input_json"],
            output_summary=r["output_summary"],
            success=bool(r["success"]),
            created_at=r["created_at"],
        )
        for r in rows
    ]


def record_denied(
    db: Db2Session, *, actor_id: str, action: str, investigation_id: int | None, reason: str
) -> None:
    """Audit a rejected attempt (written outside any rolled-back transaction)."""
    repo.write_audit(
        db,
        actor_type="USER",
        actor_id=actor_id,
        action=action,
        investigation_id=investigation_id,
        output_summary=reason,
        success=False,
    )


def now() -> datetime:  # small seam for tests
    return repo.utcnow()
