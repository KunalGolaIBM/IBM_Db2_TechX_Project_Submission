"""Test execution adapter for ShipSafe AI."""

import re
import sys
from pathlib import Path
from typing import List, Tuple
from ..models import Finding, ToolRun
from .base import SafeExecutionBoundary


class TestRunnerAnalyzer:
    """Discovers and executes tests safely, collecting pass/fail/error telemetry."""

    def __init__(self, boundary: SafeExecutionBoundary):
        self.boundary = boundary

    def scan(self, assessment_id: str, test_dir: str = "tests") -> Tuple[ToolRun, List[Finding]]:
        findings: List[Finding] = []
        tool_name = "shipsafe_test_runner"
        version = "1.0.0"

        # Check if tests directory exists
        test_path = self.boundary.workspace_root / test_dir
        if not test_path.exists() or not test_path.is_dir():
            run = ToolRun(
                tool_run_id=f"{assessment_id}_tests",
                assessment_id=assessment_id,
                tool_name=tool_name,
                version=version,
                exit_code=0,
                duration_ms=0,
                status="skipped",
                message=f"No '{test_dir}' directory found. Test execution skipped.",
            )
            return run, findings

        # Run python unittest discovery
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", test_dir, "-t", ".", "-p", "test_*.py"]
        ret, stdout, stderr, dur = self.boundary.run_command(cmd, timeout=30)

        # Parse test results
        combined_output = f"{stdout}\n{stderr}"
        failed_count = 0
        error_count = 0

        # Look for FAILED (failures=X, errors=Y)
        match_fail = re.search(r'FAILED\s*\((?:failures=(\d+))?(?:,\s*)?(?:errors=(\d+))?\)', combined_output)
        if match_fail:
            f_str = match_fail.group(1) or "0"
            e_str = match_fail.group(2) or "0"
            failed_count = int(f_str)
            error_count = int(e_str)

        total_failed = failed_count + error_count

        if ret != 0 or total_failed > 0:
            if total_failed > 0:
                title = f"Test Suite Regression: {total_failed} Failed Test(s)"
                desc = f"Automated test run reported {failed_count} failure(s) and {error_count} error(s)."
            else:
                title = "Test Suite Could Not Run"
                desc = f"The test runner exited with code {ret} before reporting results (import or discovery error)."
            findings.append(Finding.create(
                assessment_id=assessment_id,
                source_tool=tool_name,
                rule_id="TEST-SUITE-FAILURE",
                category="tests",
                severity="critical",
                confidence="high",
                title=title,
                description=desc,
                file_path=test_dir,
                line_start=1,
                line_end=1,
                evidence={"output_excerpt": combined_output[-500:]},
                remediation="Investigate test assertion failures and ensure all regression tests pass before approving Pull Request.",
            ))

        run = ToolRun(
            tool_run_id=f"{assessment_id}_tests",
            assessment_id=assessment_id,
            tool_name=tool_name,
            version=version,
            exit_code=ret,
            duration_ms=dur,
            status="passed" if ret == 0 and total_failed == 0 else "failed",
            message=f"Test run completed in {dur}ms. Result: {'PASS' if ret == 0 else 'FAIL'} (Failures: {failed_count}, Errors: {error_count})",
        )
        return run, findings
