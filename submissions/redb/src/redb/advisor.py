"""Prescribe + what-if proof: Db2's index advisor with virtual indexes."""
from __future__ import annotations

import hashlib
import re
from typing import Any

IDENT = re.compile(r"^[A-Z0-9_#@$]+$")


def valid_ident(name: str) -> bool:
    return bool(name) and len(name) <= 128 and bool(IDENT.match(name))


def parse_colnames(colnames: str) -> list[tuple[str, str]]:
    """'+CUSTOMER_ID-ORDER_DATE' -> [('CUSTOMER_ID','ASC'), ('ORDER_DATE','DESC')]."""
    cols = re.findall(r"([+-])([^+-]+)", (colnames or "").strip())
    if not cols:
        raise ValueError(f"cannot parse COLNAMES {colnames!r}")
    return [(c.strip(), "ASC" if sign == "+" else "DESC") for sign, c in cols]


def index_ddl(schema: str, table: str, cols: list[tuple[str, str]], name: str | None = None) -> tuple[str, str, str]:
    """Return (index_name, create_ddl, undo_ddl). Raises on any unsafe identifier."""
    if name is None:
        h = hashlib.sha1(f"{schema}.{table}:{cols}".encode()).hexdigest()[:6].upper()
        name = f"REDB_IX_{table[:40]}_{h}"
    for ident in [schema, table, name, *[c for c, _ in cols]]:
        if not valid_ident(ident):
            raise ValueError(f"unsafe identifier {ident!r}")
    if any(d not in ("ASC", "DESC") for _, d in cols):
        raise ValueError("bad column direction")
    collist = ", ".join(f'"{c}" {d}' for c, d in cols)
    return (name, f'CREATE INDEX "{schema}"."{name}" ON "{schema}"."{table}" ({collist})',
            f'DROP INDEX "{schema}"."{name}"')


def has_parameter_markers(sql: str) -> bool:
    bare = re.sub(r"'(?:[^']|'')*'", "''", sql)
    return "?" in bare or bool(re.search(r"(?<![\w:]):[A-Za-z_]\w*", bare))


def clear_advice(db) -> None:
    db.execute("DELETE FROM ADVISE_INDEX")


def _compile(db, sql: str, mode: str) -> dict[str, Any] | None:
    """Compile (not run) `sql` under an explain mode; return the keys + cost of the plan Db2 stored."""
    marker = db.scalar("SELECT CHAR(CURRENT TIMESTAMP) FROM SYSIBM.SYSDUMMY1")
    try:
        db.exec_immediate(f"SET CURRENT EXPLAIN MODE {mode}")
        try:
            db.exec_immediate(sql)  # compiled, not executed: SQL0217W is expected
        except Exception as e:
            if "SQL0217W" not in str(e):
                raise
    finally:
        db.exec_immediate("SET CURRENT EXPLAIN MODE NO")
    rows = db.query("""SELECT CHAR(EXPLAIN_TIME) AS ET, SOURCE_NAME, STMTNO, SECTNO, TOTAL_COST
                       FROM EXPLAIN_STATEMENT
                       WHERE EXPLAIN_LEVEL = 'P' AND EXPLAIN_TIME >= TIMESTAMP(CAST(? AS VARCHAR(32)))
                       ORDER BY EXPLAIN_TIME DESC FETCH FIRST 1 ROW ONLY""", (marker,))
    return ({**rows[0], "marker": marker}) if rows else None


def recommend(db, sql: str, schema: str) -> dict[str, Any]:
    """Ask Db2 for virtual indexes. Returns est cost with them and the DDL to build them."""
    if has_parameter_markers(sql):
        return {"skipped": "statement has parameter markers", "indexes": [], "cost_with_indexes": None}
    keys = _compile(db, sql, "RECOMMEND INDEXES")
    if not keys:
        return {"skipped": "advisor produced no plan", "indexes": [], "cost_with_indexes": None}
    advised = db.query("""SELECT A.NAME, A.TBCREATOR, A.TBNAME, A.COLNAMES, A.NLEAF,
                            (SELECT S.PAGESIZE FROM SYSCAT.TABLES T JOIN SYSCAT.TABLESPACES S
                               ON S.TBSPACE = COALESCE(T.INDEX_TBSPACE, T.TBSPACE)
                              WHERE T.TABSCHEMA = A.TBCREATOR AND T.TABNAME = A.TBNAME) AS PAGESIZE
                          FROM ADVISE_INDEX A
                          WHERE A.EXISTS = 'N' AND A.EXPLAIN_TIME >= TIMESTAMP(CAST(? AS VARCHAR(32)))""",
                       (keys["marker"],))
    indexes, seen = [], set()
    for r in advised:
        tbschema, table = r["TBCREATOR"].strip(), r["TBNAME"].strip()
        if tbschema.upper() != schema.upper():
            continue
        cols = parse_colnames(r["COLNAMES"])
        name, ddl, undo = index_ddl(tbschema, table, cols)
        if name in seen:
            continue
        seen.add(name)
        size_mb = round(float(r["NLEAF"] or 0) * float(r["PAGESIZE"] or 4096) / 1_048_576, 1)
        indexes.append({"name": name, "advise_name": r["NAME"].strip(), "table": f"{tbschema}.{table}",
                        "columns": cols, "ddl": ddl, "undo": undo, "size_mb": size_mb})
    return {"skipped": None, "indexes": indexes, "cost_with_indexes": float(keys["TOTAL_COST"])}


def evaluate(db, sql: str, advise_names: list[str]) -> dict[str, Any] | None:
    """What-if: plan keys + cost of `sql` if exactly the given virtual indexes (ADVISE_INDEX.NAME) existed."""
    for n in advise_names:
        if not valid_ident(n):
            raise ValueError(f"unsafe advise index name {n!r}")
    inlist = ", ".join(f"'{n}'" for n in advise_names) or "''"
    db.execute(f"UPDATE ADVISE_INDEX SET USE_INDEX = CASE WHEN NAME IN ({inlist}) THEN 'Y' ELSE 'N' END")
    return _compile(db, sql, "EVALUATE INDEXES")


def consolidate(indexes: list[dict], total_cost, baseline: float, keep_gain: float = 0.95) -> tuple[list[dict], list[dict]]:
    """Greedy what-if pruning: drop an index (largest first) whenever the workload keeps >= keep_gain of the
    total cost reduction without it. `total_cost(kept)` prices the workload with a set of virtual indexes."""
    kept = list(indexes)
    full = total_cost(kept)
    allowed = full + (1 - keep_gain) * max(baseline - full, 0)
    dropped = []
    for idx in sorted(indexes, key=lambda i: -i.get("size_mb", 0)):
        trial = [k for k in kept if k is not idx]
        if total_cost(trial) <= allowed:
            kept = trial
            dropped.append(idx)
    return kept, dropped
