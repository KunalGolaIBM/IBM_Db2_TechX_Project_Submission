"""Prove that a rewrite returns the same rows as the original, inside Db2."""
from __future__ import annotations

import re
from typing import Any


def _strip(sql: str) -> str:
    return sql.strip().rstrip(";").strip()


def equivalence_sql(a: str, b: str) -> str:
    a, b = _strip(a), _strip(b)
    return ("SELECT "
            f"(SELECT COUNT(*) FROM ((SELECT * FROM ({a}) X) EXCEPT ALL (SELECT * FROM ({b}) Y)) D1) AS A_MINUS_B, "
            f"(SELECT COUNT(*) FROM ((SELECT * FROM ({b}) X) EXCEPT ALL (SELECT * FROM ({a}) Y)) D2) AS B_MINUS_A "
            "FROM SYSIBM.SYSDUMMY1")


def has_outer_order_by(sql: str) -> bool:
    """True if ORDER BY appears at parenthesis depth 0 (i.e. on the outer query)."""
    depth, s = 0, re.sub(r"'(?:[^']|'')*'", "''", sql).upper()
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and s.startswith("ORDER BY", i) and (i == 0 or not s[i - 1].isalnum()):
            return True
    return False


def prove(db, original: str, rewrite: str) -> dict[str, Any]:
    """Equivalence on current data. Any error => not proven."""
    try:
        row = db.query(equivalence_sql(original, rewrite))[0]
        a_b, b_a = int(row["A_MINUS_B"]), int(row["B_MINUS_A"])
        ok = a_b == 0 and b_a == 0
        detail = f"EXCEPT ALL both ways: {a_b} / {b_a} differing rows"
        if ok and has_outer_order_by(original):
            ra = [tuple(r.values()) for r in db.query(_strip(original))]
            rb = [tuple(r.values()) for r in db.query(_strip(rewrite))]
            ok = ra == rb
            detail += "; ordered row lists " + ("match" if ok else "differ")
        return {"proven": ok, "detail": detail}
    except Exception as e:  # noqa: BLE001 - any failure means not proven
        return {"proven": False, "detail": f"not proven: {str(e)[:300]}"}
