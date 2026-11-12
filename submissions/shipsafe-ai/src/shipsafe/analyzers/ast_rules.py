"""Syntax-aware security rules.

Python files are parsed with the standard-library `ast` module, so code that
only *mentions* a dangerous call (in a comment, docstring or string literal)
is never reported. JavaScript/TypeScript files get comment- and string-aware
token rules. Every rule returns plain `RuleHit`s; the caller turns them into
`Finding`s so the same rules serve both workspace scans and the IDE guard.
"""

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

SQL_START = re.compile(r"^\s*\(?\s*(SELECT|INSERT|UPDATE|DELETE|MERGE|WITH|CREATE|DROP|ALTER|TRUNCATE|CALL)\b", re.I)
SQL_SINKS = {"execute", "executemany", "executescript", "exec_immediate", "prepare", "raw", "read_sql", "read_sql_query"}
SUBPROCESS_FUNCS = {"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}
_EXECUTE_RESULT = "<result of ibm_db.execute>"
_STRIP_SQL_LITERALS = re.compile(r"'(?:[^']|'')*'")
CONSTANT_NAME = re.compile(r"^_?[A-Z][A-Z0-9_]*$")


@dataclass
class RuleHit:
    rule_id: str
    severity: str
    confidence: str
    title: str
    description: str
    remediation: str
    line: int
    end_line: int
    snippet: str
    references: List[str] = field(default_factory=list)


RULES: Dict[str, Dict[str, object]] = {
    "SQLI-DYNAMIC": dict(
        severity="critical", confidence="high", title="SQL built from runtime values",
        description="A SQL statement is assembled from runtime values (f-string, concatenation, % or .format) "
                    "and passed to a database call. Untrusted input in that value is SQL injection.",
        remediation="Use parameter markers and pass values separately: "
                    "`cur.execute(\"SELECT * FROM T WHERE ID = ?\", (user_id,))`.",
        references=["https://www.ibm.com/docs/en/db2/12.1?topic=statements-parameter-markers"]),
    "SQLI-IDENTIFIER": dict(
        severity="low", confidence="medium", title="SQL text includes interpolated constants",
        description="The SQL text interpolates only constants or validated identifiers. This is not injectable as "
                    "written, but the identifiers must stay out of user control.",
        remediation="Keep identifiers in an allow-list or validate them (letters, digits, underscore) before use.",
        references=[]),
    "CMD-SHELL": dict(
        severity="high", confidence="high", title="Process started through the shell",
        description="`shell=True` (or os.system/os.popen) passes the command to a shell, so any untrusted text in it "
                    "can run extra commands.",
        remediation="Pass an argument list with `shell=False`: `subprocess.run([\"git\", \"status\"], check=True)`.",
        references=["https://docs.python.org/3/library/subprocess.html#security-considerations"]),
    "CODE-EVAL": dict(
        severity="critical", confidence="high", title="eval()/exec() on a non-literal value",
        description="eval() and exec() run arbitrary code. Called on anything except a fixed literal this is "
                    "remote code execution if the value can be influenced.",
        remediation="Use `ast.literal_eval()` for data, `json.loads()` for JSON, or an explicit dispatch table.",
        references=[]),
    "DESER-UNSAFE": dict(
        severity="high", confidence="medium", title="Unsafe deserialization",
        description="pickle/marshal/yaml.load can execute code while loading untrusted data.",
        remediation="Use JSON, or `yaml.safe_load()`. Only unpickle data you produced and authenticated.",
        references=[]),
    "TLS-VERIFY-OFF": dict(
        severity="high", confidence="high", title="TLS certificate verification disabled",
        description="`verify=False` accepts any certificate, so traffic can be intercepted.",
        remediation="Remove `verify=False`; point `verify=` at a CA bundle if you use a private CA.",
        references=[]),
    "DEBUG-ENABLED": dict(
        severity="medium", confidence="high", title="Debug mode enabled in application start-up",
        description="Running with debug=True exposes an interactive debugger and stack traces.",
        remediation="Read debug from configuration and default it to False in production.",
        references=[]),
    "DB2-API-MISUSE": dict(
        severity="high", confidence="high", title="ibm_db call that fails at runtime",
        description="exec_immediate runs a finished SQL string, so a statement with ? markers (or a tuple) fails; "
                    "and ibm_db.execute() returns True/False, so rows must be fetched from the statement, not from "
                    "its return value.",
        remediation="Prepare once and bind values: `stmt = ibm_db.prepare(conn, sql)` then "
                    "`ibm_db.execute(stmt, (value,))`, then `ibm_db.fetch_assoc(stmt)`.",
        references=["https://github.com/ibmdb/python-ibmdb/wiki/APIs#ibm_dbprepare"]),
    "TEMPFILE-MKTEMP": dict(
        severity="medium", confidence="high", title="Insecure temporary file name",
        description="tempfile.mktemp() returns a name that another process can claim first.",
        remediation="Use `tempfile.NamedTemporaryFile()` or `tempfile.mkstemp()`.",
        references=[]),
    "JS-EVAL": dict(
        severity="critical", confidence="medium", title="eval()/new Function() in JavaScript",
        description="Dynamic code evaluation runs arbitrary code.",
        remediation="Parse data with JSON.parse or use an explicit dispatch table.",
        references=[]),
    "JS-INNERHTML": dict(
        severity="high", confidence="medium", title="Assignment to innerHTML/outerHTML",
        description="Writing HTML built from variables enables cross-site scripting.",
        remediation="Use textContent, or sanitise with a vetted library before inserting HTML.",
        references=[]),
    "JS-CHILD-EXEC": dict(
        severity="high", confidence="medium", title="child_process.exec with a dynamic command",
        description="exec() runs the command through a shell.",
        remediation="Use execFile/spawn with an argument array.",
        references=[]),
}


def _hit(rule_id: str, node: ast.AST, lines: List[str]) -> RuleHit:
    meta = RULES[rule_id]
    line = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", line) or line
    snippet = lines[line - 1].strip() if 0 < line <= len(lines) else ""
    return RuleHit(rule_id=rule_id, severity=meta["severity"], confidence=meta["confidence"],  # type: ignore[arg-type]
                   title=meta["title"], description=meta["description"], remediation=meta["remediation"],  # type: ignore[arg-type]
                   line=line, end_line=end, snippet=snippet[:300], references=list(meta["references"]))  # type: ignore[arg-type]


def _call_name(node: ast.Call) -> str:
    """Dotted name of the called function, e.g. 'subprocess.run' or 'cur.execute'."""
    parts: List[str] = []
    cur: ast.AST = node.func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _is_safe_interpolation(expr: ast.AST) -> bool:
    """True for values that cannot carry user text: constants, ALL_CAPS names, int()/len() casts."""
    if isinstance(expr, ast.Constant):
        return True
    if isinstance(expr, ast.Name):
        return bool(CONSTANT_NAME.match(expr.id))
    if isinstance(expr, ast.Attribute):
        return bool(CONSTANT_NAME.match(expr.attr))
    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id in ("int", "float", "len", "bool"):
        return True
    return False


class _SqlShape:
    """Classifies an expression that builds a string: static, dynamic-safe or dynamic-unsafe."""

    def __init__(self, tainted_names: Dict[str, tuple]):
        self.tainted = tainted_names  # variable name -> ("unsafe" | "identifier", node where the SQL was built)

    def literal_text(self, expr: ast.AST) -> Optional[str]:
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return expr.value
        if isinstance(expr, ast.JoinedStr):
            return "".join(v.value for v in expr.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
        if isinstance(expr, ast.BinOp):
            left, right = self.literal_text(expr.left), self.literal_text(expr.right)
            return (left or "") + (right or "") if (left or right) else None
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr == "format":
            return self.literal_text(expr.func.value)
        return None

    def classify(self, expr: ast.AST) -> Optional[str]:
        """None (not dynamic SQL), 'unsafe' or 'identifier'."""
        if isinstance(expr, ast.Name) and expr.id in self.tainted:
            return self.tainted[expr.id][0]
        text = self.literal_text(expr)
        if not text or not SQL_START.search(text):
            return None
        dynamic: List[ast.AST] = []
        if isinstance(expr, ast.JoinedStr):
            dynamic = [v.value for v in expr.values if isinstance(v, ast.FormattedValue)]
        elif isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.Mod)):
            dynamic = [n for n in (expr.left, expr.right) if self.literal_text(n) is None]
            if isinstance(expr.op, ast.Mod) and isinstance(expr.right, ast.Tuple):
                dynamic = list(expr.right.elts)
        elif isinstance(expr, ast.Call):
            dynamic = list(expr.args) + [k.value for k in expr.keywords]
        if not dynamic:
            return None
        return "identifier" if all(_is_safe_interpolation(d) for d in dynamic) else "unsafe"


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self, lines: List[str]):
        self.lines = lines
        self.hits: List[RuleHit] = []
        self.scopes: List[Dict[str, tuple]] = [{}]
        self.literals: List[Dict[str, str]] = [{}]  # variable -> constant string it holds (per function)
        self._seen: Set[tuple] = set()

    def _add(self, rule_id: str, node: ast.AST) -> None:
        key = (rule_id, getattr(node, "lineno", 0))
        if key not in self._seen:
            self._seen.add(key)
            self.hits.append(_hit(rule_id, node, self.lines))

    # Track variables that hold dynamic SQL so `sql = f"..."; cur.execute(sql)` is caught.
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scopes.append({})
        self.literals.append({})
        self.generic_visit(node)
        self.scopes.pop()
        self.literals.pop()

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_Assign(self, node: ast.Assign) -> None:
        shape = _SqlShape(self.scopes[-1]).classify(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                if shape:
                    origin = node.value
                    if isinstance(node.value, ast.Name) and node.value.id in self.scopes[-1]:
                        origin = self.scopes[-1][node.value.id][1]
                    self.scopes[-1][target.id] = (shape, origin)
                else:
                    self.scopes[-1].pop(target.id, None)
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    self.literals[-1][target.id] = node.value.value
                elif isinstance(node.value, ast.Call) and _call_name(node.value) == "ibm_db.execute":
                    self.literals[-1][target.id] = _EXECUTE_RESULT
                else:
                    self.literals[-1].pop(target.id, None)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _call_name(node)
        leaf = name.rsplit(".", 1)[-1]
        kw = {k.arg: k.value for k in node.keywords if k.arg}

        if leaf in SQL_SINKS and node.args:
            # ibm_db.exec_immediate(conn, sql) / ibm_db.prepare(conn, sql) take SQL second.
            sql_arg = node.args[1] if name.startswith("ibm_db.") and len(node.args) > 1 else node.args[0]
            shape = _SqlShape(self.scopes[-1]).classify(sql_arg)
            # Report where the SQL text is built: that is the line to fix (and where Bandit reports it).
            where = self.scopes[-1][sql_arg.id][1] if isinstance(sql_arg, ast.Name) and sql_arg.id in self.scopes[-1] else node
            if shape == "unsafe":
                self._add("SQLI-DYNAMIC", where)
            elif shape == "identifier":
                self._add("SQLI-IDENTIFIER", where)

        shell = kw.get("shell")
        if (name.startswith("subprocess.") or leaf in SUBPROCESS_FUNCS) and isinstance(shell, ast.Constant) and shell.value is True:
            self._add("CMD-SHELL", node)
        if name in ("os.system", "os.popen") and node.args and not isinstance(node.args[0], ast.Constant):
            self._add("CMD-SHELL", node)

        if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec") and node.args \
                and not isinstance(node.args[0], ast.Constant):
            self._add("CODE-EVAL", node)

        if name in ("pickle.load", "pickle.loads", "marshal.load", "marshal.loads", "cPickle.loads", "dill.loads"):
            self._add("DESER-UNSAFE", node)
        if name == "yaml.load":
            loader = kw.get("Loader") or (node.args[1] if len(node.args) > 1 else None)
            loader_name = ast.unparse(loader) if loader is not None else ""
            if "Safe" not in loader_name:
                self._add("DESER-UNSAFE", node)

        verify = kw.get("verify")
        if isinstance(verify, ast.Constant) and verify.value is False:
            self._add("TLS-VERIFY-OFF", node)
        debug = kw.get("debug")
        if leaf == "run" and isinstance(debug, ast.Constant) and debug.value is True:
            self._add("DEBUG-ENABLED", node)
        if name in ("tempfile.mktemp", "mktemp"):
            self._add("TEMPFILE-MKTEMP", node)
        if name == "ibm_db.exec_immediate" and len(node.args) > 1:
            stmt = node.args[1]
            text = stmt.value if isinstance(stmt, ast.Constant) and isinstance(stmt.value, str) else \
                self.literals[-1].get(stmt.id) if isinstance(stmt, ast.Name) else None
            if isinstance(stmt, ast.Tuple) or (text and "?" in _STRIP_SQL_LITERALS.sub("''", text)) or len(node.args) > 2:
                self._add("DB2-API-MISUSE", node)
        if name.startswith("ibm_db.fetch_") and node.args and isinstance(node.args[0], ast.Name)                 and self.literals[-1].get(node.args[0].id) == _EXECUTE_RESULT:
            self._add("DB2-API-MISUSE", node)
        self.generic_visit(node)


def analyze_python(source: str) -> List[RuleHit]:
    """Run the Python rules. Returns [] for files that do not parse (they are reported elsewhere)."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    visitor = _PythonVisitor(source.splitlines())
    visitor.visit(tree)
    return sorted(visitor.hits, key=lambda h: (h.line, h.rule_id))


# ---------------------------------------------------------------- JavaScript
_JS_TOKEN = re.compile(r"""//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'|`(?:\\.|[^`\\])*`""", re.S)


def _blank_js(source: str) -> str:
    """Replace comments and plain string contents with spaces (line numbers preserved).

    Template literals keep their `${...}` parts visible so dynamic commands are detectable."""
    def repl(m: "re.Match[str]") -> str:
        tok = m.group(0)
        if tok.startswith("`") and "${" in tok:
            return tok
        if tok.startswith(("//", "/*")):
            return re.sub(r"[^\n]", " ", tok)
        return tok[0] + re.sub(r"[^\n]", " ", tok[1:-1]) + tok[-1]
    return _JS_TOKEN.sub(repl, source)


_JS_RULES = [
    ("JS-EVAL", re.compile(r"(?<![\w.$])(?:eval\s*\(\s*(?!['\"]\s*\))|new\s+Function\s*\()")),
    ("JS-INNERHTML", re.compile(r"\.(?:innerHTML|outerHTML)\s*=(?!=)(?!\s*['\"]\s*['\"]\s*;?\s*$)")),
    ("JS-CHILD-EXEC", re.compile(r"(?<![\w$])(?:child_process\.)?exec(?:Sync)?\s*\(\s*(?:`[^`]*\$\{|[A-Za-z_$][\w$]*\s*[+,)])")),
]


def analyze_javascript(source: str) -> List[RuleHit]:
    clean = _blank_js(source)
    original = source.splitlines()
    hits: List[RuleHit] = []
    for idx, line in enumerate(clean.splitlines(), 1):
        for rule_id, pattern in _JS_RULES:
            if pattern.search(line):
                meta = RULES[rule_id]
                hits.append(RuleHit(rule_id=rule_id, severity=meta["severity"], confidence=meta["confidence"],  # type: ignore[arg-type]
                                    title=meta["title"], description=meta["description"],  # type: ignore[arg-type]
                                    remediation=meta["remediation"], line=idx, end_line=idx,  # type: ignore[arg-type]
                                    snippet=original[idx - 1].strip()[:300], references=list(meta["references"])))  # type: ignore[arg-type]
    return hits


JS_SUFFIXES = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")


def analyze_source(source: str, filename: str) -> List[RuleHit]:
    """Dispatch on file extension."""
    lower = filename.lower()
    if lower.endswith(".py"):
        return analyze_python(source)
    if lower.endswith(JS_SUFFIXES):
        return analyze_javascript(source)
    return []
