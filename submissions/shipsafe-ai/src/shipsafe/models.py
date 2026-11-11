"""Data models and shared contracts for ShipSafe AI."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any
import hashlib
import json
import time


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ReleaseGateStatus(str, Enum):
    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    BLOCKED = "BLOCKED"


class ScanProfile(str, Enum):
    QUICK = "quick"
    PRE_PR = "pre-pr"
    DEEP = "deep"


class FindingCategory(str, Enum):
    SECURITY = "security"
    SECRETS = "secrets"
    DEPENDENCIES = "dependencies"
    QUALITY = "quality"
    TESTS = "tests"
    INFRASTRUCTURE = "infrastructure"
    ARCHITECTURE = "architecture"


@dataclass
class Finding:
    """Normalized finding produced by every analyzer and stored in Db2 FINDINGS."""
    finding_id: str
    fingerprint: str
    assessment_id: str
    source_tool: str
    rule_id: str
    category: str
    severity: str
    confidence: str
    title: str
    description: str
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    remediation: Optional[str] = None
    status: str = "new"  # new, existing, resolved, regressed
    references: List[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        assessment_id: str,
        source_tool: str,
        rule_id: str,
        category: str,
        severity: str,
        confidence: str,
        title: str,
        description: str,
        file_path: Optional[str] = None,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        evidence: Optional[Dict[str, Any]] = None,
        remediation: Optional[str] = None,
        references: Optional[List[str]] = None,
    ) -> "Finding":
        # Normalise paths so fingerprints are identical on Windows, Linux and macOS.
        if file_path:
            file_path = file_path.replace("\\", "/")
        # Calculate stable SHA-256 fingerprint from rule_id, file_path, line_start, title
        fp_basis = f"{rule_id}:{file_path or ''}:{line_start or 0}:{title}".strip()
        fingerprint = hashlib.sha256(fp_basis.encode("utf-8")).hexdigest()
        finding_id = f"fnd_{assessment_id}_{fingerprint[:12]}"
        return cls(
            finding_id=finding_id,
            fingerprint=fingerprint,
            assessment_id=assessment_id,
            source_tool=source_tool,
            rule_id=rule_id,
            category=category,
            severity=severity.lower(),
            confidence=confidence.lower(),
            title=title,
            description=description,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            evidence=evidence or {},
            remediation=remediation,
            status="new",
            references=references or [],
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolRun:
    """Provenance record for a deterministic scanner or check execution."""
    tool_run_id: str
    assessment_id: str
    tool_name: str
    version: str
    exit_code: int
    duration_ms: int
    status: str  # passed, failed, skipped, unsupported, not_run
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Assessment:
    """Assessment execution record persisted in IBM Db2."""
    assessment_id: str
    project_id: str
    commit_sha: str
    base_sha: Optional[str]
    profile: str
    status: str  # PASS, PASS_WITH_WARNINGS, BLOCKED
    gate_reason: str
    started_at: int
    finished_at: int
    findings_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class KnowledgeChunk:
    """Retrieved policy / remediation guidance from Db2 vector knowledge store."""
    doc_id: str
    title: str
    content: str
    source: str
    category: str
    version: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    similarity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
