"""Verification Engine.

Compares expected states declared in Predictions against empirical observations
from AWS Evidence (or AWS observation outcomes/errors) to produce deterministic
VerificationResults.
"""

from typing import Any, Optional
from backend.app.aws.errors import (
    AWSAuthorizationError,
    AWSEvidenceError,
    AWSServiceError,
    ResourceNotFoundError,
)
from backend.app.models.evidence import Evidence
from backend.app.models.prediction import Prediction, VerificationApproach
from backend.app.models.verification import VerificationResult, VerificationStatus


class Verifier:
    """Evaluates prediction satisfaction against observed AWS evidence or errors."""

    def verify_prediction(
        self,
        prediction: Prediction,
        evidence: Optional[Evidence] = None,
        error: Optional[Exception] = None,
    ) -> VerificationResult:
        """Compare a single prediction against available evidence or observation error."""
        pred_id = prediction.prediction_id
        approach = prediction.verification_approach
        expected = prediction.expected_value

        # Handle AWS observation errors
        if error is not None:
            if isinstance(error, ResourceNotFoundError):
                if approach == VerificationApproach.RESOURCE_DELETED:
                    return VerificationResult(
                        prediction_id=pred_id,
                        status=VerificationStatus.VERIFIED,
                        expected_value=expected,
                        observed_value="RESOURCE_NOT_FOUND",
                        explanation=f"Resource '{error.resource_id}' confirmed deleted (NotFound returned by AWS API).",
                        evidence_reference={
                            "resource_id": error.resource_id,
                            "resource_type": error.resource_type,
                        },
                    )
                else:
                    return VerificationResult(
                        prediction_id=pred_id,
                        status=VerificationStatus.MISMATCH,
                        expected_value=expected,
                        observed_value="RESOURCE_NOT_FOUND",
                        explanation=f"Resource '{error.resource_id}' was not found in AWS, but was expected to exist.",
                        evidence_reference={
                            "resource_id": error.resource_id,
                            "resource_type": error.resource_type,
                        },
                    )

            if isinstance(error, (AWSAuthorizationError, AWSServiceError, AWSEvidenceError)):
                error_msg = getattr(error, "message", str(error))
                return VerificationResult(
                    prediction_id=pred_id,
                    status=VerificationStatus.NOT_OBSERVABLE,
                    expected_value=expected,
                    observed_value=None,
                    explanation=f"AWS observation failed: {error_msg}",
                )

            return VerificationResult(
                prediction_id=pred_id,
                status=VerificationStatus.NOT_OBSERVABLE,
                expected_value=expected,
                observed_value=None,
                explanation=f"Observation error: {str(error)}",
            )

        # If error is None and evidence is None
        if evidence is None:
            return VerificationResult(
                prediction_id=pred_id,
                status=VerificationStatus.NOT_OBSERVABLE,
                expected_value=expected,
                observed_value=None,
                explanation="Evidence could not be retrieved from AWS.",
            )

        evidence_ref = {
            "source": evidence.source,
            "resource_id": evidence.resource_id,
        }

        # Dispatch based on declared verification approach
        if approach == VerificationApproach.EXACT_MATCH:
            return self._verify_exact_match(prediction, evidence, evidence_ref)
        elif approach == VerificationApproach.CONFIG_MATCH:
            return self._verify_config_match(prediction, evidence, evidence_ref)
        elif approach == VerificationApproach.SET_CONTAINS:
            return self._verify_set_contains(prediction, evidence, evidence_ref)
        elif approach == VerificationApproach.IDENTITY_REPLACED:
            return self._verify_identity_replaced(prediction, evidence, evidence_ref)
        elif approach == VerificationApproach.RESOURCE_DELETED:
            return self._verify_resource_deleted(prediction, evidence, evidence_ref)
        else:
            return VerificationResult(
                prediction_id=pred_id,
                status=VerificationStatus.NOT_OBSERVABLE,
                expected_value=expected,
                observed_value=evidence.observed_value,
                explanation=f"Unsupported verification approach '{approach}'.",
                evidence_reference=evidence_ref,
            )

    def _verify_exact_match(
        self,
        prediction: Prediction,
        evidence: Evidence,
        evidence_ref: dict[str, Any],
    ) -> VerificationResult:
        expected = prediction.expected_value
        observed = evidence.observed_value

        if observed is None:
            return VerificationResult(
                prediction_id=prediction.prediction_id,
                status=VerificationStatus.NOT_OBSERVABLE,
                expected_value=expected,
                observed_value=None,
                explanation="Observed value is null or missing in evidence.",
                evidence_reference=evidence_ref,
            )

        if observed == expected:
            return VerificationResult(
                prediction_id=prediction.prediction_id,
                status=VerificationStatus.VERIFIED,
                expected_value=expected,
                observed_value=observed,
                explanation=f"Observed value '{observed}' exactly matches expected value.",
                evidence_reference=evidence_ref,
            )
        else:
            return VerificationResult(
                prediction_id=prediction.prediction_id,
                status=VerificationStatus.MISMATCH,
                expected_value=expected,
                observed_value=observed,
                explanation=f"Mismatch: expected '{expected}', but observed '{observed}'.",
                evidence_reference=evidence_ref,
            )

    def _verify_config_match(
        self,
        prediction: Prediction,
        evidence: Evidence,
        evidence_ref: dict[str, Any],
    ) -> VerificationResult:
        expected = prediction.expected_value
        observed = evidence.observed_value

        if not isinstance(expected, dict):
            if observed == expected:
                return VerificationResult(
                    prediction_id=prediction.prediction_id,
                    status=VerificationStatus.VERIFIED,
                    expected_value=expected,
                    observed_value=observed,
                    explanation="Observed configuration matches expected configuration.",
                    evidence_reference=evidence_ref,
                )
            return VerificationResult(
                prediction_id=prediction.prediction_id,
                status=VerificationStatus.MISMATCH,
                expected_value=expected,
                observed_value=observed,
                explanation=f"Configuration mismatch: expected '{expected}', but observed '{observed}'.",
                evidence_reference=evidence_ref,
            )

        if not isinstance(observed, dict):
            return VerificationResult(
                prediction_id=prediction.prediction_id,
                status=VerificationStatus.NOT_OBSERVABLE,
                expected_value=expected,
                observed_value=observed,
                explanation=f"Expected configuration dictionary in evidence, but got {type(observed).__name__}.",
                evidence_reference=evidence_ref,
            )

        # Check that all expected attributes are present and match
        for key, exp_val in expected.items():
            if key not in observed:
                return VerificationResult(
                    prediction_id=prediction.prediction_id,
                    status=VerificationStatus.NOT_OBSERVABLE,
                    expected_value=expected,
                    observed_value=observed,
                    explanation=f"Required configuration attribute '{key}' is missing from observed evidence.",
                    evidence_reference=evidence_ref,
                )
            if observed[key] != exp_val:
                # Handle boolean vs enabled/disabled representation for monitoring
                if key == "monitoring" and (
                    (exp_val is True and observed[key] in {True, "enabled"})
                    or (exp_val is False and observed[key] in {False, "disabled"})
                    or (exp_val == "enabled" and observed[key] is True)
                    or (exp_val == "disabled" and observed[key] is False)
                ):
                    continue

                return VerificationResult(
                    prediction_id=prediction.prediction_id,
                    status=VerificationStatus.MISMATCH,
                    expected_value=expected,
                    observed_value=observed,
                    explanation=f"Configuration attribute '{key}' mismatch: expected '{exp_val}', but observed '{observed[key]}'.",
                    evidence_reference=evidence_ref,
                )

        return VerificationResult(
            prediction_id=prediction.prediction_id,
            status=VerificationStatus.VERIFIED,
            expected_value=expected,
            observed_value=observed,
            explanation=f"All {len(expected)} expected configuration attributes match observed state.",
            evidence_reference=evidence_ref,
        )

    def _verify_set_contains(
        self,
        prediction: Prediction,
        evidence: Evidence,
        evidence_ref: dict[str, Any],
    ) -> VerificationResult:
        expected = prediction.expected_value
        observed = evidence.observed_value

        if not isinstance(observed, list):
            return VerificationResult(
                prediction_id=prediction.prediction_id,
                status=VerificationStatus.NOT_OBSERVABLE,
                expected_value=expected,
                observed_value=observed,
                explanation=f"Expected collection in evidence, but got {type(observed).__name__}.",
                evidence_reference=evidence_ref,
            )

        expected_items = expected if isinstance(expected, list) else [expected]

        for exp_item in expected_items:
            if not self._contains_item(observed, exp_item):
                return VerificationResult(
                    prediction_id=prediction.prediction_id,
                    status=VerificationStatus.MISMATCH,
                    expected_value=expected,
                    observed_value=observed,
                    explanation=f"Expected element '{exp_item}' was not found in observed collection.",
                    evidence_reference=evidence_ref,
                )

        return VerificationResult(
            prediction_id=prediction.prediction_id,
            status=VerificationStatus.VERIFIED,
            expected_value=expected,
            observed_value=observed,
            explanation=f"All {len(expected_items)} expected elements are contained in observed AWS collection.",
            evidence_reference=evidence_ref,
        )

    def _contains_item(self, observed_list: list[Any], expected_item: Any) -> bool:
        """Helper to match items, including port range expansion for sensitive port rules."""
        if expected_item in observed_list:
            return True

        if isinstance(expected_item, dict):
            # Check port range match for sensitive port rule
            if "port" in expected_item:
                target_port = expected_item.get("port")
                target_protocol = expected_item.get("protocol")
                target_cidr = expected_item.get("cidr")

                for obs in observed_list:
                    if isinstance(obs, dict):
                        proto = obs.get("protocol")
                        cidr = obs.get("cidr")
                        from_p = obs.get("from_port")
                        to_p = obs.get("to_port")

                        proto_match = (proto == target_protocol or proto in {"-1", "all"})
                        cidr_match = (cidr == target_cidr)
                        if from_p is None and to_p is None:
                            port_match = True
                        elif from_p is not None and to_p is not None and target_port is not None:
                            port_match = (from_p <= target_port <= to_p)
                        else:
                            port_match = False

                        if proto_match and cidr_match and port_match:
                            return True

            # Check general dict subset match
            for obs in observed_list:
                if isinstance(obs, dict):
                    if all(obs.get(k) == v for k, v in expected_item.items()):
                        return True

        return False

    def _verify_identity_replaced(
        self,
        prediction: Prediction,
        evidence: Evidence,
        evidence_ref: dict[str, Any],
    ) -> VerificationResult:
        expected = prediction.expected_value
        observed = evidence.observed_value

        prior_id: Optional[str] = None
        if isinstance(expected, dict):
            prior_id = expected.get("prior_physical_id")
        elif isinstance(expected, str):
            prior_id = expected

        if prior_id is None or str(prior_id).strip() == "":
            return VerificationResult(
                prediction_id=prediction.prediction_id,
                status=VerificationStatus.NOT_OBSERVABLE,
                expected_value=expected,
                observed_value=observed,
                explanation="Prior physical resource identity is unresolved or missing; cannot confirm replacement.",
                evidence_reference=evidence_ref,
            )

        observed_id: Optional[str] = None
        if isinstance(observed, dict):
            observed_id = observed.get("instance_id") or observed.get("dbi_resource_id") or observed.get("id") or evidence.resource_id
        elif isinstance(observed, str):
            observed_id = observed
        else:
            observed_id = evidence.resource_id

        if observed_id is None or str(observed_id).strip() == "":
            return VerificationResult(
                prediction_id=prediction.prediction_id,
                status=VerificationStatus.NOT_OBSERVABLE,
                expected_value=expected,
                observed_value=observed,
                explanation="Observed physical resource identity is missing in AWS evidence.",
                evidence_reference=evidence_ref,
            )

        if str(observed_id) != str(prior_id):
            return VerificationResult(
                prediction_id=prediction.prediction_id,
                status=VerificationStatus.VERIFIED,
                expected_value=expected,
                observed_value=observed_id,
                explanation=f"Physical resource identity changed from '{prior_id}' to '{observed_id}' (replacement confirmed).",
                evidence_reference=evidence_ref,
            )
        else:
            return VerificationResult(
                prediction_id=prediction.prediction_id,
                status=VerificationStatus.MISMATCH,
                expected_value=expected,
                observed_value=observed_id,
                explanation=f"Physical resource identity '{observed_id}' matches prior identity '{prior_id}' (resource was not replaced).",
                evidence_reference=evidence_ref,
            )

    def _verify_resource_deleted(
        self,
        prediction: Prediction,
        evidence: Evidence,
        evidence_ref: dict[str, Any],
    ) -> VerificationResult:
        return VerificationResult(
            prediction_id=prediction.prediction_id,
            status=VerificationStatus.MISMATCH,
            expected_value=prediction.expected_value,
            observed_value=evidence.observed_value,
            explanation=f"Resource '{evidence.resource_id}' still exists in AWS (observed: {evidence.observed_value}), but was expected to be deleted.",
            evidence_reference=evidence_ref,
        )

    def verify_all(
        self,
        predictions: list[Prediction],
        evidence_map: Optional[dict[str, Evidence]] = None,
        error_map: Optional[dict[str, Exception]] = None,
    ) -> list[VerificationResult]:
        """Verify multiple predictions against corresponding evidence and error mappings."""
        evidence_map = evidence_map or {}
        error_map = error_map or {}
        results: list[VerificationResult] = []

        for pred in predictions:
            pid = pred.prediction_id
            ev = evidence_map.get(pid)
            err = error_map.get(pid)
            results.append(self.verify_prediction(prediction=pred, evidence=ev, error=err))

        return results
