"""Real Db2 tests. Skipped (reported as skipped, not as live evidence) when Db2 is unreachable."""
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from db import Db2Error, connect, execute, query, server_identity  # noqa: E402
from models import Scope  # noqa: E402
from seed import seed  # noqa: E402
from config import get_settings  # noqa: E402
from trace import InputError, StalePreviewError, db2_crosscheck, load_case, run_trace, save_case  # noqa: E402

try:
    server_identity()
    DB2 = True
except Db2Error:
    DB2 = False

pytestmark = pytest.mark.skipif(not DB2, reason="Db2 not reachable; live Db2 tests NOT run")
SCOPE = Scope("CAL-017", "external_diameter", datetime(2026, 11, 2, 8), datetime(2026, 11, 9, 10))


def counts(conn):
    return {t: query(conn, f"SELECT COUNT(*) AS N FROM {t}")[0]["N"] for t in ("DT_CASES", "DT_FINDINGS", "DT_AUDIT")}


def draft(fp, sub=None, bound=Decimal("0.040")):
    return {"client_submission_id": sub or f"test-{uuid.uuid4()}", "notice_text": "test notice", "extraction": {"test": True},
            "intake_mode": "manual", "provider": None, "model": None, "scope": SCOPE, "rationale": "test window",
            "bound": bound, "bound_accepted": True, "preview_fingerprint": fp}


def preview(bound=Decimal("0.040")):
    with connect() as conn:
        return run_trace(conn, SCOPE, bound)


def test_seed_is_idempotent():
    seed()
    r = seed()
    assert r["created"] == [] and all(v == 0 for v in r["inserted"].values())
    assert r["counts"]["DT_INSPECTIONS"] >= 6


def test_expected_trace_counts_from_db2():
    findings, t, _ = preview()
    cls = {f.fact.inspection_id: f.classification for f in findings}
    assert cls == {"I-101": "REVIEW_SCOPE", "I-102": "REVIEW_SCOPE", "I-103": "REVIEW_SCOPE",
                   "I-104": "OUTSIDE_SCOPE", "I-105": "OUTSIDE_SCOPE", "I-106": "INSUFFICIENT_DATA"}
    assert (len(t.review_lots), len(t.review_shipments), t.review_shipped_units, t.review_unshipped_units) == (3, 2, 70, 40)
    assert (t.insufficient_lots, t.insufficient_shipped_units) == (["L-106"], 10)
    hyp = {f.fact.inspection_id: f.hypothetical for f in findings if f.classification == "REVIEW_SCOPE"}
    assert hyp == {"I-101": "CROSSES_LIMIT_UNDER_ASSUMPTION", "I-102": "WITHIN_LIMITS_UNDER_ASSUMPTION",
                   "I-103": "CROSSES_LIMIT_UNDER_ASSUMPTION"}


def test_save_persists_and_duplicate_is_idempotent():
    _, _, fp = preview()
    d = draft(fp)
    case_id, created = save_case(d)
    assert created
    again, created2 = save_case(d)
    assert again == case_id and not created2
    with connect() as conn:
        case = load_case(conn, case_id)
        n = query(conn, "SELECT COUNT(*) AS N FROM DT_FINDINGS WHERE CASE_ID = ?", (case_id,))[0]["N"]
    assert n == 6 and len(case["AUDIT"]) == 1
    assert case["SCOPE"]["totals"]["review_shipped_units"] == 70
    i101 = next(f for f in case["FINDINGS"] if f["INSPECTION_ID"] == "I-101")
    assert i101["SNAPSHOT"]["linked_shipments"][0]["shipment_id"] == "S-101"


def test_stale_preview_rejected():
    with connect() as conn:
        before = counts(conn)
    with pytest.raises(StalePreviewError):
        save_case(draft("0" * 64))
    with connect() as conn:
        assert counts(conn) == before


def test_forced_failure_rolls_back_everything():
    _, _, fp = preview()
    with connect() as conn:
        before = counts(conn)
    d = draft(fp)
    with pytest.raises(RuntimeError, match="Forced failure"):
        save_case(d, _fail_after_findings=True)
    with connect() as conn:
        assert counts(conn) == before
        assert not query(conn, "SELECT ID FROM DT_CASES WHERE CLIENT_SUBMISSION_ID = ?", (d["client_submission_id"],))


def test_snapshot_survives_operational_change():
    """Reopening a case shows the stored snapshot even if operational data later changes."""
    _, _, fp = preview()
    case_id, _ = save_case(draft(fp))
    with connect(admin=True) as conn:  # operational change by an administrator, not the app
        execute(conn, "UPDATE DT_SHIPMENTS SET SHIPPED_QUANTITY = ? WHERE ID = ?", (39, "S-101"))
    try:
        with connect() as conn:
            case = load_case(conn, case_id)
        assert case["SCOPE"]["totals"]["review_shipped_units"] == 70
    finally:
        with connect(admin=True) as conn:
            execute(conn, "UPDATE DT_SHIPMENTS SET SHIPPED_QUANTITY = ? WHERE ID = ?", (40, "S-101"))


def test_db2_view_crosscheck_matches_app_totals():
    findings, totals, _ = preview()
    with connect() as conn:
        cc = db2_crosscheck(conn, totals)
    assert cc == {"lots": 3, "shipments": 2, "shipped": 70, "unshipped": 40, "matches": True}


