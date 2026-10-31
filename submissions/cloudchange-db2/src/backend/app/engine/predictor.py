"""Impact and Prediction Engine.

Evaluates CanonicalChanges against deterministic rules to produce
ImpactFindings and observable Predictions with EvidenceRequirements.
"""

from typing import Optional

from backend.app.engine.rules import ALL_RULES, BaseRule
from backend.app.models.change import CanonicalChange
from backend.app.models.impact import ImpactFinding
from backend.app.models.prediction import Prediction


class ImpactPredictor:
    """Orchestrates deterministic rule execution over a set of CanonicalChanges."""

    def __init__(self, rules: Optional[list[BaseRule]] = None) -> None:
        self.rules: list[BaseRule] = list(rules) if rules is not None else list(ALL_RULES)

    def evaluate(self, changes: list[CanonicalChange]) -> tuple[list[ImpactFinding], list[Prediction]]:
        """Run all registered rules against canonical changes.
        
        Returns:
            Tuple of (findings, predictions) where each prediction has an
            attached EvidenceRequirement.
        """
        findings: list[ImpactFinding] = []
        predictions: list[Prediction] = []

        for change in changes:
            for rule in self.rules:
                if rule.applies_to(change.resource_type) and rule.trigger(change):
                    finding, prediction = rule.evaluate(change)
                    findings.append(finding)
                    predictions.append(prediction)

        return findings, predictions
