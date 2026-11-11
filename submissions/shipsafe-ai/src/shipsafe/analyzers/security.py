"""Static Application Security Testing (SAST) analyzer for ShipSafe AI."""

import ast
import re
from pathlib import Path
from typing import List, Tuple
from ..models import Finding, ToolRun
from .base import SafeExecutionBoundary, redact_secrets

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}


class SecurityAnalyzer:
    """Detects security vulnerabilities: SQL injection, command injection, unsafe deserialization."""

    def __init__(self, boundary: SafeExecutionBoundary):
        self.boundary = boundary

    def scan(self, assessment_id: str, target_scope: List[str] = None) -> Tuple[ToolRun, List[Finding]]:
        findings: List[Finding] = []
        tool_name = "shipsafe_sast_bandit"
        version = "1.0.0"

        # Check if bandit is installed
        ret, stdout, stderr, dur = self.boundary.run_command(["bandit", "--version"])
        use_bandit = (ret == 0)

        # Built-in deterministic SAST rules (Python AST & pattern analysis)
        root_path = self.boundary.workspace_root
        file_count = 0

        # Pattern definitions
        sql_concat_pattern = re.compile(r'(?i)(?:cursor\.execute|db2\.exec_immediate|raw_sql|execute_query)\s*\(\s*(?:f["\']|["\'].*?\%.*?["\']\s*\%|["\'].*?\+\s*\w+)')
        # f-string SQL built with interpolated values, e.g. f"SELECT ... WHERE ID = '{user_id}'"
        sql_fstring_pattern = re.compile(r"""(?i)\bf(["'])(?=(?:(?!\1).)*\b(?:SELECT|INSERT|UPDATE|DELETE|MERGE)\b)(?:(?!\1).)*\{[^}]+\}""")
        shell_true_pattern = re.compile(r'subprocess\.(?:run|Popen|call|check_output)\s*\(.*shell\s*=\s*True.*')
        eval_exec_pattern = re.compile(r'\b(?:eval|exec)\s*\((?!\s*["\']\s*\))')
        pickle_pattern = re.compile(r'\bpickle\.loads?\s*\(')
        insecure_temp_pattern = re.compile(r'\bmktemp\s*\(')

        for path in root_path.rglob("*.py"):
            parts = path.parts
            if any(d in parts for d in SKIP_DIRS):
                continue
            rel_path = path.relative_to(root_path).as_posix()
            if target_scope and rel_path not in target_scope:
                continue

            file_count += 1
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()

                for line_idx, line in enumerate(lines, 1):
                    # 1. SQL Injection / Db2 raw execution without parameterization
                    if sql_concat_pattern.search(line) or sql_fstring_pattern.search(line):
                        findings.append(Finding.create(
                            assessment_id=assessment_id,
                            source_tool=tool_name,
                            rule_id="B608-SQLI",
                            category="security",
                            severity="critical",
                            confidence="high",
                            title="Potential SQL Injection / Unparameterized Query",
                            description="Database query constructed via dynamic string formatting or concatenation. IBM Db2 queries must use parameterized markers (?) to prevent SQL injection.",
                            file_path=rel_path,
                            line_start=line_idx,
                            line_end=line_idx,
                            evidence={"snippet": line.strip()},
                            remediation="Refactor to use parameterized SQL queries with query markers (e.g., `ibm_db.execute(stmt, (param1, param2))` or parameter tuple). Never format user input directly into SQL strings.",
                            references=["https://www.ibm.com/docs/en/db2/11.5?topic=sql-parameter-markers"],
                        ))

                    # 2. Command injection via shell=True
                    if shell_true_pattern.search(line):
                        findings.append(Finding.create(
                            assessment_id=assessment_id,
                            source_tool=tool_name,
                            rule_id="B602-SUBPROCESS-SHELL",
                            category="security",
                            severity="high",
                            confidence="high",
                            title="Subprocess Executed with shell=True",
                            description="Spawning a process with `shell=True` exposes the application to arbitrary shell command injection.",
                            file_path=rel_path,
                            line_start=line_idx,
                            line_end=line_idx,
                            evidence={"snippet": line.strip()},
                            remediation="Set `shell=False` and pass command arguments as an array of validated strings: `subprocess.run(['command', 'arg1'])`.",
                        ))

                    # 3. Arbitrary code execution via eval/exec
                    if eval_exec_pattern.search(line):
                        findings.append(Finding.create(
                            assessment_id=assessment_id,
                            source_tool=tool_name,
                            rule_id="B307-EVAL-EXEC",
                            category="security",
                            severity="critical",
                            confidence="high",
                            title="Use of Dangerous eval() or exec()",
                            description="Dynamic execution of code from eval() or exec() can lead to Remote Code Execution (RCE).",
                            file_path=rel_path,
                            line_start=line_idx,
                            line_end=line_idx,
                            evidence={"snippet": line.strip()},
                            remediation="Avoid eval() or exec(). Use safe parsers such as `ast.literal_eval()` or structured JSON serialization.",
                        ))

                    # 4. Unsafe deserialization with pickle
                    if pickle_pattern.search(line):
                        findings.append(Finding.create(
                            assessment_id=assessment_id,
                            source_tool=tool_name,
                            rule_id="B301-PICKLE",
                            category="security",
                            severity="high",
                            confidence="medium",
                            title="Unsafe Deserialization via pickle.loads",
                            description="Deserializing untrusted pickle streams allows arbitrary code execution via __reduce__.",
                            file_path=rel_path,
                            line_start=line_idx,
                            line_end=line_idx,
                            evidence={"snippet": line.strip()},
                            remediation="Use secure serialization formats like JSON, MessagePack, or Protocol Buffers instead of pickle.",
                        ))
            except Exception:
                continue

        run = ToolRun(
            tool_run_id=f"{assessment_id}_sast",
            assessment_id=assessment_id,
            tool_name=tool_name,
            version=version,
            exit_code=0 if len(findings) == 0 else 1,
            duration_ms=dur,
            status="passed" if len(findings) == 0 else "failed",
            message=f"SAST analysis completed across {file_count} Python files. Found {len(findings)} security findings.",
        )
        return run, findings
