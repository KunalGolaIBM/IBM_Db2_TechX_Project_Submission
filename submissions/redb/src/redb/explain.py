"""Diagnose: EXPLAIN a statement and turn Db2's explain tables into a plan tree."""
from __future__ import annotations

import random
from typing import Any

BIG_TABLE_ROWS = 10_000


def ensure_explain_tables(db) -> None:
    schema = db.settings.db2_user.upper()
    exists = db.scalar("SELECT COUNT(*) FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = 'EXPLAIN_INSTANCE'",
                       (schema,))
    if not exists:
        db.execute("CALL SYSPROC.SYSINSTALLOBJECTS('EXPLAIN','C',CAST(NULL AS VARCHAR(128)), ?)", (schema,))


def _statement_keys(db, queryno: int) -> dict[str, Any] | None:
    rows = db.query(
        """SELECT CHAR(EXPLAIN_TIME) AS ET, SOURCE_NAME, STMTNO, SECTNO, TOTAL_COST
           FROM EXPLAIN_STATEMENT WHERE EXPLAIN_LEVEL = 'P' AND QUERYNO = ?
           ORDER BY EXPLAIN_TIME DESC FETCH FIRST 1 ROW ONLY""", (queryno,))
    return rows[0] if rows else None


def read_plan(db, keys: dict[str, Any]) -> tuple[list[dict], list[dict]]:
    k = (keys["ET"], keys["SOURCE_NAME"], keys["STMTNO"], keys["SECTNO"])
    where = "CHAR(EXPLAIN_TIME) = ? AND SOURCE_NAME = ? AND STMTNO = ? AND SECTNO = ?"
    ops = db.query(f"""SELECT OPERATOR_ID, OPERATOR_TYPE, TOTAL_COST, IO_COST, CPU_COST
                        FROM EXPLAIN_OPERATOR WHERE {where} ORDER BY OPERATOR_ID""", k)
    streams = db.query(f"""SELECT SOURCE_TYPE, SOURCE_ID, TARGET_ID, OBJECT_SCHEMA, OBJECT_NAME, STREAM_COUNT
                            FROM EXPLAIN_STREAM WHERE {where}""", k)
    return ops, streams


def explain(db, sql: str) -> dict[str, Any]:
    queryno = random.randint(1, 2_000_000_000)
    db.execute(f"EXPLAIN PLAN SET QUERYNO = {queryno} SET QUERYTAG = 'REDB' FOR {sql}")
    keys = _statement_keys(db, queryno)
    if not keys:
        raise RuntimeError("EXPLAIN produced no statement row")
    ops, streams = read_plan(db, keys)
    plan = build_plan(ops, streams)
    plan["total_cost"] = float(keys["TOTAL_COST"])
    return plan


