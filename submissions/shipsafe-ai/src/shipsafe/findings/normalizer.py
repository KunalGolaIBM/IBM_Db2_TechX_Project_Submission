"""Finding normalization and cross-tool de-duplication."""

import re
from typing import Dict, List, Optional, Tuple

from ..models import Finding

SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}

# Rule families shared by different tools. Two findings in the same file, on the
# same line and in the same family describe one issue and are merged.
_FAMILIES = [
    ("sql-injection", re.compile(r"^(B608|B611|B610|SQLI-)")),
    ("shell-injection", re.compile(r"^(B602|B604|B605|B606|B607|B609|CMD-SHELL)")),
    ("dynamic-code", re.compile(r"^(B307|B102|CODE-EVAL)")),
    ("deserialization", re.compile(r"^(B301|B302|B403|B506|DESER-)")),
    ("tls-verify", re.compile(r"^(B501|TLS-VERIFY)")),
    ("debug-mode", re.compile(r"^(B201|DEBUG-ENABLED)")),
    ("insecure-temp", re.compile(r"^(B306|TEMPFILE-)")),
    ("hardcoded-secret", re.compile(r"^(SEC-\d+|B105|B106|B107)")),
]


def rule_family(rule_id: str) -> Optional[str]:
    for name, pattern in _FAMILIES:
        if pattern.match(rule_id.upper()):
            return name
    return None


class FindingNormalizer:
    """Removes duplicates by fingerprint and merges equivalent findings across tools."""

    @staticmethod
    def _merge(keep: Finding, other: Finding) -> Finding:
        if SEVERITY_RANK.get(other.severity, 0) > SEVERITY_RANK.get(keep.severity, 0):
            keep, other = other, keep
        sources = keep.evidence.setdefault("sources", [keep.source_tool])
        if other.source_tool not in sources:
            sources.append(other.source_tool)
        for ref in other.references:
            if ref not in keep.references:
                keep.references.append(ref)
        if other.rule_id != keep.rule_id:
            keep.evidence.setdefault("related_rules", [])
            if other.rule_id not in keep.evidence["related_rules"]:
                keep.evidence["related_rules"].append(other.rule_id)
        return keep

    @classmethod
    def deduplicate(cls, findings: List[Finding]) -> List[Finding]:
        by_fp: Dict[str, Finding] = {}
        for f in findings:
            by_fp[f.fingerprint] = cls._merge(by_fp[f.fingerprint], f) if f.fingerprint in by_fp else f

        merged: Dict[Tuple, Finding] = {}
        for f in by_fp.values():
            fam = rule_family(f.rule_id)
            if f.category == "dependencies":
                key: Tuple = ("dep", f.file_path, f.evidence.get("package", "").lower(), f.rule_id)
            elif fam and f.file_path and f.line_start:
                key = ("fam", f.file_path, f.line_start, fam)
            else:
                key = ("fp", f.fingerprint)
            merged[key] = cls._merge(merged[key], f) if key in merged else f

        return sorted(merged.values(),
                      key=lambda f: (-SEVERITY_RANK.get(f.severity, 0), f.file_path or "", f.line_start or 0))

    @staticmethod
    def group_by_severity(findings: List[Finding]) -> Dict[str, List[Finding]]:
        groups: Dict[str, List[Finding]] = {k: [] for k in SEVERITY_RANK}
        for f in findings:
            groups.get(f.severity.lower(), groups["info"]).append(f)
        return groups

    @staticmethod
    def group_by_category(findings: List[Finding]) -> Dict[str, List[Finding]]:
        groups: Dict[str, List[Finding]] = {}
        for f in findings:
            groups.setdefault(f.category.lower(), []).append(f)
        return groups
