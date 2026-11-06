"""Build guard: no string-built SQL.

Scans every module under src/asof, and every test, with the Python AST (no imports, no database) and fails on:

1. SQL text built at runtime. An f-string, a `%` or `+` expression, or a `.format()` call whose
   literal text looks like SQL may only interpolate `db.ident(...)` (or `ident(...)` inside db.py).
   Db2 cannot bind identifiers in DDL or GRANT, so setup code names objects through that one
   validating helper; values are always `?` parameters.
2. Runtime modules passing anything but a literal to the database. In the modules that serve
   requests, the SQL argument of db.query, db.execute and callproc must be a string literal or
   a module-level string constant.

Two documented exceptions build no SQL from input: schema.load_statements substitutes the
validated schema name for the `ASOF.` token in the bundled DDL files, and seed.faq_store gives
langchain-db2 a validated table name. Both are covered by the identifier tests below.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from asof import db

SRC = Path(__file__).resolve().parents[1] / "src" / "asof"
TESTS = Path(__file__).resolve().parent
RUNTIME = {"api.py", "gate.py", "checkgraph.py", "impactagent.py", "ledger.py", "policy.py", "retriever.py",
           "assistant.py", "integration.py"}
# Statement shapes, matched on the literal text of a string with its placeholders removed,
# so "SELECT * FROM {t} WHERE ..." is caught but an error message like "CALL {proc} failed" is not.
SQL_TEXT = re.compile(
    r"\bselect\b.+\bfrom\b|\binsert\s+into\b|\bdelete\s+from\b|\bupdate\b\s+\S*\s*\bset\b|\bmerge\s+into\b"
    r"|^\s*call\b\s*\S*\s*\(|\b(create|drop|alter)\s+(or\s+replace\s+)?(table|view|index|schema|procedure|function"
    r"|trigger|specific|external\s+model)\b|\b(grant|revoke)\b.+\b(on|to|from)\b|\bset\s+current\b|^\s*values\b"
    r"|\bwhere\b.+[=<>]",
    re.I | re.S)
SAFE_CALLS = {"ident", "string_literal"}


def _literal_text(node: ast.AST) -> str:
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _is_ident_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    return (isinstance(f, ast.Attribute) and f.attr in SAFE_CALLS) or (isinstance(f, ast.Name) and f.id in SAFE_CALLS)


def _looks_like_sql(text: str) -> bool:
    return bool(SQL_TEXT.search(text))


def violations(source: str, filename: str) -> list[str]:
    tree = ast.parse(source, filename)
    found: list[str] = []
    module_constants = {
        t.id for n in tree.body if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
        and isinstance(n.value.value, str) for t in n.targets if isinstance(t, ast.Name)
    }
    for node in ast.walk(tree):
        where = f"{filename}:{getattr(node, 'lineno', '?')}"
        if isinstance(node, ast.JoinedStr) and _looks_like_sql(_literal_text(node)):
            bad = [v for v in node.values if isinstance(v, ast.FormattedValue) and not _is_ident_call(v.value)]
            if bad:
                found.append(f"{where}: f-string builds SQL from {ast.unparse(bad[0].value)!r}")
        elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mod, ast.Add)):
            texts = [_literal_text(node.left), _literal_text(node.right)]
            others = [x for x in (node.left, node.right) if not isinstance(x, ast.Constant)]
            if any(_looks_like_sql(t) for t in texts) and any(not _is_ident_call(x) for x in others):
                found.append(f"{where}: SQL built with {type(node.op).__name__}")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format" \
                and _looks_like_sql(_literal_text(node.func.value)):
            found.append(f"{where}: SQL built with .format()")
        if Path(filename).name in RUNTIME and isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            arg = None
            if name in {"query", "execute"} and isinstance(f, ast.Attribute) and getattr(f.value, "id", "") == "db":
                arg = node.args[1] if len(node.args) > 1 else None
            elif name == "callproc":
                arg = node.args[0] if node.args else None
            if arg is not None and not (
                (isinstance(arg, ast.Constant) and isinstance(arg.value, str))
                or (isinstance(arg, ast.Name) and arg.id in module_constants)
            ):
                found.append(f"{where}: runtime {name}() gets a non-literal SQL argument {ast.unparse(arg)!r}")
    return found


def test_no_string_built_sql_anywhere_in_the_package_or_its_tests():
    files = sorted(SRC.rglob("*.py")) + sorted(TESTS.glob("*.py"))
    assert len(files) > 30
    problems = [v for f in files for v in violations(f.read_text(encoding="utf-8"), f.name)]
    assert not problems, "string-built SQL found:\n" + "\n".join(problems)


@pytest.mark.parametrize("snippet", [
    'db.query(conn, f"SELECT * FROM POLICY_CLAUSE WHERE CLAUSE_ID = {cid}")',
    'sql = f"DELETE FROM {schema}.ANSWER_LEDGER"',
    'sql = "SELECT * FROM T WHERE NAME = \'" + name + "\'"',
    'sql = "UPDATE T SET X = %s" % value',
    'sql = "SELECT * FROM {}".format(table)',
])
def test_the_scanner_catches_string_built_sql(snippet):
    assert violations(snippet, "ledger.py"), snippet


def test_the_scanner_accepts_validated_identifiers_and_literals():
    assert violations('db.execute(conn, f"DROP TABLE {db.ident(schema)}.{db.ident(name)}")', "schema.py") == []
    ok = "\n".join([
        'SQL_X = "SELECT 1 FROM SYSIBM.SYSDUMMY1"',
        'db.query(conn, SQL_X, (1,))',
        'db.query(conn, "SELECT COUNT(*) FROM ANSWER_LEDGER WHERE DECISION = ?", (d,))',
        'msg = f"unknown clause {clause_id}"',
        'err = f"CALL {proc} failed"',
        'note = f"Schema {name} was removed."',
    ])
    assert violations(ok, "ledger.py") == []


def test_runtime_modules_pass_only_literals_to_the_database():
    assert violations('db.query(conn, sql_from_somewhere, ())', "policy.py")
    assert violations('cur.callproc(schema + ".APPEND_LEDGER", p)', "ledger.py")
    assert violations('db.execute(conn, f"DROP TABLE {db.ident(schema)}.X")', "ledger.py")


@pytest.mark.parametrize("bad", ["asof;drop table x", 'A"B', "a b", "X.Y", "", "1ABC", "ÄBC", "x" * 129])
def test_ident_rejects_anything_but_a_plain_identifier(bad):
    with pytest.raises(ValueError):
        db.ident(bad)


def test_ident_upper_cases_user_names_the_way_db2_stores_them():
    assert db.ident("asofapp") == "ASOFAPP"
    assert db.ident("ASOF_TEST") == "ASOF_TEST"


@pytest.mark.parametrize("bad", ["asof", "ASOF;", "ASOF.X", "A" * 31, ""])
def test_schema_names_are_validated_before_they_reach_the_connection(bad):
    with pytest.raises(ValueError):
        db.validate_schema(bad)
    with pytest.raises(ValueError):
        db.use_schema(object(), bad)  # type: ignore[arg-type]
