"""The benchmark's synthetic data and the explain tool's coverage (no database needed)."""

from __future__ import annotations

import json
import math

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
    assert {retriever.SQL_AS_OF, retriever.SQL_REPLAY, ledger.SQL_LIST, ledger.SQL_CITATIONS, policy.SQL_HISTORY} <= used
    for _, _, sql, params in explain.STATEMENTS:
        assert sql.count("?") == len(params)
