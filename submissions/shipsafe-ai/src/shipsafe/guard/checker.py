"""Check a piece of code *before* the AI assistant writes it to disk.

This is the core of ShipSafe inside an AI IDE. Bob (or Claude, Cursor, VS Code)
sends the code it is about to write; ShipSafe answers in well under a second
with a verdict and concrete issues, so the assistant can correct itself before
the code ever lands in the project.

Checks run on the text only: syntax-aware rules, secret patterns, a syntax
check, and Bandit (run on a temporary copy, never on the user's file).
"""

import ast
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..analyzers.ast_rules import JS_SUFFIXES, analyze_source
from ..analyzers.base import redact_secrets
from ..analyzers.external import BANDIT_ESCALATE, BANDIT_SEVERITY, tool_available
from ..findings.normalizer import SEVERITY_RANK, rule_family
from ..analyzers.secrets import find_secrets

MAX_CODE_BYTES = 400_000
LANGUAGES = {".py": "python", ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
             ".ts": "typescript", ".tsx": "typescript", ".sql": "sql", ".java": "java", ".go": "go"}


@dataclass
class GuardIssue:
    rule_id: str
    severity: str
    category: str
    title: str
    line: int
    snippet: str
    why: str
    fix: str
    sources: List[str] = field(default_factory=list)
    policy: Optional[Dict[str, Any]] = None


@dataclass
class GuardResult:
    verdict: str                     # clean | warn | block
    language: str
    issues: List[GuardIssue]
    duration_ms: int
    checks: List[str]
    filename: str = ""

    @property
    def max_severity(self) -> Optional[str]:
        return max((i.severity for i in self.issues), key=lambda s: SEVERITY_RANK.get(s, 0), default=None)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["max_severity"] = self.max_severity
        d["summary"] = self.summary()
        return d

    def summary(self) -> str:
        if not self.issues:
            return f"No issues found in {self.filename or 'the code'} ({', '.join(self.checks)})."
        worst = self.max_severity
        return (f"{len(self.issues)} issue(s) in {self.filename or 'the code'}, worst: {worst}. "
                + ("Do not write this code as-is; fix the blocking issues first." if self.verdict == "block"
                   else "Safe to write, but consider the warnings."))


def language_for(filename: str) -> str:
    return LANGUAGES.get(Path(filename).suffix.lower(), "text")


def _verdict(issues: List[GuardIssue]) -> str:
    worst = max((SEVERITY_RANK.get(i.severity, 0) for i in issues), default=-1)
    if worst >= SEVERITY_RANK["high"]:
        return "block"
    return "warn" if issues else "clean"


def _bandit_on_text(code: str, timeout: int = 60) -> List[GuardIssue]:
    """Run Bandit on a temporary copy of the code. Returns [] if Bandit is not installed."""
    if not tool_available("bandit"):  # pragma: no cover - bandit is a declared dependency
        return []
    with tempfile.TemporaryDirectory(prefix="shipsafe-guard-") as tmp:
        target = Path(tmp) / "snippet.py"
        target.write_text(code, encoding="utf-8")
        proc = subprocess.run([sys.executable, "-m", "bandit", "-f", "json", "-q", str(target)],
                              capture_output=True, text=True, timeout=timeout, shell=False,
                              stdin=subprocess.DEVNULL)
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:  # pragma: no cover - only if a bandit release breaks its JSON format
        return []
    issues = []
    for r in data.get("results", []):
        test_id = r.get("test_id", "B000")
        issues.append(GuardIssue(
            rule_id=f"{test_id}-{r.get('test_name', 'check')}".upper()[:64],
            severity=BANDIT_ESCALATE.get(test_id, BANDIT_SEVERITY.get(r.get("issue_severity", "LOW"), "low")),
            category="security", title=f"Bandit {test_id}: {r.get('issue_text', '').strip()}"[:200],
            line=int(r.get("line_number") or 1), snippet=redact_secrets((r.get("code") or "").strip())[:300],
            why=redact_secrets(r.get("issue_text", "")), fix=f"See {r.get('more_info')}" if r.get("more_info") else "",
            sources=["bandit"]))
    return issues


def _merge(issues: List[GuardIssue]) -> List[GuardIssue]:
    """One issue per (line, rule family): keep the most severe and list every tool that found it."""
    merged: Dict[tuple, GuardIssue] = {}
    for issue in issues:
        key = (issue.line, rule_family(issue.rule_id) or issue.rule_id)
        keep = merged.get(key)
        if keep is None:
            merged[key] = issue
            continue
        if SEVERITY_RANK.get(issue.severity, 0) > SEVERITY_RANK.get(keep.severity, 0):
            issue.sources = sorted(set(issue.sources + keep.sources))
            merged[key] = issue
        else:
            keep.sources = sorted(set(keep.sources + issue.sources))
    return sorted(merged.values(), key=lambda i: (-SEVERITY_RANK.get(i.severity, 0), i.line))


def check_code(code: str, filename: str = "snippet.py", use_bandit: bool = True) -> GuardResult:
    """Check code text. Pure function of its input: no files of the user are read or written."""
    started = time.perf_counter()
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        raise ValueError(f"Code is larger than {MAX_CODE_BYTES // 1000} KB; check the file with check_files instead.")
    language = language_for(filename)
    checks = ["secrets"]
    issues: List[GuardIssue] = []

    for rule, line, snippet in find_secrets(code):
        issues.append(GuardIssue(rule_id=rule["id"], severity=rule["severity"], category="secrets", title=rule["name"],
                                 line=line, snippet=snippet, why="A credential in source code is readable by anyone "
                                 "with access to the repository, its history and its build logs.",
                                 fix=rule["remediation"], sources=["shipsafe_secrets"]))

    if language == "python":
        checks.append("syntax")
        try:
            ast.parse(code)
        except SyntaxError as exc:
            issues.append(GuardIssue(rule_id="PY-SYNTAX", severity="high", category="quality",
                                     title=f"Python syntax error: {exc.msg}", line=int(exc.lineno or 1),
                                     snippet=(exc.text or "").strip()[:300], why="The file will not import.",
                                     fix="Fix the syntax error before writing the file.", sources=["python"]))
    if language == "python" or filename.lower().endswith(JS_SUFFIXES):
        checks.append("code-rules")
        for h in analyze_source(code, filename):
            issues.append(GuardIssue(rule_id=h.rule_id, severity=h.severity, category="security", title=h.title,
                                     line=h.line, snippet=redact_secrets(h.snippet), why=h.description,
                                     fix=h.remediation, sources=["shipsafe_code_rules"]))
    if language == "python" and use_bandit and tool_available("bandit"):
        checks.append("bandit")
        issues.extend(_bandit_on_text(code))

    merged = _merge(issues)
    return GuardResult(verdict=_verdict(merged), language=language, issues=merged,
                       duration_ms=int((time.perf_counter() - started) * 1000), checks=checks, filename=filename)