def build_plan(ops: list[dict], streams: list[dict]) -> dict[str, Any]:
    """Build an operator tree from EXPLAIN_OPERATOR + EXPLAIN_STREAM rows and flag problems."""
    nodes = {int(o["OPERATOR_ID"]): {
        "id": int(o["OPERATOR_ID"]), "type": o["OPERATOR_TYPE"].strip(),
        "cost": float(o["TOTAL_COST"] or 0), "io": float(o["IO_COST"] or 0),
        "cpu": float(o["CPU_COST"] or 0), "children": [], "objects": []} for o in ops}
    for s in streams:
        tgt = s["TARGET_ID"]
        if tgt is None or int(tgt) < 0 or int(tgt) not in nodes:
            continue
        node = nodes[int(tgt)]
        rows = float(s["STREAM_COUNT"] or 0)
        if (s["SOURCE_TYPE"] or "").strip() == "D":
            node["objects"].append({"schema": (s["OBJECT_SCHEMA"] or "").strip(),
                                    "name": (s["OBJECT_NAME"] or "").strip(), "rows": rows,
                                    "index": node["type"] == "IXSCAN"})  # an IXSCAN's data object is the index
        elif s["SOURCE_ID"] is not None and int(s["SOURCE_ID"]) in nodes:
            node["children"].append({"id": int(s["SOURCE_ID"]), "rows": rows})
    root = next((n["id"] for n in nodes.values() if n["type"] == "RETURN"), min(nodes) if nodes else None)
    total = nodes[root]["cost"] if root is not None else 0.0
    flags = []
    for n in nodes.values():
        if n["type"] == "TBSCAN":
            for obj in n["objects"]:
                if obj["rows"] >= BIG_TABLE_ROWS and not obj["index"]:
                    flags.append({"op": n["id"], "kind": "TABLE_SCAN",
                                  "detail": f"full scan of {obj['schema']}.{obj['name']} (~{obj['rows']:,.0f} rows)"})
        elif n["type"] == "SORT":
            flags.append({"op": n["id"], "kind": "SORT", "detail": f"sort costing {n['cost']:,.1f} timerons"})
        elif n["type"] in ("HSJOIN", "NLJOIN", "MSJOIN") and total and n["cost"] > 0.5 * total:
            flags.append({"op": n["id"], "kind": "COSTLY_JOIN",
                          "detail": f"{n['type']} accounts for {100 * n['cost'] / total:.0f}% of cost"})
    objs = [o for n in nodes.values() for o in n["objects"]]
    return {"root": root, "nodes": nodes, "flags": flags, "operators": sorted({n["type"] for n in nodes.values()}),
            "tables": sorted({f"{o['schema']}.{o['name']}" for o in objs if not o["index"]}),
            "indexes": sorted({f"{o['schema']}.{o['name']}" for o in objs if o["index"]})}


def summarize(plan: dict[str, Any]) -> str:
    lines = [f"Total estimated cost: {plan.get('total_cost', 0):,.1f} timerons"]

    def walk(nid: int, depth: int) -> None:
        n = plan["nodes"][nid]
        objs = ", ".join(f"{o['schema']}.{o['name']} ({o['rows']:,.0f} rows)" for o in n["objects"])
        lines.append(f"{'  ' * depth}#{n['id']} {n['type']} cost={n['cost']:,.1f}" + (f" on {objs}" if objs else ""))
        for c in n["children"]:
            walk(c["id"], depth + 1)

    if plan["root"] is not None:
        walk(plan["root"], 0)
    for f in plan["flags"]:
        lines.append(f"FLAG {f['kind']}: {f['detail']}")
    return "\n".join(lines)


def to_dot(plan: dict[str, Any], names: dict[str, str] | None = None) -> str:
    """Graphviz DOT. `names` maps object names (e.g. the advisor's virtual index names) to display names."""
    names = names or {}
    fills = {"TBSCAN": 'fillcolor="#f8d7da", color="#c0392b"', "IXSCAN": 'fillcolor="#d1f2e0", color="#0b6b3a"'}
    out = ['digraph plan {', 'rankdir=BT; node [fontname="Helvetica", fontsize=10];']
    for n in plan["nodes"].values():
        style = "style=filled, " + fills.get(n["type"], 'fillcolor="#e8f0fe", color="#1f4e8c"')
        out.append(f'op{n["id"]} [shape=box, {style}, label="{n["type"]} #{n["id"]}\\ncost {n["cost"]:,.0f}"];')
        for c in n["children"]:
            out.append(f'op{c["id"]} -> op{n["id"]} [label="{c["rows"]:,.0f}"];')
        for i, o in enumerate(n["objects"]):
            tid = f'tb{n["id"]}_{i}'
            label = names.get(o["name"], o["name"])
            if o["index"]:
                out.append(f'{tid} [shape=note, style=filled, fillcolor="#d1f2e0", label="index\\n{label}"];')
            else:
                out.append(f'{tid} [shape=cylinder, style=filled, fillcolor="#fff3cd", label="{label}\\n{o["rows"]:,.0f} rows"];')
            out.append(f'{tid} -> op{n["id"]};')
    out.append("}")
    return "\n".join(out)
