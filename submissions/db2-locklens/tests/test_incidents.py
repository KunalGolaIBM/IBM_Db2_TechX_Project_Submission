"""Incident persistence: creation, de-duplication, escalation, resolution, validation."""

from pathlib import Path

from helpers import FakeIncidentDb

from locklens.models import Finding, Severity
from locklens.services.incident_service import IncidentStore, RESOLUTION_NOTE, load_schema_statements

import pytest


def finding(key="blocker:7", sev=Severity.WARNING, wait=30, ftype="BLOCKING_SESSION", persist=True):
    return Finding(finding_type=ftype, severity=sev, title="t", explanation="e", evidence=["x"],
                   recommendations=["r"], subject_key=key, blocker_handle=7, waiter_handles=[9],
                   lock_details="ROW lock", max_wait_seconds=wait, persist=persist)


def test_first_record_creates_one_open_incident():
    db = FakeIncidentDb(); store = IncidentStore(db)
    r = store.record([finding()])
    assert (r.created, r.updated) == (1, 0) and len(db.rows) == 1 and db.rows[0]["STATUS"] == "OPEN"


def test_repeated_refreshes_do_not_create_duplicates():
    db = FakeIncidentDb(); store = IncidentStore(db)
    for _ in range(5):
        store.record([finding()])
    assert len(db.rows) == 1 and db.rows[0]["OBSERVATIONS"] == 5


def test_severity_only_escalates_and_max_wait_is_kept():
    db = FakeIncidentDb(); store = IncidentStore(db)
    store.record([finding(sev=Severity.CRITICAL, wait=90)])
    store.record([finding(sev=Severity.WARNING, wait=20)])
    assert db.rows[0]["SEVERITY"] == "CRITICAL" and db.rows[0]["MAX_WAIT_SECONDS"] == 90


def test_findings_below_threshold_or_marked_non_persistent_are_skipped():
    db = FakeIncidentDb(); store = IncidentStore(db)
    r = store.record([finding(sev=Severity.INFO), finding(key="b", persist=False), finding(key="")])
    assert r.created == 0 and r.skipped == 3 and not db.rows
    assert store.record([finding(sev=Severity.INFO)], min_severity=Severity.INFO).created == 1


def test_distinct_subjects_create_distinct_incidents():
    db = FakeIncidentDb(); store = IncidentStore(db)
    store.record([finding("blocker:7"), finding("blocker:8")])
    assert len(db.rows) == 2


def test_absent_incident_is_resolved_and_a_recurrence_opens_a_new_row():
    db = FakeIncidentDb(); store = IncidentStore(db)
    store.record([finding()])
    keys = IncidentStore.active_keys([], Severity.WARNING)
    assert store.resolve_absent(keys) == 1
    assert db.rows[0]["STATUS"] == "RESOLVED" and db.rows[0]["OPEN_KEY"] is None
    store.record([finding()])                                   # same blocker blocks again later
    assert len(db.rows) == 2 and db.rows[1]["STATUS"] == "OPEN"


def test_still_active_incident_is_not_resolved():
    db = FakeIncidentDb(); store = IncidentStore(db)
    f = finding(); store.record([f])
    assert store.resolve_absent(IncidentStore.active_keys([f], Severity.WARNING)) == 0
    assert db.rows[0]["STATUS"] == "OPEN"


def test_duplicate_key_race_falls_back_to_update():
    db = FakeIncidentDb(fail_first_insert_with_duplicate=True); store = IncidentStore(db)
    r = store.record([finding()])
    assert (r.created, r.updated) == (0, 1) and len(db.rows) == 1


def test_non_duplicate_database_errors_are_not_swallowed():
    from locklens.errors import Db2QueryError

    class Boom(FakeIncidentDb):
        def execute(self, sql, params=()):
            raise Db2QueryError("SQL0104N", 104)

    with pytest.raises(Db2QueryError):
        IncidentStore(Boom()).record([finding()])


def test_schema_name_is_validated_against_injection():
    for bad in ("x; DROP TABLE y", "1abc", "", "a" * 40, "a b"):
        with pytest.raises(ValueError):
            IncidentStore(FakeIncidentDb(), bad)
    with pytest.raises(ValueError):
        load_schema_statements("bad name")


def test_filter_values_are_validated_and_bound_not_interpolated():
    db = FakeIncidentDb(); store = IncidentStore(db)
    store.list_incidents(severity="critical", category="lock_contention", status="open", since="2026-11-01")
    sql = db.sql_log[-1]
    assert "SEVERITY = ?" in sql and "critical" not in sql.lower().replace("severity", "") and "2026" not in sql
    for kwargs in ({"severity": "huge"}, {"status": "weird"}, {"since": "1; DROP"}):
        with pytest.raises(ValueError):
            store.list_incidents(**kwargs)


def test_limit_is_clamped():
    db = FakeIncidentDb(); IncidentStore(db).list_incidents(limit=10**9)
    assert "FETCH FIRST 1000 ROWS ONLY" in db.sql_log[-1]


def test_schema_ddl_has_open_key_unique_index_and_substitution():
    stmts = load_schema_statements("MYLENS")
    joined = "\n".join(stmts)
    assert "${SCHEMA}" not in joined and "MYLENS.LOCK_INCIDENTS" in joined
    assert "UNIQUE INDEX MYLENS.UX_LOCK_INCIDENTS_OPEN" in joined and "EXCLUDE NULL KEYS" in joined
    assert len(stmts) == 4


def test_cli_script_matches_packaged_schema():
    script = Path(__file__).resolve().parents[1] / "scripts" / "init_db.sql"
    text = "\n".join(l for l in script.read_text().splitlines() if not l.strip().startswith("--"))
    script_stmts = [" ".join(s.split()) for s in text.split(";") if s.strip()]
    packaged = [" ".join(s.split()) for s in load_schema_statements("LOCKLENS")]
    assert script_stmts == packaged


def test_init_schema_ignores_already_exists_but_raises_real_failures():
    from locklens.errors import Db2QueryError

    class Exists(FakeIncidentDb):
        def execute(self, sql, params=()):
            raise Db2QueryError("SQL0601N exists", 601)

    lines = IncidentStore(Exists()).init_schema()
    assert all(l.startswith("EXISTS") for l in lines)

    class Denied(FakeIncidentDb):
        def execute(self, sql, params=()):
            raise Db2QueryError("SQL0551N denied", 551)

    with pytest.raises(Db2QueryError):
        IncidentStore(Denied()).init_schema()


def test_resolution_note_is_evidence_based_wording():
    assert "No longer observed" in RESOLUTION_NOTE
