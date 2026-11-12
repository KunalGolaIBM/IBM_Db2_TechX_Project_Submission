"""Deterministic Release-Gate policy evaluator for ShipSafe AI."""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from ..models import Finding, ToolRun, ReleaseGateStatus


@dataclass
class GateEvaluationResult:
    """Outcome of deterministic release gate assessment."""
    status: ReleaseGateStatus
    reason: str
    reasons: List[str] = field(default_factory=list)
    blockers_count: int = 0
    warnings_count: int = 0
    passed_checks_count: int = 0
    failed_checks_count: int = 0
    skipped_checks_count: int = 0


class ReleaseGateEvaluator:
    """
    Evaluates assessment evidence against deterministic enterprise policies.
    Guarantees: An LLM NEVER overrides the deterministic release gate.
    """

    def __init__(
        self,
        block_on_critical: bool = True,
        block_on_high: bool = True,
        block_on_test_failure: bool = True,
    ):
        self.block_on_critical = block_on_critical
        self.block_on_high = block_on_high
        self.block_on_test_failure = block_on_test_failure

    def evaluate(
        self,
        findings: List[Finding],
        tool_runs: List[ToolRun],
        skipped_checks: Dict[str, str] = None,
    ) -> GateEvaluationResult:
        reasons: List[str] = []
        blockers: int = 0
        warnings: int = 0

        # 1. Evaluate Findings
        crit_count = sum(1 for f in findings if f.severity.lower() == "critical")
        high_count = sum(1 for f in findings if f.severity.lower() == "high")
        med_count = sum(1 for f in findings if f.severity.lower() == "medium")
        low_count = sum(1 for f in findings if f.severity.lower() == "low")

        if self.block_on_critical and crit_count > 0:
            reasons.append(f"Blocked by Policy GATE-001: {crit_count} Critical severity finding(s) detected (Secrets/RCE/SQLi).")
            blockers += crit_count

        if self.block_on_high and high_count > 0:
            reasons.append(f"Blocked by Policy GATE-002: {high_count} High severity finding(s) detected.")
            blockers += high_count

        # 2. Evaluate Tool Executions
        passed_tools = 0
        failed_tools = 0
        skipped_tools = 0

        for tr in tool_runs:
            if tr.status == "passed":
                passed_tools += 1
            elif tr.status == "failed":
                failed_tools += 1
                if self.block_on_test_failure and "test" in tr.tool_name.lower():
                    reasons.append(f"Blocked by Policy GATE-003: Required automated test suite failed.")
                    blockers += 1
                else:
                    warnings += 1
            elif tr.status in ("skipped", "unsupported", "not_run"):
                skipped_tools += 1

        # 3. Evaluate Warnings
        if med_count > 0:
            reasons.append(f"Warning GATE-101: {med_count} Medium severity finding(s) identified.")
            warnings += med_count

        if low_count > 0:
            reasons.append(f"Warning GATE-102: {low_count} Low severity finding(s) identified.")
            warnings += low_count

        if skipped_checks:
            for chk, reason in skipped_checks.items():
                skipped_tools += 1
                reasons.append(f"Notice GATE-201: Check '{chk}' was skipped ({reason}).")

        # 4. Compute Final Gate Status
        if blockers > 0:
            status = ReleaseGateStatus.BLOCKED
            primary_reason = f"BLOCKED: {blockers} blocking issue(s) violate production-readiness criteria."
        elif warnings > 0 or skipped_tools > 0:
            status = ReleaseGateStatus.PASS_WITH_WARNINGS
            primary_reason = f"PASS_WITH_WARNINGS: Clean of blockers, but {warnings} warning(s) and {skipped_tools} skipped check(s) exist."
        else:
            status = ReleaseGateStatus.PASS
            primary_reason = "PASS: All required engineering checks completed successfully with 0 blocking conditions."

        return GateEvaluationResult(
            status=status,
            reason=primary_reason,
            reasons=reasons,
            blockers_count=blockers,
            warnings_count=warnings,
            passed_checks_count=passed_tools,
            failed_checks_count=failed_tools,
            skipped_checks_count=skipped_tools,
        )
