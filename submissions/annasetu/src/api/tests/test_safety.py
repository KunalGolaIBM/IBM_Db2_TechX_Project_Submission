from datetime import datetime, timedelta, timezone
import unittest

from api.app.services.safety import SafetyEvidence, evaluate_safety, estimate_transit_minutes

NOW = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def evidence(**overrides):
    data = {
        "human_verified": True,
        "verification_recorded": True,
        "allergens_confirmed": True,
        "storage_type": "cold",
        "storage_temp_c": 4.0,
        "use_by": NOW + timedelta(hours=4),
        "transit_minutes": 45,
    }
    data.update(overrides)
    return SafetyEvidence(**data)


class SafetyTests(unittest.TestCase):
    def test_complete_cold_chain_is_logistically_feasible(self):
        result = evaluate_safety(evidence(), NOW)
        self.assertEqual(result.status, "FEASIBLE")
        self.assertEqual(result.remaining_minutes, 240)
        self.assertEqual(result.estimated_transit_minutes, 45)

    def test_missing_human_review_or_temperature_holds_batch(self):
        result = evaluate_safety(evidence(human_verified=False, storage_temp_c=None), NOW)
        self.assertEqual(result.status, "HOLD")
        self.assertTrue(any("human verifier" in reason for reason in result.reasons))
        self.assertTrue(any("temperature" in reason for reason in result.reasons))

    def test_missing_allergen_declaration_holds_batch(self):
        self.assertEqual(evaluate_safety(evidence(allergens_confirmed=False), NOW).status, "HOLD")

    def test_out_of_range_temperature_holds_instead_of_certifying(self):
        result = evaluate_safety(evidence(storage_temp_c=7.0), NOW)
        self.assertEqual(result.status, "HOLD")
        self.assertIn("≤5°C", result.reasons[0])

    def test_passed_use_by_or_impossible_eta_is_infeasible(self):
        expired = evaluate_safety(evidence(use_by=NOW - timedelta(minutes=1)), NOW)
        late = evaluate_safety(evidence(use_by=NOW + timedelta(minutes=30)), NOW)
        self.assertEqual(expired.status, "INFEASIBLE")
        self.assertEqual(late.status, "INFEASIBLE")

    def test_hot_and_frozen_thresholds_are_deterministic(self):
        hot = evaluate_safety(evidence(storage_type="hot", storage_temp_c=60.0), NOW)
        frozen = evaluate_safety(evidence(storage_type="frozen", storage_temp_c=-18.0), NOW)
        self.assertEqual(hot.status, "FEASIBLE")
        self.assertEqual(frozen.status, "FEASIBLE")

    def test_distance_estimate_has_handoff_allowance_and_zero_distance_floor(self):
        self.assertEqual(estimate_transit_minutes(12.97, 77.59, 12.97, 77.59), 15)
        self.assertGreater(estimate_transit_minutes(12.97, 77.59, 13.07, 77.59), 45)
