"""Adapters for industry-standard scanners: Bandit (SAST) and pip-audit (OSV/PyPI advisories).

Each adapter runs the tool through SafeExecutionBoundary (fixed argv, shell=False,
timeout, output cap), parses its JSON and maps every result into the ShipSafe
finding contract. If a tool is not installed it is reported as `skipped`, never
as `passed`.
"""

import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import List, Tuple

from ..models import Finding, ToolRun
from .base import SafeExecutionBoundary, redact_secrets
from .dependencies import KNOWN_VULNERABILITIES

EXCLUDES = ".git,.venv,venv,node_modules,__pycache__,dist,build"


def tool_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _rel(path: str) -> str:
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def _skipped(assessment_id: str, name: str, message: str) -> ToolRun:
    return ToolRun(f"{assessment_id}_{name}", assessment_id, name, "-", 0, 0, "skipped", message)


# ----------------------------------------------------------------------- bandit
BANDIT_SEVERITY = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
# Bandit checks that ShipSafe treats as more severe than Bandit's default rating.
BANDIT_ESCALATE = {"B608": "critical", "B307": "critical", "B102": "critical"}


def parse_bandit(data: dict, assessment_id: str, version: str = "") -> List[Finding]:
    out: List[Finding] = []
    for r in data.get("results", []):
        test_id = r.get("test_id", "B000")
        sev = BANDIT_ESCALATE.get(test_id, BANDIT_SEVERITY.get(r.get("issue_severity", "LOW"), "low"))
        cwe = (r.get("issue_cwe") or {}).get("id")
        refs = [r["more_info"]] if r.get("more_info") else []
        if cwe:
            refs.append(f"https://cwe.mitre.org/data/definitions/{cwe}.html")
        out.append(Finding.create(
            assessment_id=assessment_id,
            source_tool="bandit",
            rule_id=f"{test_id}-{r.get('test_name', 'check')}".upper()[:64],
            category="security",
            severity=sev,
            confidence=str(r.get("issue_confidence", "MEDIUM")).lower(),
            title=redact_secrets(f"Bandit {test_id}: {r.get('issue_text', '').strip()}")[:250],
            description=redact_secrets(r.get("issue_text", "")),
            file_path=_rel(r.get("filename", "")),
            line_start=r.get("line_number"),
            line_end=(r.get("line_range") or [r.get("line_number")])[-1],
            evidence={"snippet": redact_secrets((r.get("code") or "").strip())[:600], "cwe": cwe},
            remediation=f"See {r['more_info']}" if r.get("more_info") else None,
            references=refs,
        ))
    return out


def run_bandit(boundary: SafeExecutionBoundary, assessment_id: str) -> Tuple[ToolRun, List[Finding]]:
    if not tool_available("bandit"):  # pragma: no cover - bandit is a declared dependency
        return _skipped(assessment_id, "bandit", "Bandit not installed (pip install bandit)"), []
    cmd = [sys.executable, "-m", "bandit", "-r", ".", "-f", "json", "-q", "-x", EXCLUDES]
    ret, out, err, dur = boundary.run_command(cmd, timeout=120, redact=False)
    try:
        data = json.loads(out or "{}")
    except json.JSONDecodeError:  # pragma: no cover - only if a bandit release breaks its JSON format
        return ToolRun(f"{assessment_id}_bandit", assessment_id, "bandit", "-", ret, dur, "failed",
                       f"Could not parse Bandit output: {(err or '')[:200]}"), []
    findings = parse_bandit(data, assessment_id)
    status = "passed" if not findings else "failed"
    files = len((data.get("metrics") or {}).keys()) - 1
    return ToolRun(f"{assessment_id}_bandit", assessment_id, "bandit", "pypi", ret, dur, status,
                   f"Bandit scanned {max(files, 0)} file(s); {len(findings)} issue(s)."), findings


