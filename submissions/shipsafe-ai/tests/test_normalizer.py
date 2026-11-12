import unittest
from shipsafe.models import Finding
from shipsafe.findings import FindingNormalizer


class TestFindingNormalizer(unittest.TestCase):
    def test_stable_fingerprint_generation(self):
        f1 = Finding.create(
            assessment_id="asm_test",
            source_tool="bandit",
            rule_id="B608-SQLI",
            category="security",
            severity="critical",
            confidence="high",
            title="SQL Injection",
            description="Dynamic formatting",
            file_path="src/api.py",
            line_start=12,
        )
        f2 = Finding.create(
            assessment_id="asm_test2",
            source_tool="bandit",
            rule_id="B608-SQLI",
            category="security",
            severity="critical",
            confidence="high",
            title="SQL Injection",
            description="Dynamic formatting",
            file_path="src/api.py",
            line_start=12,
        )
        # Fingerprint must be stable across different assessment runs
        self.assertEqual(f1.fingerprint, f2.fingerprint)
        self.assertTrue(len(f1.fingerprint) == 64)

    def test_deduplication(self):
        f1 = Finding.create(
            assessment_id="asm_1",
            source_tool="bandit",
            rule_id="B608",
            category="security",
            severity="critical",
            confidence="high",
            title="SQL Injection",
            description="desc",
            file_path="src/api.py",
            line_start=10,
        )
        f2 = Finding.create(
            assessment_id="asm_1",
            source_tool="semgrep",
            rule_id="B608",
            category="security",
            severity="critical",
            confidence="high",
            title="SQL Injection",
            description="desc",
            file_path="src/api.py",
            line_start=10,
        )
        deduped = FindingNormalizer.deduplicate([f1, f2])
        self.assertEqual(len(deduped), 1)


if __name__ == "__main__":
    unittest.main()
