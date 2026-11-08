"""The ledger benchmark's "before" design: the shipped DDL minus partitioning and the MQTs, with the two analytics
views as they were. No database needed."""

from __future__ import annotations

from asof import ledgerbench, schema


def test_the_before_design_is_the_shipped_schema_minus_partitions_and_mqts():
    before = {(st.kind, st.name): st for st in ledgerbench.flat_statements("LBFLAT")}
    shipped = {(st.kind, st.name): st for st in schema.load_statements("LBFLAT")}
    ledger_ddl = before[("table", "ANSWER_LEDGER")].sql
    assert "PARTITION BY" not in ledger_ddl and "PARTITION BY" in shipped[("table", "ANSWER_LEDGER")].sql
    assert "COMPRESS YES ADAPTIVE" in ledger_ddl and "IN ASOF_TS32K" in ledger_ddl
    assert not [k for k in before if k[0] == "mqt"] and [k for k in shipped if k[0] == "mqt"]
    assert not {name for _, name in before} & ledgerbench.NEW_ONLY
    assert "NOT PARTITIONED" not in before[("index", "IX_LEDGER_DECISION")].sql  # only valid on a partitioned table
    for view in ledgerbench.OLD_VIEWS:
        assert "GROUP BY" in before[("view", view)].sql and "MQT_" not in before[("view", view)].sql
        assert "LBFLAT." in before[("view", view)].sql and "ASOF." not in before[("view", view)].sql
    # Everything else is byte for byte the shipped DDL.
    changed = {"ANSWER_LEDGER", "IX_LEDGER_DECISION", *ledgerbench.OLD_VIEWS}
    assert all(before[k].sql == shipped[k].sql for k in before if k[1] not in changed)


def test_the_report_bolds_the_faster_time_and_flags_different_answers():
    q = {"what": "q", "same_rows": True, "LBFLAT": {"median_ms": 9.0, "cost": 2.0, "rows": 1, "objects": []},
         "LBPART": {"median_ms": 1.0, "cost": 1.0, "rows": 1, "objects": []}}
    r = {"rows": 10_000, "citations": 20_000, "ran_at": "2026-11-08T00:00:00+00:00", "git_commit": "abc1234",
         "load_s": {"LBFLAT": 1.0, "LBPART": 1.0}, "append_ms": {"LBFLAT": 1.0, "LBPART": 1.5},
         "queries": {"a": q, "b": {**q, "same_rows": False, "LBFLAT": {**q["LBFLAT"], "median_ms": 0.5}}}}
    text = ledgerbench.report(r)
    assert "**1.0 ms**" in text and "**0.5 ms**" in text
    assert "different rows for: b" in text