# -------------------------------------------------------------------- pip-audit
def parse_pip_audit(data: dict, assessment_id: str, manifest: str, direct: List[str]) -> List[Finding]:
    """Map pip-audit JSON to findings. Severity: curated advisory when known, otherwise
    'high' for direct and 'medium' for transitive packages (pip-audit itself reports no severity)."""
    out: List[Finding] = []
    direct_l = {d.lower().replace("_", "-") for d in direct}
    for dep in data.get("dependencies", []):
        name, version = dep.get("name", ""), dep.get("version", "")
        seen = set()
        for v in dep.get("vulns", []):
            aliases = v.get("aliases") or []
            cve = next((a for a in aliases if a.startswith("CVE-")), v.get("id", "UNKNOWN"))
            if cve in seen:
                continue
            seen.add(cve)
            is_direct = name.lower() in direct_l
            curated = KNOWN_VULNERABILITIES.get(name.lower())
            if curated and curated["cve"] == cve:
                sev, sev_note = curated["severity"], "curated advisory"
            else:
                sev = "high" if is_direct else "medium"
                sev_note = "pip-audit reports no severity; default for " + ("direct" if is_direct else "transitive") + " dependency"
            fixes = v.get("fix_versions") or []
            out.append(Finding.create(
                assessment_id=assessment_id,
                source_tool="pip-audit",
                rule_id=cve[:64],
                category="dependencies",
                severity=sev,
                confidence="high",
                title=f"Vulnerable Dependency: {name}=={version} ({cve})",
                description=(v.get("description") or "").strip()[:1500] or f"{name} {version} is affected by {cve}.",
                file_path=manifest,
                line_start=None if not is_direct else _line_of(manifest, name, data),
                evidence={"package": name, "installed_version": version, "advisory": v.get("id"),
                          "aliases": aliases, "fix_versions": fixes, "direct": is_direct, "severity_basis": sev_note},
                remediation=f"Upgrade {name} to {fixes[0]} or later." if fixes else "No fixed version published yet; assess exposure.",
                references=[f"https://osv.dev/vulnerability/{v.get('id')}"],
            ))
    return out


def _line_of(manifest: str, package: str, data: dict) -> int:
    root = data.get("_root")
    if not root:
        return 1
    try:
        for i, line in enumerate((Path(root) / manifest).read_text(encoding="utf-8").splitlines(), 1):
            if line.strip().lower().replace("_", "-").startswith(package.lower()):
                return i
    except OSError:
        pass
    return 1


def run_pip_audit(boundary: SafeExecutionBoundary, assessment_id: str) -> Tuple[ToolRun, List[Finding]]:
    if not tool_available("pip_audit"):  # pragma: no cover - pip-audit ships with the scanners extra
        return _skipped(assessment_id, "pip-audit", "pip-audit not installed (pip install pip-audit)"), []
    root = boundary.workspace_root
    manifests = [p for p in root.rglob("requirements*.txt")
                 if not any(x in p.parts for x in (".git", ".venv", "venv", "node_modules"))]
    if not manifests:
        return _skipped(assessment_id, "pip-audit", "No requirements*.txt manifest to audit"), []
    findings: List[Finding] = []
    start, last_ret, errors = time.time(), 0, []
    for m in manifests:
        rel = _rel(str(m.relative_to(root)))
        direct = [l.split("==")[0].split(">=")[0].strip() for l in m.read_text(encoding="utf-8").splitlines()
                  if l.strip() and not l.strip().startswith("#")]
        cmd = [sys.executable, "-m", "pip_audit", "-r", rel, "-f", "json", "--progress-spinner", "off"]
        ret, out, err, _ = boundary.run_command(cmd, timeout=240, redact=False)
        last_ret = ret
        try:
            data = json.loads(out or "{}")
        except json.JSONDecodeError:
            errors.append(f"{rel}: {(err or 'no output')[:160]}")
            continue
        data["_root"] = str(root)
        findings.extend(parse_pip_audit(data, assessment_id, rel, direct))
    dur = int((time.time() - start) * 1000)
    if errors and not findings:
        return ToolRun(f"{assessment_id}_pip-audit", assessment_id, "pip-audit", "pypi", last_ret, dur, "failed",
                       "pip-audit could not complete (network or resolver error): " + "; ".join(errors)[:600]), []
    return ToolRun(f"{assessment_id}_pip-audit", assessment_id, "pip-audit", "pypi", last_ret, dur,
                   "passed" if not findings else "failed",
                   f"Audited {len(manifests)} manifest(s) incl. transitive deps against PyPI/OSV; {len(findings)} advisories."), findings
