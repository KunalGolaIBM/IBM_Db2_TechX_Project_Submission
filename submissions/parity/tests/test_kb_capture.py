"""Tests for capturing proven lessons into the knowledge base."""

from parity.history.types import ComparisonRecord, RunRecord
from parity.kb.capture import build_title, candidates_from_run, capture_run
from parity.kb.store import InMemoryKb


def record(
    query_id="q1",
    status="MATCH",
    rules=("aggregate_alias",),
    source="SELECT COUNT(*) FROM demo_users",
    db2_sql="SELECT COUNT(*) AS count FROM demo_users",
) -> ComparisonRecord:
    return ComparisonRecord(
        query_id=query_id,
        source_sql=source,
        db2_sql=db2_sql,
        status=status,
        risk_score=0,
        risk_label="LOW",
        note="",
        diff_summary="",
        applied_rules=rules,
    )


def run(records) -> RunRecord:
    return RunRecord(run_id=7, source_dir="samples", records=tuple(records))


def test_only_a_matched_rewrite_becomes_a_candidate():
    run_record = run([record()])
    candidates = candidates_from_run(run_record)
    assert len(candidates) == 1
    assert candidates[0].evidence_run_id == 7
    assert candidates[0].verified is False
    assert "aggregate_alias" in candidates[0].cause


def test_a_failed_query_teaches_nothing():
    run_record = run([record(status="MISMATCH")])
    assert candidates_from_run(run_record) == []


def test_a_query_without_a_rewrite_teaches_nothing():
    run_record = run([record(rules=(), db2_sql="SELECT COUNT(*) FROM demo_users")])
    assert candidates_from_run(run_record) == []


def test_a_rewrite_that_changed_nothing_teaches_nothing():
    run_record = run([record(rules=(), db2_sql="SELECT COUNT(*) FROM demo_users")])
    assert candidates_from_run(run_record) == []


def test_title_is_stable():
    first = build_title(("aggregate_alias",), "SELECT COUNT(*) FROM t")
    second = build_title(("aggregate_alias",), "SELECT COUNT(*) FROM t")
    assert first == second
    other = build_title(("alias_expressions",), "SELECT COUNT(*) FROM t")
    assert other != first


def test_capture_adds_and_skips_known_entries():
    store = InMemoryKb()
    run_record = run(
        [
            record(query_id="q1"),
            record(
                query_id="q2",
                source="SELECT UPPER(name) FROM demo_users",
                db2_sql="SELECT UPPER(name) AS upper FROM demo_users",
            ),
        ]
    )
    added, skipped = capture_run(store, run_record)
    assert added == 2
    assert skipped == 0
    added, skipped = capture_run(store, run_record)
    assert added == 0
    assert skipped == 2


def test_two_entries_with_the_same_query_share_one_title():
    """The title is the identity of an entry, so it is stored once."""
    store = InMemoryKb()
    added, skipped = capture_run(store, run([record(query_id="q1"), record(query_id="q2")]))
    assert added == 1
    assert skipped == 1
    assert len(store.list_candidates()) == 1


def test_capture_entries_are_candidates_not_verified():
    store = InMemoryKb()
    capture_run(store, run([record()]))
    assert store.list_candidates()
    assert store.search("count") == ()
