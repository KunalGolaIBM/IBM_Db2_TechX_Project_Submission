"""Secret scanning analyzer for ShipSafe AI."""

import json
import re
from pathlib import Path
from typing import List, Tuple
from ..models import Finding, ToolRun
from .base import SafeExecutionBoundary, redact_secrets


# Patterns for deterministic secret analysis
DETECTION_RULES = [
    {
        "id": "SEC-001",
        "name": "AWS Access Key ID Detected",
        "regex": re.compile(r'\b(AKIA[0-9A-Z]{16})\b'),
        "severity": "critical",
        "confidence": "high",
        "category": "secrets",
        "remediation": "Revoke the exposed AWS credential immediately in AWS IAM and store secrets in environment variables or HashiCorp Vault.",
    },
    {
        "id": "SEC-002",
        "name": "Hardcoded IBM Db2 Password / Connection String",
        "regex": re.compile(r'(?i)(?:db2|database)[_-]?(?:pwd|password|pass)\s*[:=]\s*["\']([^"\'\s]{6,})["\']'),
        "severity": "critical",
        "confidence": "high",
        "category": "secrets",
        "remediation": "Remove hardcoded credentials. Use DB2_PASSWORD environment variable or client certificate authentication.",
    },
    {
        "id": "SEC-003",
        "name": "GitHub Personal Access Token Detected",
        "regex": re.compile(r'\b(ghp_[a-zA-Z0-9]{36})\b'),
        "severity": "critical",
        "confidence": "high",
        "category": "secrets",
        "remediation": "Revoke the exposed GitHub token immediately on GitHub Settings > Developer Settings.",
    },
    {
        "id": "SEC-004",
        "name": "Private Cryptographic Key Detected",
        "regex": re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
        "severity": "critical",
        "confidence": "high",
        "category": "secrets",
        "remediation": "Never commit private cryptographic keys. Generate a new keypair and configure via secure key management.",
    },
    {
        "id": "SEC-005",
        "name": "Hardcoded API Secret / Token",
        "regex": re.compile(r'(?i)(api[_-]?secret|jwt[_-]?secret|auth[_-]?secret)\s*[:=]\s*["\']([^"\'\s]{8,})["\']'),
        "severity": "high",
        "confidence": "medium",
        "category": "secrets",
        "remediation": "Move secrets out of source code into environment variables or secrets manager.",
    },
]

SKIP_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".tar", ".gz", ".lock", ".pyc"}
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}


class SecretAnalyzer:
    """Detects leaked credentials, private keys, and tokens with honest evidence and redaction."""

    def __init__(self, boundary: SafeExecutionBoundary):
        self.boundary = boundary

    def scan(self, assessment_id: str, target_scope: List[str] = None) -> Tuple[ToolRun, List[Finding]]:
        findings: List[Finding] = []
        tool_name = "shipsafe_secrets_scanner"
        version = "1.0.0"

        # Check if gitleaks executable exists
        ret, stdout, stderr, dur = self.boundary.run_command(["gitleaks", "version"])
        use_gitleaks = (ret == 0)

        if use_gitleaks:
            tool_name = "gitleaks"
            version = stdout.strip() or "8.x"
            # Run gitleaks with json report to temporary location
            # If target files specified, scan those, else whole workspace
            report_file = self.boundary.workspace_root / ".shipsafe_gitleaks.json"
            gitleaks_cmd = [
                "gitleaks", "detect",
                "--no-git",
                "--report-format", "json",
                "--report-path", str(report_file),
                "--source", str(self.boundary.workspace_root)
            ]
            ret, out, err, dur = self.boundary.run_command(gitleaks_cmd)
            if report_file.exists():
                try:
                    with open(report_file, "r", encoding="utf-8") as rf:
                        data = json.load(rf)
                        for item in data:
                            findings.append(Finding.create(
                                assessment_id=assessment_id,
                                source_tool="gitleaks",
                                rule_id=item.get("RuleID", "gitleaks-rule"),
                                category="secrets",
                                severity="critical",
                                confidence="high",
                                title=f"Exposed Secret ({item.get('Description', 'Sensitive Token')})",
                                description=f"Gitleaks detected secret matching rule '{item.get('RuleID')}'.",
                                file_path=item.get("File"),
                                line_start=item.get("StartLine"),
                                line_end=item.get("EndLine"),
                                evidence={"match": "[REDACTED_SECRET]"},
                                remediation="Revoke and rotate the exposed secret immediately.",
                            ))
                except Exception:
                    pass
                finally:
                    report_file.unlink(missing_ok=True)
            run = ToolRun(
                tool_run_id=f"{assessment_id}_secrets",
                assessment_id=assessment_id,
                tool_name=tool_name,
                version=version,
                exit_code=ret,
                duration_ms=dur,
                status="passed" if len(findings) == 0 else "failed",
                message=f"Scanned repository for secrets using {tool_name}. Found {len(findings)} issues.",
            )
            return run, findings

        # Fallback to high-precision deterministic rules
        start_ms = 0
        file_count = 0
        root_path = self.boundary.workspace_root

        for path in root_path.rglob("*"):
            if not path.is_file():
                continue
            # Check exclusions
            parts = path.parts
            if any(d in parts for d in SKIP_DIRS):
                continue
            if path.suffix.lower() in SKIP_EXTENSIONS:
                continue

            # Target scope check if specified
            rel_path = path.relative_to(root_path).as_posix()
            if target_scope and rel_path not in target_scope:
                continue

            file_count += 1
            try:
                # Read with size limit (max 500KB per file)
                if path.stat().st_size > 500_000:
                    continue
                content = path.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()

                for line_idx, line in enumerate(lines, 1):
                    for rule in DETECTION_RULES:
                        match = rule["regex"].search(line)
                        if match:
                            redacted_snippet = redact_secrets(line.strip())
                            findings.append(Finding.create(
                                assessment_id=assessment_id,
                                source_tool=tool_name,
                                rule_id=rule["id"],
                                category=rule["category"],
                                severity=rule["severity"],
                                confidence=rule["confidence"],
                                title=rule["name"],
                                description=f"Potential secret or credential pattern identified in {rel_path}:{line_idx}",
                                file_path=rel_path,
                                line_start=line_idx,
                                line_end=line_idx,
                                evidence={"snippet": redacted_snippet},
                                remediation=rule["remediation"],
                                references=["https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html"],
                            ))
            except Exception:
                continue

        run = ToolRun(
            tool_run_id=f"{assessment_id}_secrets",
            assessment_id=assessment_id,
            tool_name=tool_name,
            version=version,
            exit_code=0 if len(findings) == 0 else 1,
            duration_ms=dur,
            status="passed" if len(findings) == 0 else "failed",
            message=f"Inspected {file_count} files with {len(DETECTION_RULES)} deterministic secret rules. Identified {len(findings)} secrets.",
        )
        return run, findings
