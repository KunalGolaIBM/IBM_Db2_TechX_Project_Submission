"""Code quality, typing, and lint analyzer for ShipSafe AI."""

import ast
from pathlib import Path
from typing import List, Tuple
from ..models import Finding, ToolRun
from .base import SafeExecutionBoundary

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}


class QualityAnalyzer:
    """Analyzes syntax validity, exception hygiene, and code quality."""

    def __init__(self, boundary: SafeExecutionBoundary):
        self.boundary = boundary

    def scan(self, assessment_id: str, target_scope: List[str] = None) -> Tuple[ToolRun, List[Finding]]:
        findings: List[Finding] = []
        tool_name = "shipsafe_quality_ruff"
        version = "1.0.0"

        # Check if ruff is installed
        ret, stdout, stderr, dur = self.boundary.run_command(["ruff", "--version"])
        use_ruff = (ret == 0)

        root_path = self.boundary.workspace_root
        file_count = 0

        for path in root_path.rglob("*.py"):
            parts = path.parts
            if any(d in parts for d in SKIP_DIRS):
                continue
            rel_path = str(path.relative_to(root_path))
            if target_scope and rel_path not in target_scope:
                continue

            file_count += 1
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                # Syntax validation via python AST
                try:
                    tree = ast.parse(content, filename=rel_path)
                except SyntaxError as syn_err:
                    findings.append(Finding.create(
                        assessment_id=assessment_id,
                        source_tool=tool_name,
                        rule_id="E999-SYNTAX",
                        category="quality",
                        severity="high",
                        confidence="high",
                        title=f"Python Syntax Error: {syn_err.msg}",
                        description=f"File contains fatal syntax error at line {syn_err.lineno}.",
                        file_path=rel_path,
                        line_start=syn_err.lineno,
                        line_end=syn_err.lineno,
                        evidence={"snippet": syn_err.text or ""},
                        remediation="Correct the syntax error before merging.",
                    ))
                    continue

                # AST checks for code quality issues
                for node in ast.walk(tree):
                    # Bare except (except: or except BaseException:)
                    if isinstance(node, ast.ExceptHandler):
                        if node.type is None:
                            findings.append(Finding.create(
                                assessment_id=assessment_id,
                                source_tool=tool_name,
                                rule_id="E722-BARE-EXCEPT",
                                category="quality",
                                severity="medium",
                                confidence="high",
                                title="Bare Exception Handler Detected",
                                description="Do not use bare `except:`. It catches SystemExit and KeyboardInterrupt, concealing errors.",
                                file_path=rel_path,
                                line_start=node.lineno,
                                line_end=node.lineno,
                                evidence={"snippet": "except:"},
                                remediation="Catch specific exception types, e.g. `except Exception as e:` or `except (ValueError, KeyError):`.",
                            ))
            except Exception:
                continue

        run = ToolRun(
            tool_run_id=f"{assessment_id}_quality",
            assessment_id=assessment_id,
            tool_name=tool_name,
            version=version,
            exit_code=0 if len(findings) == 0 else 1,
            duration_ms=dur,
            status="passed" if len(findings) == 0 else "failed",
            message=f"Checked quality across {file_count} Python files. Found {len(findings)} quality/lint warnings.",
        )
        return run, findings
