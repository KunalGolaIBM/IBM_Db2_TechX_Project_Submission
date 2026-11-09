"""
Unit tests for Evidence and Finding Data Models
"""

import unittest
from data.evidence_models import AgentFinding, EvidenceReference, VerificationStatus


class TestEvidenceModels(unittest.TestCase):

    def test_evidence_reference_creation(self):
        ev = EvidenceReference(
            artifact_type="commit",
            commit_sha="abc1234",
            file_path="src/auth.py",
            start_line=10,
            end_line=25,
            verification_status=VerificationStatus.VERIFIED,
            verification_note="Verified commit in Db2",
        )
        self.assertEqual(ev.commit_sha, "abc1234")
        self.assertEqual(ev.verification_status, VerificationStatus.VERIFIED)
        self.assertEqual(ev.file_path, "src/auth.py")

    def test_agent_finding_creation(self):
        ev = EvidenceReference(
            artifact_type="file",
            file_path="src/token.py",
            verification_status=VerificationStatus.VERIFIED,
        )
        finding = AgentFinding(
            agent_name="CodeAgent",
            finding_type="REGRESSION_RISK",
            title="Token Expiration Vulnerability",
            summary="Found risk in refresh token handling without expiration check.",
            severity="HIGH",
            evidence=[ev],
            recommendations=["Add expiry check", "Add regression test"],
        )
        self.assertEqual(finding.severity, "HIGH")
        self.assertEqual(len(finding.evidence), 1)
        self.assertEqual(len(finding.recommendations), 2)


if __name__ == "__main__":
    unittest.main()

