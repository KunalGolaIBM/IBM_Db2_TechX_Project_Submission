"""The benchmark's synthetic data and the explain tool's coverage (no database needed)."""

from __future__ import annotations

import json
import math

import pytest

from asof import explain, ledger, policy, retriever, vectorbench


def test_benchmark_data_is_deterministic_unit_length_and_half_in_force():
    rows, queries = vectorbench.make_data(200, 5)
    again, _ = vectorbench.make_data(200, 5)
    assert rows == again and len(rows) == 200 and len(queries) == 5
    for _, _start, _end, vec in rows[:20]:
        v = json.loads(vec)
        assert len(v) == 384 and abs(math.sqrt(sum(x * x for x in v)) - 1) < 1e-3
    in_force = [r for r in rows if r[1] <= vectorbench.ON < r[2]]
    assert len(in_force) == 100


def test_benchmark_compares_the_same_query_exact_and_approximate():
    assert vectorbench.SQL_EXACT.replace("EXACT", "APPROX") == vectorbench.SQL_APPROX
    assert "FIRST 10 ROWS" in vectorbench.SQL_APPROX  # a constant k: with `?` Db2 does not use the index
    assert vectorbench.SQL_APPROX_PARAM_K == vectorbench.SQL_APPROX.replace("FIRST 10 ROWS", "FIRST ? ROWS")
    assert vectorbench.SQL_EXACT_ON.replace("EXACT", "APPROX") == vectorbench.SQL_APPROX_ON
    assert "IN ASOF_TS32K" in vectorbench.SQL_TABLE and "WITH DISTANCE COSINE" in vectorbench.SQL_INDEX


def test_explain_covers_the_statements_the_app_actually_runs():
    used = {sql for _, _, sql, _ in explain.STATEMENTS}
    assert {retriever.SQL_AS_OF, retriever.SQL_REPLAY, ledger.SQL_LIST, ledger.SQL_LIST_BY_DECISION, ledger.SQL_CITATIONS,
            policy.SQL_HISTORY} <= used
    for _, _, sql, params in explain.STATEMENTS:
        assert sql.count("?") == len(params)


def _cosine_distance(a: list[float], b: list[float]) -> float:
    return 1 - sum(x * y for x, y in zip(a, b, strict=True))


def test_synthetic_clauses_have_several_contiguous_business_time_versions():
    plan = vectorbench.clause_plan(3000)
    assert plan == vectorbench.clause_plan(3000)
    assert sum(len(c.periods) for c in plan) == 3000
    assert 3.0 <= 3000 / len(plan) <= 4.0
    retired = 0
    for c in plan:
        assert 1 <= len(c.periods) <= 6
        assert all(start < end for start, end in c.periods)
        assert all(a[1] == b[0] for a, b in zip(c.periods, c.periods[1:], strict=False))  # no gaps, no overlaps
        assert all(end != vectorbench.OPEN_END for _, end in c.periods[:-1])
        retired += c.periods[-1][1] != vectorbench.OPEN_END
    assert 0.05 < retired / len(plan) < 0.15


def test_synthetic_rows_fit_the_clause_table_and_versions_stay_close():
    from typing import get_args

    from asof.schemas import Area

    plan = vectorbench.clause_plan(400)
    rows = list(vectorbench.clause_rows(plan))
    assert rows == list(vectorbench.clause_rows(plan)) and len(rows) == 400
    assert len({(r[0], r[8]) for r in rows}) == 400  # (CLAUSE_ID, BUS_START) names one version
    assert {r[2] for r in rows} <= set(get_args(Area)) and all(r[4].startswith("v") for r in rows)
    assert all(r[1] == vectorbench.CLAUSE_DOC and r[6] == json.dumps({"version": int(r[4][1:])}) for r in rows)
    assert vectorbench.SQL_CLAUSE_INSERT.count("?") == len(rows[0])
    vectors = {(r[0], r[4]): json.loads(r[7]) for r in rows}
    assert all(abs(math.sqrt(sum(x * x for x in v)) - 1) < 1e-3 for v in vectors.values())
    pairs = [(vectors[(r[0], "v1")], vectors[(r[0], "v2")]) for r in rows if r[4] == "v2"]
    between_versions = sum(_cosine_distance(a, b) for a, b in pairs) / len(pairs)
    assert 0.08 < between_versions < 0.2  # BRV-002 v1 to v2 is 0.13 in the seeded corpus
    queries = vectorbench.clause_queries(plan, 5)
    assert queries == vectorbench.clause_queries(plan, 5)
    assert all(vectorbench.QUERY_FROM <= on < vectorbench.QUERY_TO and doc == vectorbench.CLAUSE_DOC
               for _, on, doc in queries)


def test_the_four_forms_are_the_app_statement_with_only_fetch_and_the_period_changed():
    app = retriever.SQL_AS_OF
    assert vectorbench.SQL_CLAUSE_EXACT_ON == app
    assert vectorbench.SQL_CLAUSE_APPROX_ON == app.replace("FETCH EXACT FIRST ? ROWS", "FETCH APPROX FIRST 10 ROWS")
    any_date = app.replace("FOR BUSINESS_TIME AS OF ? ", "").replace("FIRST ? ROWS", "FIRST 10 ROWS")
    assert vectorbench.SQL_CLAUSE_EXACT_ALL == any_date
    assert vectorbench.SQL_CLAUSE_APPROX_ALL == any_date.replace("FETCH EXACT", "FETCH APPROX")
    for name, sql, on_date, approx in vectorbench.CLAUSE_FORMS:
        assert sql.count("?") == len(vectorbench._form_params(on_date, approx, "[0]", vectorbench.ON, "D")), name
    for name, size in vectorbench.FORCED:  # the forced forms differ from APPROX under the period only by a guideline
        forced = dict((n, sql) for n, sql, *_ in vectorbench.CLAUSE_FORMS)[name]
        guideline = (f"<IXSCAN TABID='Q1' INDEX='{vectorbench.CLAUSE_INDEX}' SEARCH_LIST_SIZE='{size}'/>")
        assert forced == f"{vectorbench.SQL_CLAUSE_APPROX_ON} /* <OPTGUIDELINES>{guideline}</OPTGUIDELINES> */"


