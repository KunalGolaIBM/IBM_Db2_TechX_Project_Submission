"""Assessment orchestration engine for ShipSafe AI."""

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..analyzers import (
    DependencyAnalyzer,
    QualityAnalyzer,
    SafeExecutionBoundary,
    SecretAnalyzer,
    SecurityAnalyzer,
    TestRunnerAnalyzer,
)
from ..analyzers.external import run_bandit, run_pip_audit
from ..config import ShipSafeConfig
from ..discovery import DiscoveryResult, ProjectDiscovery
from ..findings import FindingNormalizer
from ..models import Assessment, Finding, ToolRun
from ..policies import GateEvaluationResult, ReleaseGateEvaluator

log = logging.getLogger("shipsafe.engine")

ProgressFn = Callable[[str, str], None]  # (step_key, message)

# Finding category -> policy category used to scope vector retrieval.
POLICY_CATEGORY = {"quality": "tests"}


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
    warnings: List[str] = field(default_factory=list)

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
            "warnings": self.warnings,
        }


def _skipped(assessment_id: str, name: str, message: str) -> ToolRun:
    return ToolRun(f"{assessment_id}_{name}", assessment_id, name, "-", 0, 0, "skipped", message)


class AssessmentOrchestrator:
    """Coordinates deterministic scanning, normalization, gate evaluation,
    policy retrieval and atomic Db2 persistence."""

    def __init__(self, config: Optional[ShipSafeConfig] = None, repository: Any = None, knowledge_base: Any = None):
        self.config = config or ShipSafeConfig.load()
        self.repository = repository
        self.knowledge_base = knowledge_base

    def run_assessment(
        self,
        workspace_root: str,
        profile: str = "pre-pr",
        base_commit: Optional[str] = None,
        persist_to_db2: bool = True,
        progress: Optional[ProgressFn] = None,
    ) -> AssessmentResult:
        def step(key: str, msg: str) -> None:
            log.info("assessment step %s: %s", key, msg)
            if progress:
                progress(key, msg)

        started_at = int(time.time() * 1000)
        assessment_id = f"asm_{uuid.uuid4().hex[:12]}"
        warnings: List[str] = []

        step("discover", "Inspecting workspace: languages, manifests, tests and git state")
        discovery = ProjectDiscovery(workspace_root).discover()
        boundary = SafeExecutionBoundary(workspace_root)
        tool_runs: List[ToolRun] = []
        raw: List[Finding] = []
        scope = discovery.changed_files if (profile == "quick" and discovery.changed_files) else None

        step("secrets", "Scanning for leaked keys, tokens and credentials")
        tr, fnd = SecretAnalyzer(boundary).scan(assessment_id, target_scope=scope)
        tool_runs.append(tr)
        raw.extend(fnd)

        python = "sast_bandit" in discovery.applicable_checks
        step("sast", "Code rules: SQL injection, shell=True, eval/exec, unsafe deserialization, XSS sinks")
        tr, fnd = SecurityAnalyzer(boundary).scan(assessment_id, target_scope=scope)
        tool_runs.append(tr)
        raw.extend(fnd)
        if python and self.config.use_bandit:
            tr, fnd = run_bandit(boundary, assessment_id)
            tool_runs.append(tr)
            raw.extend(f for f in fnd if not scope or f.file_path in scope)
        elif not python:
            tool_runs.append(_skipped(assessment_id, "bandit", discovery.skipped_checks.get("sast_bandit", "No Python files")))

        step("dependencies", "Checking dependencies against known vulnerabilities")
        dep_analyzer = DependencyAnalyzer(boundary)
        if "dependencies_pip_audit" in discovery.applicable_checks:
            tr, fnd = dep_analyzer.scan(assessment_id)
            tool_runs.append(tr)
            raw.extend(fnd)
            if self.config.pip_audit == "always" or (self.config.pip_audit == "deep" and profile == "deep"):
                tr, fnd = run_pip_audit(boundary, assessment_id)
                tool_runs.append(tr)
                raw.extend(fnd)
        else:
            tool_runs.append(_skipped(assessment_id, "dependencies", discovery.skipped_checks.get("dependencies_pip_audit", "No manifest")))

        if "quality_ruff" in discovery.applicable_checks:
            step("quality", "Checking syntax and exception hygiene")
            tr, fnd = QualityAnalyzer(boundary).scan(assessment_id, target_scope=scope)
            tool_runs.append(tr)
            raw.extend(fnd)

        if "tests_pytest" not in discovery.applicable_checks:
            tool_runs.append(_skipped(assessment_id, "tests", discovery.skipped_checks.get("tests_pytest", "No tests detected")))
        elif profile in ("pre-pr", "deep"):
            step("tests", "Running the project's test suite")
            tr, fnd = TestRunnerAnalyzer(boundary).scan(assessment_id)
            tool_runs.append(tr)
            raw.extend(fnd)
        else:
            tool_runs.append(_skipped(assessment_id, "tests", "Test execution is not part of the 'quick' profile"))

        step("gate", "Normalizing findings and evaluating the release gate")
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

        retrieved: List[Dict[str, Any]] = []
        if self.knowledge_base is not None and findings:
            step("policies", "Retrieving governing policies from the Db2 vector store")
            try:
                seen = set()
                for f in findings:
                    # Search the finding's own policy category first, then fall back to all policies.
                    query = f"{f.title}. {f.description}"
                    category = POLICY_CATEGORY.get(f.category, f.category)
                    hits = self.knowledge_base.retrieve(query, top_k=1, category=category) or \
                        self.knowledge_base.retrieve(query, top_k=1)
                    if hits:
                        cite = f"{hits[0]['doc_id']}: {hits[0]['title']}"
                        f.references = list(dict.fromkeys(f.references + [cite]))
                        f.evidence["policy"] = {k: hits[0][k] for k in ("doc_id", "title", "section", "version", "similarity")}
                        if hits[0]["doc_id"] not in seen:
                            seen.add(hits[0]["doc_id"])
                            retrieved.append(hits[0])
            except Exception as exc:
                warnings.append(f"Policy retrieval unavailable: {exc}")
                log.warning("policy retrieval failed: %s", exc)
        elif self.knowledge_base is None and findings:
            warnings.append("Policy retrieval skipped: the IBM Db2 vector store is not available.")

        persisted = False
        if persist_to_db2 and self.repository is not None:
            step("persist", "Writing the assessment to IBM Db2 in one transaction")
            try:
                self.repository.save_assessment_bundle(
                    project={"project_id": discovery.project_id, "repo_root_hash": discovery.project_id.split("_")[-1],
                             "name": discovery.repo_name, "default_branch": discovery.current_branch or "main"},
                    dependencies=dep_analyzer.inventory,
                    assessment=assessment, tool_runs=tool_runs, findings=findings,
                )
                persisted = True
            except Exception as exc:
                warnings.append(f"Results were not saved to Db2 (transaction rolled back): {exc}")
                log.error("persistence failed, rolled back: %s", exc)
        elif persist_to_db2:
            warnings.append("Results were not saved: IBM Db2 is unavailable.")

        step("done", f"Release gate: {gate.status.value}")
        return AssessmentResult(
            assessment=assessment, discovery=discovery, gate=gate, findings=findings, tool_runs=tool_runs,
            retrieved_policies=retrieved, persisted=persisted, warnings=warnings,
        )
