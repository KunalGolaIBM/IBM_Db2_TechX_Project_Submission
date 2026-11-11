"""Assessment orchestration engine for ShipSafe AI."""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..analyzers import (
    DependencyAnalyzer,
    QualityAnalyzer,
    SafeExecutionBoundary,
    SecretAnalyzer,
    SecurityAnalyzer,
    TestRunnerAnalyzer,
)
from ..config import ShipSafeConfig
from ..db2 import Db2Repository
from ..discovery import DiscoveryResult, ProjectDiscovery
from ..findings import FindingNormalizer
from ..models import Assessment, Finding, ToolRun
from ..policies import GateEvaluationResult, ReleaseGateEvaluator


@dataclass
class AssessmentResult:
    """Complete bundle returned after an assessment."""
    assessment: Assessment
    discovery: DiscoveryResult
    gate: GateEvaluationResult
    findings: List[Finding]
    tool_runs: List[ToolRun]
    retrieved_policies: List[Dict[str, Any]] = field(default_factory=list)
    persisted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment": self.assessment.to_dict(),
            "discovery": self.discovery.to_dict(),
            "gate": {
                "status": self.gate.status.value,
                "reason": self.gate.reason,
                "reasons": self.gate.reasons,
                "blockers_count": self.gate.blockers_count,
                "warnings_count": self.gate.warnings_count,
                "passed_checks": self.gate.passed_checks_count,
                "failed_checks": self.gate.failed_checks_count,
                "skipped_checks": self.gate.skipped_checks_count,
            },
            "findings": [f.to_dict() for f in self.findings],
            "tool_runs": [tr.to_dict() for tr in self.tool_runs],
            "retrieved_policies": self.retrieved_policies,
            "persisted_to_db2": self.persisted,
        }


def _skipped(assessment_id: str, name: str, message: str) -> ToolRun:
    return ToolRun(
        tool_run_id=f"{assessment_id}_{name}",
        assessment_id=assessment_id,
        tool_name=name,
        version="-",
        exit_code=0,
        duration_ms=0,
        status="skipped",
        message=message,
    )


class AssessmentOrchestrator:
    """Coordinates deterministic scanning, normalization, gate evaluation,
    Db2 persistence and policy retrieval."""

    def __init__(
        self,
        config: Optional[ShipSafeConfig] = None,
        repository: Optional[Db2Repository] = None,
        knowledge_base: Any = None,
    ):
        self.config = config or ShipSafeConfig.load()
        self.repository = repository
        self.knowledge_base = knowledge_base

    def run_assessment(
        self,
        workspace_root: str,
        profile: str = "pre-pr",
        base_commit: Optional[str] = None,
        persist_to_db2: bool = True,
    ) -> AssessmentResult:
        started_at = int(time.time() * 1000)
        assessment_id = f"asm_{uuid.uuid4().hex[:12]}"

        discovery = ProjectDiscovery(workspace_root).discover()
        boundary = SafeExecutionBoundary(workspace_root)
        tool_runs: List[ToolRun] = []
        raw: List[Finding] = []

        scope = discovery.changed_files if (profile == "quick" and discovery.changed_files) else None

        # Secrets: always run.
        tr, fnd = SecretAnalyzer(boundary).scan(assessment_id, target_scope=scope)
        tool_runs.append(tr)
        raw.extend(fnd)

        if "sast_bandit" in discovery.applicable_checks:
            tr, fnd = SecurityAnalyzer(boundary).scan(assessment_id, target_scope=scope)
            tool_runs.append(tr)
            raw.extend(fnd)
        else:
            tool_runs.append(_skipped(assessment_id, "sast", discovery.skipped_checks.get("sast_bandit", "Not applicable")))

        dep_analyzer = DependencyAnalyzer(boundary)
        if "dependencies_pip_audit" in discovery.applicable_checks:
            tr, fnd = dep_analyzer.scan(assessment_id)
            tool_runs.append(tr)
            raw.extend(fnd)
        else:
            tool_runs.append(_skipped(assessment_id, "dependencies", discovery.skipped_checks.get("dependencies_pip_audit", "No manifest")))

        if "quality_ruff" in discovery.applicable_checks:
            tr, fnd = QualityAnalyzer(boundary).scan(assessment_id, target_scope=scope)
            tool_runs.append(tr)
            raw.extend(fnd)

        if "tests_pytest" not in discovery.applicable_checks:
            tool_runs.append(_skipped(assessment_id, "tests", discovery.skipped_checks.get("tests_pytest", "No tests detected")))
        elif profile in ("pre-pr", "deep"):
            tr, fnd = TestRunnerAnalyzer(boundary).scan(assessment_id)
            tool_runs.append(tr)
            raw.extend(fnd)
        else:
            tool_runs.append(_skipped(assessment_id, "tests", "Test execution is not part of the 'quick' profile"))

        findings = FindingNormalizer.deduplicate(raw)
        gate = ReleaseGateEvaluator().evaluate(findings=findings, tool_runs=tool_runs, skipped_checks=discovery.skipped_checks)

        counts = {s: sum(1 for f in findings if f.severity == s) for s in ("critical", "high", "medium", "low")}
        assessment = Assessment(
            assessment_id=assessment_id,
            project_id=discovery.project_id,
            commit_sha=discovery.head_commit or "uncommitted",
            base_sha=base_commit or discovery.base_commit,
            profile=profile,
            status=gate.status.value,
            gate_reason=gate.reason,
            started_at=started_at,
            finished_at=int(time.time() * 1000),
            findings_count=len(findings),
            critical_count=counts["critical"],
            high_count=counts["high"],
            medium_count=counts["medium"],
            low_count=counts["low"],
        )

        # Retrieve the governing policy for each finding from the Db2 vector store.
        retrieved: List[Dict[str, Any]] = []
        if self.knowledge_base is not None and findings:
            seen = set()
            for f in findings:
                hits = self.knowledge_base.retrieve(f"{f.title}. {f.description}", top_k=1)
                if hits:
                    f.references = list(dict.fromkeys(f.references + [f"{hits[0]['doc_id']}: {hits[0]['title']}"]))
                    if hits[0]["doc_id"] not in seen:
                        seen.add(hits[0]["doc_id"])
                        retrieved.append(hits[0])

        persisted = False
        if persist_to_db2 and self.repository is not None:
            self.repository.save_project(
                project_id=discovery.project_id,
                repo_root_hash=discovery.project_id.split("_")[-1],
                name=discovery.repo_name,
                default_branch=discovery.current_branch or "main",
            )
            self.repository.save_dependencies(discovery.project_id, dep_analyzer.inventory)
            self.repository.save_assessment(assessment)
            self.repository.save_tool_runs(tool_runs)
            self.repository.save_findings(findings)
            persisted = True

        return AssessmentResult(
            assessment=assessment,
            discovery=discovery,
            gate=gate,
            findings=findings,
            tool_runs=tool_runs,
            retrieved_policies=retrieved,
            persisted=persisted,
        )
