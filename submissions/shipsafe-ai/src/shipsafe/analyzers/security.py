"""Code-security analyzer for workspaces (Python AST rules + JS/TS token rules)."""

import time
from typing import List, Optional, Tuple

from ..models import Finding, ToolRun
from .ast_rules import JS_SUFFIXES, RuleHit, analyze_source
from .base import SafeExecutionBoundary, redact_secrets

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".mypy_cache", ".pytest_cache"}
SOURCE_SUFFIXES = (".py",) + JS_SUFFIXES
TOOL_NAME = "shipsafe_code_rules"
MAX_FILE_BYTES = 1_500_000


def hit_to_finding(hit: RuleHit, assessment_id: str, rel_path: Optional[str]) -> Finding:
    return Finding.create(
        assessment_id=assessment_id, source_tool=TOOL_NAME, rule_id=hit.rule_id, category="security",
        severity=hit.severity, confidence=hit.confidence, title=hit.title, description=hit.description,
        file_path=rel_path, line_start=hit.line, line_end=hit.end_line,
        evidence={"snippet": redact_secrets(hit.snippet)}, remediation=hit.remediation, references=hit.references,
    )


class SecurityAnalyzer:
    """Runs the syntax-aware rules over every Python / JS / TS file in scope."""

    def __init__(self, boundary: SafeExecutionBoundary):
        self.boundary = boundary

    def scan(self, assessment_id: str, target_scope: Optional[List[str]] = None) -> Tuple[ToolRun, List[Finding]]:
        started = time.perf_counter()
        root = self.boundary.workspace_root
        findings: List[Finding] = []
        file_count = 0
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            rel_path = path.relative_to(root).as_posix()
            if target_scope and rel_path not in target_scope:
                continue
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            file_count += 1
            source = path.read_text(encoding="utf-8", errors="ignore")
            findings.extend(hit_to_finding(h, assessment_id, rel_path) for h in analyze_source(source, rel_path))

        run = ToolRun(
            tool_run_id=f"{assessment_id}_sast",
            assessment_id=assessment_id,
            tool_name=TOOL_NAME,
            version="2.0.0",
            exit_code=1 if findings else 0,
            duration_ms=int((time.perf_counter() - started) * 1000),
            status="failed" if findings else "passed",
            message=f"Syntax-aware rules checked {file_count} source files and found {len(findings)} issues.",
        )
        return run, findings
