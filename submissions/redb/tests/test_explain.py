from redb.explain import build_plan, summarize, to_dot

OPS = [
    {"OPERATOR_ID": 1, "OPERATOR_TYPE": "RETURN", "TOTAL_COST": 806.5, "IO_COST": 100, "CPU_COST": 1e6},
    {"OPERATOR_ID": 2, "OPERATOR_TYPE": "TBSCAN", "TOTAL_COST": 806.5, "IO_COST": 100, "CPU_COST": 1e6},
    {"OPERATOR_ID": 3, "OPERATOR_TYPE": "SORT", "TOTAL_COST": 806.5, "IO_COST": 100, "CPU_COST": 1e6},
    {"OPERATOR_ID": 4, "OPERATOR_TYPE": "TBSCAN", "TOTAL_COST": 806.4, "IO_COST": 100, "CPU_COST": 1e6},
]
STREAMS = [
    {"SOURCE_TYPE": "O", "SOURCE_ID": 2, "TARGET_ID": 1, "OBJECT_SCHEMA": None, "OBJECT_NAME": None, "STREAM_COUNT": 4},
    {"SOURCE_TYPE": "O", "SOURCE_ID": 3, "TARGET_ID": 2, "OBJECT_SCHEMA": None, "OBJECT_NAME": None, "STREAM_COUNT": 4},
    {"SOURCE_TYPE": "O", "SOURCE_ID": 4, "TARGET_ID": 3, "OBJECT_SCHEMA": None, "OBJECT_NAME": None, "STREAM_COUNT": 4},
    {"SOURCE_TYPE": "D", "SOURCE_ID": -1, "TARGET_ID": 4, "OBJECT_SCHEMA": "RETAIL  ", "OBJECT_NAME": "ORDERS",
     "STREAM_COUNT": 400000},
    {"SOURCE_TYPE": "O", "SOURCE_ID": 1, "TARGET_ID": -1, "OBJECT_SCHEMA": None, "OBJECT_NAME": None, "STREAM_COUNT": 4},
]


def test_tree_and_flags():
    plan = build_plan(OPS, STREAMS)
    assert plan["root"] == 1
    assert [c["id"] for c in plan["nodes"][1]["children"]] == [2]
    assert plan["nodes"][4]["objects"] == [{"schema": "RETAIL", "name": "ORDERS", "rows": 400000.0, "index": False}]
    kinds = {f["kind"] for f in plan["flags"]}
    assert "TABLE_SCAN" in kinds and "SORT" in kinds
    scans = [f for f in plan["flags"] if f["kind"] == "TABLE_SCAN"]
    assert len(scans) == 1 and scans[0]["op"] == 4  # TBSCAN of the sort output (#2) is not a table scan
    assert plan["tables"] == ["RETAIL.ORDERS"]


def test_small_table_scan_not_flagged():
    streams = [dict(s) for s in STREAMS]
    streams[3]["STREAM_COUNT"] = 50
    assert not [f for f in build_plan(OPS, streams)["flags"] if f["kind"] == "TABLE_SCAN"]


def test_summary_and_dot():
    plan = build_plan(OPS, STREAMS)
    plan["total_cost"] = 806.5
    text = summarize(plan)
    assert text.splitlines()[1].startswith("#1 RETURN")
    assert "FLAG TABLE_SCAN" in text
    dot = to_dot(plan)
    assert dot.startswith("digraph") and dot.rstrip().endswith("}")
    assert "shape=cylinder" in dot and "ORDERS" in dot
    assert 'op4 [shape=box, style=filled, fillcolor="#f8d7da"' in dot  # TBSCAN in red
    assert "op4 -> op3" in dot


def test_index_scan_objects_are_indexes_not_tables():
    ops = [dict(OPS[0]), {**OPS[1], "OPERATOR_TYPE": "IXSCAN"}]
    streams = [dict(STREAMS[0]), {"SOURCE_TYPE": "D", "SOURCE_ID": -1, "TARGET_ID": 2, "OBJECT_SCHEMA": "SYSTEM",
                                  "OBJECT_NAME": "IDX1", "STREAM_COUNT": 400000}]
    plan = build_plan(ops, streams)
    assert plan["tables"] == [] and plan["indexes"] == ["SYSTEM.IDX1"] and not plan["flags"]
    dot = to_dot(plan, {"IDX1": "REDB_IX_ORDERS_X"})
    assert "REDB_IX_ORDERS_X" in dot and 'fillcolor="#d1f2e0"' in dot
