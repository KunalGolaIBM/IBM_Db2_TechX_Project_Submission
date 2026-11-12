"""Scanner adapters (Bandit, pip-audit), cross-tool de-duplication, SARIF, path safety, pool recovery."""
import tempfile
import unittest
from pathlib import Path

from shipsafe.analyzers.external import parse_bandit, parse_pip_audit
from shipsafe.findings import FindingNormalizer
from shipsafe.models import Finding
from shipsafe.reports.generator import sarif_document
from shipsafe.security import TargetNotAllowed, resolve_target

BANDIT_JSON = {"results": [
    {"test_id": "B602", "test_name": "subprocess_popen_with_shell_equals_true", "issue_severity": "HIGH",
     "issue_confidence": "HIGH", "filename": ".\\src\\api.py", "line_number": 19, "line_range": [19],
     "issue_text": "subprocess call with shell=True identified, security issue.", "code": "subprocess.run(cmd, shell=True)",
     "more_info": "https://bandit.readthedocs.io/b602.html", "issue_cwe": {"id": 78}},
    {"test_id": "B608", "test_name": "hardcoded_sql_expressions", "issue_severity": "MEDIUM", "issue_confidence": "LOW",
     "filename": "./src/api.py", "line_number": 12, "issue_text": "Possible SQL injection vector.", "issue_cwe": {"id": 89}},
]}

PIP_AUDIT_JSON = {"dependencies": [
    {"name": "pyyaml", "version": "5.3.1", "vulns": [
        {"id": "PYSEC-2021-142", "aliases": ["CVE-2020-14343"], "fix_versions": ["5.4"], "description": "RCE"},
        {"id": "PYSEC-2021-142", "aliases": ["CVE-2020-14343"], "fix_versions": ["5.4"], "description": "RCE"}]},
    {"name": "urllib3", "version": "1.26.20", "vulns": [
        {"id": "PYSEC-2026-1999", "aliases": ["CVE-2025-50181"], "fix_versions": ["2.5.0"]}]},
    {"name": "certifi", "version": "2026.10.23", "vulns": []},
]}


class TestAdapters(unittest.TestCase):
    def test_bandit_mapping_normalises_paths_and_escalates_sql(self):
        f = {x.rule_id.split("-")[0]: x for x in parse_bandit(BANDIT_JSON, "asm_t")}
        self.assertEqual(f["B602"].file_path, "src/api.py")
        self.assertEqual(f["B602"].severity, "high")
        self.assertEqual(f["B608"].severity, "critical")  # SQL injection is release-blocking by policy
        self.assertIn("https://cwe.mitre.org/data/definitions/78.html", f["B602"].references)

    def test_pip_audit_dedupes_aliases_and_marks_transitive(self):
        out = parse_pip_audit(PIP_AUDIT_JSON, "asm_t", "requirements.txt", ["pyyaml==5.3.1"])
        by_pkg = {x.evidence["package"]: x for x in out}
        self.assertEqual(len(out), 2)
        self.assertEqual(by_pkg["pyyaml"].rule_id, "CVE-2020-14343")
        self.assertEqual(by_pkg["pyyaml"].severity, "critical")          # from curated advisory
        self.assertFalse(by_pkg["urllib3"].evidence["direct"])
        self.assertEqual(by_pkg["urllib3"].severity, "medium")           # transitive default, stated in evidence
        self.assertIn("no severity", by_pkg["urllib3"].evidence["severity_basis"])

    def test_cross_tool_duplicates_merge_keeping_highest_severity(self):
        builtin = Finding.create("asm_t", "shipsafe_sast", "B608-SQLI", "security", "critical", "high",
                                 "Potential SQL Injection", "d", file_path="src/api.py", line_start=12)
        bandit = parse_bandit(BANDIT_JSON, "asm_t")
        merged = FindingNormalizer.deduplicate([builtin] + bandit)
        sql = [f for f in merged if f.line_start == 12]
        self.assertEqual(len(sql), 1)
        self.assertEqual(sql[0].severity, "critical")
        self.assertEqual(set(sql[0].evidence["sources"]), {"shipsafe_sast", "bandit"})
        self.assertEqual(len(merged), 2)

    def test_dependency_findings_merge_across_curated_and_pip_audit(self):
        curated = Finding.create("asm_t", "shipsafe_dependency_audit", "CVE-2020-14343", "dependencies", "critical", "high",
                                 "Vulnerable Dependency: pyyaml==5.3.1 (CVE-2020-14343)", "d", file_path="requirements.txt",
                                 line_start=1, evidence={"package": "pyyaml"})
        audit = parse_pip_audit(PIP_AUDIT_JSON, "asm_t", "requirements.txt", ["pyyaml==5.3.1"])
        merged = FindingNormalizer.deduplicate([curated] + audit)
        self.assertEqual(sum(1 for f in merged if f.rule_id == "CVE-2020-14343"), 1)


class TestSarif(unittest.TestCase):
    def test_sarif_structure(self):
        f = Finding.create("asm_t", "shipsafe_secrets", "SEC-001", "secrets", "critical", "high", "AWS key", "leak",
                           file_path="src/api.py", line_start=7)
        doc = sarif_document("asm_t", [f.to_dict()])
        run = doc["runs"][0]
        self.assertEqual(doc["version"], "2.1.0")
        self.assertEqual(run["results"][0]["level"], "error")
        self.assertEqual(run["results"][0]["locations"][0]["physicalLocation"]["region"]["startLine"], 7)
        self.assertEqual(run["tool"]["driver"]["rules"][0]["properties"]["security-severity"], "9.5")

    def test_sarif_accepts_db2_rows(self):
        row = {"RULE_ID": "B602", "SEVERITY": "high", "TITLE": "shell", "DESCRIPTION": "", "FINGERPRINT": "a" * 64,
               "CATEGORY": "security", "CONFIDENCE": "high", "FILE_PATH": "x.py", "LINE_START": 3, "REMEDIATION": None}
        self.assertEqual(sarif_document("a", [row])["runs"][0]["results"][0]["ruleId"], "B602")


class TestPathSafety(unittest.TestCase):
    def test_resolve_inside_and_outside(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as other:
            (Path(root) / "svc").mkdir()
            self.assertEqual(resolve_target("svc", [root]), (Path(root) / "svc").resolve())
            for bad in ("..", "svc/../..", other, "", "missing"):
                with self.assertRaises(TargetNotAllowed, msg=bad):
                    resolve_target(bad, [root])


if __name__ == "__main__":
    unittest.main()