def test_audit_records_db2_session_user():
    _, _, fp = preview()
    case_id, _ = save_case(draft(fp))
    with connect() as conn:
        case = load_case(conn, case_id)
    assert case["AUDIT"][0]["DETAILS"]["db2_session_user"] == get_settings().uid.upper()
    assert case["AUDIT"][0]["DETAILS"]["db2_crosscheck_matches"] is True


LEAST_PRIV = pytest.mark.skipif(
    not get_settings().admin_uid or get_settings().admin_uid.upper() == get_settings().uid.upper(),
    reason="App and admin users are the same; least-privilege tests NOT run")


@LEAST_PRIV
@pytest.mark.parametrize("sql,params", [
    ("UPDATE DT_SHIPMENTS SET SHIPPED_QUANTITY = 1 WHERE ID = ?", ("S-101",)),
    ("DELETE FROM DT_INSPECTIONS WHERE ID = ?", ("I-101",)),
    ("INSERT INTO DT_LOTS (ID, PRODUCT_NAME, PRODUCED_QUANTITY) VALUES (?, ?, ?)", ("L-X", "x", 1)),
    ("DROP TABLE DT_AUDIT", ()),
])
def test_app_user_cannot_modify_operational_data(sql, params):
    with connect() as conn:
        with pytest.raises(Exception, match="SQL0551N|SQL0552N|42501|42502"):
            execute(conn, sql, params)


@pytest.mark.parametrize("sql", [
    "UPDATE DT_AUDIT SET EVENT_TYPE = 'TAMPERED' WHERE ID = ?",
    "DELETE FROM DT_AUDIT WHERE ID = ?",
    "UPDATE DT_FINDINGS SET CLASSIFICATION = 'OUTSIDE_SCOPE' WHERE CASE_ID = ?",
    "DELETE FROM DT_CASES WHERE ID = ?",
])
def test_saved_records_are_append_only_even_for_admin(sql):
    _, _, fp = preview()
    case_id, _ = save_case(draft(fp))
    with connect() as conn:
        target = case_id if "DT_AUDIT" not in sql else load_case(conn, case_id)["AUDIT"][0]["ID"]
    with connect(admin=True) as conn:
        with pytest.raises(Exception, match="75001|append-only"):
            execute(conn, sql, (target,))
    with connect() as conn:
        case = load_case(conn, case_id)
    assert case["AUDIT"][0]["EVENT_TYPE"] == "CASE_CREATED" and len(case["FINDINGS"]) == 6


@pytest.mark.parametrize("field,value", [("notice_text", "x" * 8001), ("notice_text", ""), ("rationale", " "),
                                         ("rationale", "r" * 1001), ("bound", Decimal("-0.001")), ("bound", Decimal("1.001"))])
def test_server_side_input_limits(field, value):
    _, _, fp = preview()
    d = draft(fp)
    d[field] = value
    with pytest.raises(InputError):
        save_case(d)


def test_sql_injection_text_is_inert():
    """Hostile text in a bound parameter is stored as data and never executed."""
    _, _, fp = preview()
    d = draft(fp)
    d["notice_text"] = "x'); DROP TABLE DT_AUDIT; --"
    case_id, _ = save_case(d)
    with connect() as conn:
        assert load_case(conn, case_id)["NOTICE_TEXT"] == d["notice_text"]
        assert query(conn, "SELECT COUNT(*) AS N FROM DT_AUDIT")[0]["N"] >= 1


def test_review_dispositions_append_only_history_with_audit():
    from trace import record_review, review_status
    _, _, fp = preview()
    case_id, _ = save_case(draft(fp))
    record_review(case_id, "I-103", "NOT_AVAILABLE_FOR_REMEASURE", "Lot L-103 consumed in assembly", "QM test")
    record_review(case_id, "I-103", "REMEASURED_CONFORMS", "Retained sample re-measured on CAL-018", "QM test", Decimal("24.990"))
    record_review(case_id, "I-101", "REMEASURED_NONCONFORMING", "Retained sample", "QM test", Decimal("25.061"))
    with pytest.raises(InputError):  # verdict contradicts limits
        record_review(case_id, "I-102", "REMEASURED_CONFORMS", "x", "QM test", Decimal("25.200"))
    with pytest.raises(InputError):  # outside-scope finding takes no disposition
        record_review(case_id, "I-104", "REVIEWED_NO_FURTHER_ACTION", "x", "QM test")
    with connect() as conn:
        case = load_case(conn, case_id)
    st = review_status(case)
    assert st["open_ids"] == ["I-101", "I-102", "I-103", "I-106"]
    assert st["latest"]["I-103"]["DISPOSITION"] == "REMEASURED_CONFORMS"   # history kept, latest wins
    assert len([r for r in case["REVIEWS"] if r["INSPECTION_ID"] == "I-103"]) == 2
    assert st["remaining"] == ["I-102", "I-106"]
    assert [a["EVENT_TYPE"] for a in case["AUDIT"]].count("REVIEW_RECORDED") == 3
    with connect(admin=True) as conn:
        with pytest.raises(Exception, match="75001|append-only"):
            execute(conn, "DELETE FROM DT_REVIEW_EVENTS WHERE CASE_ID = ?", (case_id,))
