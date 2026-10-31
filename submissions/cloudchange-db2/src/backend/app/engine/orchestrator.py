"""Verification Lifecycle Orchestrator.

Coordinates resource identity resolution, AWS evidence collection via registry,
and empirical verification using the Verifier engine.
"""

from typing import Any, Optional
from backend.app.aws.clients import AWSClientFactory
from backend.app.aws.collectors.registry import EvidenceCollectorRegistry
from backend.app.aws.errors import AWSEvidenceError, ResourceNotFoundError
from backend.app.aws.identity import StateIdentityResolver
from backend.app.engine.verifier import Verifier
from backend.app.models.prediction import Prediction, VerificationApproach
from backend.app.models.run import Run, RunStatus
from backend.app.models.verification import VerificationResult, VerificationStatus


class VerificationOrchestrator:
    """Orchestrates end-to-end verification of Run predictions against AWS evidence."""

    def __init__(
        self,
        client_factory: Optional[AWSClientFactory] = None,
        registry: Optional[EvidenceCollectorRegistry] = None,
        verifier: Optional[Verifier] = None,
        identity_resolver: Optional[StateIdentityResolver] = None,
    ) -> None:
        self.client_factory = client_factory or AWSClientFactory()
        self.registry = registry or EvidenceCollectorRegistry(client_factory=self.client_factory)
        self.verifier = verifier or Verifier()
        self.identity_resolver = identity_resolver or StateIdentityResolver()

    def verify_run(
        self,
        run: Run,
        state_artifact: dict[str, Any],
        region: Optional[str] = None,
    ) -> Run:
        """Execute post-deployment verification on a Run given a Terraform state artifact."""
        if not run.predictions:
            run.verification_results = []
            run.status = RunStatus.VERIFIED
            return run

        # Resolve physical resource identities from the Terraform state JSON
        identities = self.identity_resolver.resolve_identities(state_artifact or {})

        # Map canonical changes by address for fallback identity lookup (e.g. for DELETE/REPLACE actions)
        changes_by_address = {c.resource_address: c for c in run.changes}

        verification_results: list[VerificationResult] = []

        for pred in run.predictions:
            res = self._verify_single_prediction(
                pred=pred,
                identities=identities,
                changes_by_address=changes_by_address,
                region=region,
            )
            verification_results.append(res)

        # Aggregate RunStatus deterministically
        if all(r.status == VerificationStatus.VERIFIED for r in verification_results):
            final_status = RunStatus.VERIFIED
        elif any(r.status == VerificationStatus.MISMATCH for r in verification_results):
            final_status = RunStatus.VERIFICATION_FAILED
        else:
            final_status = RunStatus.PARTIALLY_VERIFIED

        run.verification_results = verification_results
        run.status = final_status
        return run

    def _verify_single_prediction(
        self,
        pred: Prediction,
        identities: dict[str, Any],
        changes_by_address: dict[str, Any],
        region: Optional[str] = None,
    ) -> VerificationResult:
        """Resolve identity, fetch evidence, and verify an individual prediction."""
        address = pred.resource_address
        physical_id: Optional[str] = None

        if address and address in identities:
            identity = identities[address]
            physical_id = identity.resource_id
        elif address and address in changes_by_address:
            change = changes_by_address[address]
            # For deletions/replacements, check before state for physical ID
            before_attrs = change.before or {}
            after_attrs = change.after or {}
            physical_id = (
                after_attrs.get("id")
                or after_attrs.get("identifier")
                or before_attrs.get("id")
                or before_attrs.get("identifier")
                or before_attrs.get("dbi_resource_id")
            )

        # If physical resource ID is missing
        if not physical_id:
            if pred.verification_approach in {
                VerificationApproach.IDENTITY_REPLACED,
                VerificationApproach.RESOURCE_DELETED,
            }:
                return VerificationResult(
                    prediction_id=pred.prediction_id,
                    status=VerificationStatus.NOT_OBSERVABLE,
                    expected_value=pred.expected_value,
                    observed_value=None,
                    explanation=(
                        f"Resource identity could not be resolved from state or plan for '{address}'."
                    ),
                )
            return VerificationResult(
                prediction_id=pred.prediction_id,
                status=VerificationStatus.NOT_OBSERVABLE,
                expected_value=pred.expected_value,
                observed_value=None,
                explanation=f"Resource physical ID could not be resolved from Terraform state for '{address}'.",
            )

        # Retrieve evidence from registry
        svc = pred.evidence_requirement.service
        req_rtype = pred.evidence_requirement.resource_type
        field = pred.evidence_requirement.field

        # Determine target region:
        # 1. Explicit verification override (region argument)
        # 2. Resource explicit region (inferred from availability_zone or arn)
        # 3. Fallback to configured default (None lets collector/factory use default)
        target_region = region
        if not target_region and address and address in changes_by_address:
            change = changes_by_address[address]
            az = (change.after or {}).get("availability_zone") or (change.before or {}).get("availability_zone")
            if az and len(az) > 1 and az[-1].isalpha():
                target_region = az[:-1]
            arn = (change.after or {}).get("arn") or (change.before or {}).get("arn")
            if not target_region and arn and isinstance(arn, str) and arn.startswith("arn:aws:"):
                parts = arn.split(":")
                if len(parts) > 3 and parts[3]:
                    target_region = parts[3]

        try:
            collector = self.registry.get_collector_for_service(svc, req_rtype)
            evidence = collector.collect(
                resource_id=physical_id,
                field=field,
                region=target_region,
            )
            return self.verifier.verify_prediction(
                prediction=pred,
                evidence=evidence,
                error=None,
            )
        except ResourceNotFoundError as err:
            return self.verifier.verify_prediction(
                prediction=pred,
                evidence=None,
                error=err,
            )
        except AWSEvidenceError as err:
            return self.verifier.verify_prediction(
                prediction=pred,
                evidence=None,
                error=err,
            )
        except Exception as err:
            return self.verifier.verify_prediction(
                prediction=pred,
                evidence=None,
                error=err,
            )


# Application-scoped default orchestrator instance
_DEFAULT_ORCHESTRATOR = VerificationOrchestrator()


def get_verification_orchestrator() -> VerificationOrchestrator:
    """FastAPI dependency provider returning the VerificationOrchestrator."""
    return _DEFAULT_ORCHESTRATOR
