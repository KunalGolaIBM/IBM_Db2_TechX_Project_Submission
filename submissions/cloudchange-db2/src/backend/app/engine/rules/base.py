"""Base Rule Contract for CloudChange Deterministic Impact Rules."""

from abc import ABC, abstractmethod

from backend.app.models.change import CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.impact import ImpactCategory, ImpactFinding, Severity
from backend.app.models.prediction import Prediction


class BaseRule(ABC):
    """Abstract base contract for all CloudChange deterministic impact rules."""

    rule_id: str
    rule_version: str = "1.0.0"
    name: str
    resource_types: set[str]
    category: ImpactCategory
    severity: Severity

    def applies_to(self, resource_type: str) -> bool:
        """Check whether this rule applies to the given Terraform resource type."""
        return resource_type in self.resource_types

    @abstractmethod
    def trigger(self, change: CanonicalChange) -> bool:
        """Pure deterministic trigger condition."""
        ...

    @abstractmethod
    def generate_finding(self, change: CanonicalChange) -> ImpactFinding:
        """Construct an auditable ImpactFinding explaining why this change matters."""
        ...

    @abstractmethod
    def generate_evidence_requirement(self, change: CanonicalChange) -> EvidenceRequirement:
        """Construct the exact EvidenceRequirement specifying what AWS API field to observe."""
        ...

    @abstractmethod
    def generate_prediction(self, change: CanonicalChange) -> Prediction:
        """Construct a machine-readable Prediction of post-deployment AWS state with EvidenceRequirement attached."""
        ...

    def evaluate(self, change: CanonicalChange) -> tuple[ImpactFinding, Prediction]:
        """Execute evaluation, returning non-null ImpactFinding and evidenced Prediction."""
        finding = self.generate_finding(change)
        prediction = self.generate_prediction(change)
        return finding, prediction