def test_db2batch_script_binds_every_marker_and_refuses_a_quote():
    script = vectorbench.batch_script("ASOF_VBENCH", [("exact_on", vectorbench.SQL_CLAUSE_EXACT_ON,
                                                       ("[0.1,0.2]", vectorbench.ON, "VBENCH-POLICY", 10))])
    lines = script.splitlines()
    assert lines[:2] == ["--#SET ROWS_OUT 0", "SET CURRENT SCHEMA ASOF_VBENCH;"]
    assert lines[2:6] == ["--#PARAM '[0.1,0.2]'", "--#PARAM '2026-03-10'", "--#PARAM 'VBENCH-POLICY'", "--#PARAM 10"]
    assert lines[6] == vectorbench.SQL_CLAUSE_EXACT_ON + ";"
    with pytest.raises(ValueError):
        vectorbench.batch_script("ASOF_VBENCH", [("x", vectorbench.SQL_CLAUSE_APPROX_ALL, ("it's", "D"))])
    with pytest.raises(ValueError):
        vectorbench.batch_script("ASOF_VBENCH", [("x", vectorbench.SQL_CLAUSE_APPROX_ALL, ("[0]",))])
    with pytest.raises(ValueError):
        vectorbench.batch_script("ASOF; DROP", [])


def _clause_result(**extra):
    forms = [name for name, *_ in vectorbench.CLAUSE_FORMS]
    approx = [name for name, _, _, is_approx in vectorbench.CLAUSE_FORMS if is_approx]
    return {"versions": 100_000, "queries": 50, "in_force": 23_000.0, "nearest": 0.3, "timing": "db2batch",
            "p50": dict.fromkeys(forms, 1.5), "recall": dict.fromkeys(approx, 0.97) | {"approx_on": 0.5},
            "min_recall": dict.fromkeys(approx, 0.8) | {"approx_on": 0.1}, "short": dict.fromkeys(approx, 0) | {"approx_on": 3},
            "index_used": dict.fromkeys(forms, False) | {"approx_all": True, "approx_on": True}, **extra}


def test_report_keeps_earlier_runs_and_says_how_latency_was_timed():
    old = "# Title\n\nold numbers\n\n## Earlier runs\n\n### 2026-11-06\n\n| a |\n"
    history = vectorbench.kept_history(old)
    assert history.startswith("## Earlier runs") and "2026-11-06" in history and "old numbers" not in history
    assert vectorbench.kept_history("# Title\n") == ""
    text = vectorbench.render([], 10, "test host", [("Synthetic", _clause_result(clause_ids=28_000, insert_s=1.0,
                                                                                    index_s=2.0))], history)
    assert "db2batch" in text and text.endswith(history) and "## A generic table" not in text
    assert "| Synthetic | 100,000 | 23,000 |" in text and "0.50 (0.1) | 3 of 50 | yes |" in text
    assert "| Synthetic | 200 | 1.5 ms | 0.97 (0.8) | 0 of 50 | no |" in text
    assert "28,000 clause ids" in text and "vector index built in 2 s" in text
    assert "measured at the client" in vectorbench.render([], 10, "h", [("S", _clause_result(timing="client"))])


def test_explain_covers_the_three_retrieval_forms_at_seeded_size_and_at_scale():
    seeded = {name: sql for name, _, sql, _ in explain.STATEMENTS}
    assert seeded["as_of_retrieval"] == retriever.SQL_AS_OF
    assert seeded["as_of_retrieval_approx"] == vectorbench.SQL_CLAUSE_APPROX_ON
    assert seeded["nearest_any_date_approx"] == vectorbench.SQL_CLAUSE_APPROX_ALL
    assert [sql for _, _, sql, _ in explain.SCALED] == [vectorbench.SQL_CLAUSE_EXACT_ON, vectorbench.SQL_CLAUSE_APPROX_ON,
                                                       vectorbench.SQL_CLAUSE_APPROX_ALL, vectorbench.SQL_CLAUSE_DEFAULT_ALL]
    assert vectorbench.SQL_CLAUSE_DEFAULT_ALL == vectorbench.SQL_CLAUSE_APPROX_ALL.replace("FETCH APPROX", "FETCH")
    for _, _, sql, params in explain.SCALED:
        assert sql.count("?") == len(params) and vectorbench.CLAUSE_DOC in params
    assert explain.scaled_name("as_of_retrieval", 100_000) == "as_of_retrieval_100k"
    assert explain.scaled_name("x", 500) == "x_500"


def test_db2exfmt_runs_from_the_instance_home(monkeypatch):
    """In IBM's stock image `docker exec` starts in /, where db2exfmt cannot write its bind messages and prints no
    plan ("Error during bind"); from the instance owner's home it works."""
    import subprocess
    from types import SimpleNamespace

    from asof.config import Settings

    seen = []

    def fake_run(cmd, **kw):
        seen.append(cmd)
        return SimpleNamespace(returncode=0, stdout="Access Plan:\n...")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert explain._exfmt(Settings(), "db2server") == "Access Plan:\n..."
    assert seen[0][-1].startswith("cd ~ && db2exfmt ")
    assert explain._exfmt(Settings(), None) is None
