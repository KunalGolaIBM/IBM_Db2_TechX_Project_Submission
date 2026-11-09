"""
Unit tests for Deterministic Risk Engine & Signal Weights
"""

import unittest
from workflows.review import SIGNAL_WEIGHTS, RiskSignal


class TestRiskEngine(unittest.TestCase):

    def test_signal_weights_configured(self):
        self.assertGreaterEqual(SIGNAL_WEIGHTS["HISTORICAL_REVERT"], 30.0)
        self.assertGreaterEqual(SIGNAL_WEIGHTS["PREVIOUS_REGRESSION"], 25.0)
        self.assertGreaterEqual(SIGNAL_WEIGHTS["SECURITY_SENSITIVE"], 20.0)
        self.assertGreaterEqual(SIGNAL_WEIGHTS["VERIFIED_BUG_FIX_FILE"], 15.0)

    def test_deterministic_score_calculation(self):
        signals = [
            RiskSignal(
                signal_id="HISTORICAL_REVERT",
                name="Historical Revert",
                description="Reverted in commit abc",
                weight=SIGNAL_WEIGHTS["HISTORICAL_REVERT"],
            ),
            RiskSignal(
                signal_id="SECURITY_SENSITIVE",
                name="Security Sensitive",
                description="Token handling modified",
                weight=SIGNAL_WEIGHTS["SECURITY_SENSITIVE"],
            ),
        ]
        raw_score = sum(s.weight for s in signals)
        self.assertEqual(raw_score, 60.0)

        # Assessment threshold mapping
        if raw_score >= 60:
            assessment = "CRITICAL HISTORICAL RISK"
        elif raw_score >= 40:
            assessment = "HIGH HISTORICAL RISK"
        else:
            assessment = "LOW HISTORICAL RISK"

        self.assertEqual(assessment, "CRITICAL HISTORICAL RISK")


if __name__ == "__main__":
    unittest.main()

