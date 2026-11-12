"""Syntax-aware rules: real vulnerable patterns are found; mentions in comments, docstrings and strings are not."""

import pytest

from shipsafe.analyzers.ast_rules import analyze_javascript, analyze_python, analyze_source


def rules(src: str):
    return [(h.rule_id, h.line) for h in analyze_python(src)]


@pytest.mark.parametrize("src, expected", [
    ('cur.execute(f"SELECT * FROM T WHERE ID = \'{uid}\'")', [("SQLI-DYNAMIC", 1)]),
    ('cur.execute("SELECT * FROM T WHERE ID = " + uid)', [("SQLI-DYNAMIC", 1)]),
    ('cur.execute("SELECT * FROM T WHERE ID = %s" % uid)', [("SQLI-DYNAMIC", 1)]),
    ('cur.execute("SELECT * FROM T WHERE ID = %s AND X = %s" % (a, b))', [("SQLI-DYNAMIC", 1)]),
    ('cur.execute("DELETE FROM T WHERE ID = {}".format(uid))', [("SQLI-DYNAMIC", 1)]),
    ('ibm_db.exec_immediate(conn, f"UPDATE T SET A = {v}")', [("SQLI-DYNAMIC", 1)]),
    ('sql = f"SELECT A FROM T WHERE B = {b}"\nq = sql\ncur.execute(q)', [("SQLI-DYNAMIC", 1)]),
    ('cur.execute(f"SELECT * FROM {SCHEMA}.T FETCH FIRST {int(n)} ROWS ONLY")', [("SQLI-IDENTIFIER", 1)]),
    ('cur.execute(f"SELECT * FROM {self.SCHEMA}.T")', [("SQLI-IDENTIFIER", 1)]),
    ('cur.execute("SELECT * FROM T WHERE ID = ?", (uid,))', []),
    ('cur.execute(f"select {1}")', [("SQLI-IDENTIFIER", 1)]),
    ('requests.get(f"https://x/update/{uid}")', []),                       # URL containing "update" (was a false alarm)
    ('cur.execute("SELECT 1")', []),
    ('subprocess.run(cmd, shell=True)', [("CMD-SHELL", 1)]),
    ('subprocess.run(["ls"], shell=False)', []),
    ('os.system(user_cmd)', [("CMD-SHELL", 1)]),
    ('os.system("ls")', []),
    ('eval(data)', [("CODE-EVAL", 1)]),
    ('exec(code)', [("CODE-EVAL", 1)]),
    ('eval("1 + 1")', []),
    ('"""Never call eval() on input."""', []),                              # docstring mention
    ('# eval(x) and shell=True are dangerous', []),                         # comment mention
    ('msg = "use subprocess.run(x, shell=True) carefully"', []),            # string mention
    ('pickle.loads(blob)', [("DESER-UNSAFE", 1)]),
    ('yaml.load(text)', [("DESER-UNSAFE", 1)]),
    ('yaml.load(text, Loader=yaml.FullLoader)', [("DESER-UNSAFE", 1)]),
    ('yaml.load(text, Loader=yaml.SafeLoader)', []),
    ('requests.get(url, verify=False)', [("TLS-VERIFY-OFF", 1)]),
    ('app.run(debug=True)', [("DEBUG-ENABLED", 1)]),
    ('app.run(debug=False)', []),
    ('tempfile.mktemp()', [("TEMPFILE-MKTEMP", 1)]),
])
def test_python_rules(src, expected):
    assert rules(src) == expected


def test_taint_is_scoped_per_function_and_cleared_on_reassignment():
    src = (
        "def a(x):\n"
        "    sql = f\"SELECT * FROM T WHERE ID = {x}\"\n"
        "    sql = \"SELECT * FROM T WHERE ID = ?\"\n"
        "    cur.execute(sql, (x,))\n"
        "def b():\n"
        "    cur.execute(sql)\n"
    )
    assert rules(src) == []


async_src = "async def f(x):\n    q = f\"DELETE FROM T WHERE ID = {x}\"\n    await cur.execute(q)\n"


def test_async_functions_are_checked():
    assert rules(async_src) == [("SQLI-DYNAMIC", 2)]


def test_same_rule_on_same_line_is_reported_once():
    assert rules("subprocess.run(a, shell=True); subprocess.call(b, shell=True)") == [("CMD-SHELL", 1)]


def test_unparseable_python_returns_nothing():
    assert analyze_python("def broken(:\n") == []


def test_hit_carries_guidance():
    hit = analyze_python('cur.execute(f"SELECT * FROM T WHERE A = {a}")')[0]
    assert hit.severity == "critical" and "?" in hit.remediation and hit.references
    assert hit.snippet.startswith("cur.execute")


@pytest.mark.parametrize("src, expected", [
    ("const r = eval(userInput);", ["JS-EVAL"]),
    ("const f = new Function('a', body);", ["JS-EVAL"]),
    ("el.innerHTML = html;", ["JS-INNERHTML"]),
    ("el.innerHTML = '';", []),
    ("exec(`git ${branch}`);", ["JS-CHILD-EXEC"]),
    ("child_process.execSync(cmd + arg);", ["JS-CHILD-EXEC"]),
    ("// eval(x) is bad", []),
    ("/* el.innerHTML = x */", []),
    ("const s = 'eval(x)';", []),
    ("const t = \"el.innerHTML = y\";", []),
    ("if (a.innerHTML == b) {}", []),
])
def test_javascript_rules(src, expected):
    assert [h.rule_id for h in analyze_javascript(src)] == expected


def test_dispatch_by_extension():
    assert analyze_source("eval(x)", "a.py")[0].rule_id == "CODE-EVAL"
    assert analyze_source("eval(x)", "a.tsx")[0].rule_id == "JS-EVAL"
    assert analyze_source("eval(x)", "a.go") == []
