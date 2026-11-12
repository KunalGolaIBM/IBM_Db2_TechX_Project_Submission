import unittest
from shipsafe.models import Finding, ToolRun, ReleaseGateStatus
from shipsafe.policies import ReleaseGateEvaluator


class TestReleaseGate(unittest.TestCase):
    def setUp(self):
        self.evaluator = ReleaseGateEvaluator()

    def test_gate_blocked_on_critical_finding(self):
        findings = [
            Finding.create(
                assessment_id="asm_test",
                source_tool="secrets",
                rule_id="SEC-001",
                category="secrets",
                severity="critical",
                confidence="high",
                title="AWS Key Leak",
                description="Leaked token",
            )
        ]
        tool_runs = [
            ToolRun("r1", "asm_test", "secrets", "1.0", 0, 50, "passed")
        ]
        result = self.evaluator.evaluate(findings, tool_runs)
        self.assertEqual(result.status, ReleaseGateStatus.BLOCKED)
        self.assertTrue(result.blockers_count > 0)

    def test_gate_pass_with_warnings_on_medium_finding(self):
        findings = [
            Finding.create(
                assessment_id="asm_test",
                source_tool="quality",
                rule_id="E722",
                category="quality",
                severity="medium",
                confidence="high",
                title="Bare except",
                description="desc",
            )
        ]
        tool_runs = [
            ToolRun("r1", "asm_test", "quality", "1.0", 0, 50, "passed")
        ]
        result = self.evaluator.evaluate(findings, tool_runs)
        self.assertEqual(result.status, ReleaseGateStatus.PASS_WITH_WARNINGS)

    def test_gate_pass_clean(self):
        findings = []
        tool_runs = [
            ToolRun("r1", "asm_test", "secrets", "1.0", 0, 50, "passed"),
            ToolRun("r2", "asm_test", "tests", "1.0", 0, 100, "passed"),
        ]
        result = self.evaluator.evaluate(findings, tool_runs)
        self.assertEqual(result.status, ReleaseGateStatus.PASS)


if __name__ == "__main__":
    unittest.main()
