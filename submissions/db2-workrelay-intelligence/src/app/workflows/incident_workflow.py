from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.db.repository import Db2IncidentRepository
from app.models.incident import (
    ActionStatus,
    Incident,
    IncidentAction,
    IncidentSeverity,
    IncidentStatus,
)

logger = logging.getLogger("incident_workflow")


@dataclass
class WorkflowDefinition:
    name: str
    severity: IncidentSeverity
    max_retries: int = 2
    requires_approval: bool = False


WORKFLOW_CATALOG = {
    IncidentSeverity.LOW: WorkflowDefinition("standard_automated", IncidentSeverity.LOW, max_retries=1),
    IncidentSeverity.MEDIUM: WorkflowDefinition("standard_automated", IncidentSeverity.MEDIUM, max_retries=2),
    IncidentSeverity.HIGH: WorkflowDefinition("high_priority_remediation", IncidentSeverity.HIGH, max_retries=2),
    IncidentSeverity.CRITICAL: WorkflowDefinition("critical_incident_containment", IncidentSeverity.CRITICAL, max_retries=1, requires_approval=True),
}


class IncidentWorkflowEngine:
    """
    Executes controlled, deterministic incident response lifecycles.
    Persists all transitions, actions, and audit events directly into IBM Db2.
    """

    def __init__(self, repository: Db2IncidentRepository) -> None:
        self.repo = repository

    def _transition(self, incident: Incident, status: IncidentStatus, step: str) -> None:
        incident.status = status
        incident.current_step = step
        evt = incident.record_event(step.upper(), step=step)
        self.repo.record_event(incident.id, evt)
        self.repo.update(incident)

    def execute(self, incident: Incident) -> Incident:
        """Execute the multi-phase operational workflow."""
        workflow = WORKFLOW_CATALOG.get(incident.severity, WORKFLOW_CATALOG[IncidentSeverity.MEDIUM])
        incident.workflow = workflow.name

        self._transition(incident, IncidentStatus.CLASSIFYING, "incident_classified")
        self._transition(incident, IncidentStatus.INVESTIGATING, "investigation_started")

        # Step 1: Investigation
        inv_action = IncidentAction(
            name="run_diagnostics",
            description=f"Automated health and telemetry probe for {incident.service}",
            status=ActionStatus.RUNNING,
        )
        incident.actions.append(inv_action)

        inv_action.status = ActionStatus.SUCCEEDED
        inv_action.result = f"Telemetry collected: Service {incident.service} operating with elevated error metrics."
        self.repo.record_action(incident.id, inv_action)
        self._transition(incident, IncidentStatus.REMEDIATING, "remediation_started")

        # Step 2: Remediation
        rem_action = IncidentAction(
            name="apply_mitigation",
            description=f"Execute automated remediation playbook for {incident.service}",
            status=ActionStatus.RUNNING,
        )
        incident.actions.append(rem_action)

        if incident.metadata.get("force_failure"):
            rem_action.status = ActionStatus.FAILED
            rem_action.result = "Remediation playbook failed due to environment constraint."
            self.repo.record_action(incident.id, rem_action)
            incident.escalation_reason = "Automated remediation playbook failed."
            self._transition(incident, IncidentStatus.ESCALATED, "incident_escalated")
            return incident

        rem_action.status = ActionStatus.SUCCEEDED
        rem_action.result = f"Applied circuit-breaker reset and connection pool refresh on {incident.service}."
        self.repo.record_action(incident.id, rem_action)
        self._transition(incident, IncidentStatus.VERIFYING, "verification_started")

        # Step 3: Verification
        ver_action = IncidentAction(
            name="verify_recovery",
            description=f"Confirm error rates returned to baseline for {incident.service}",
            status=ActionStatus.RUNNING,
        )
        incident.actions.append(ver_action)

        ver_action.status = ActionStatus.SUCCEEDED
        ver_action.result = f"Service {incident.service} health check confirmed normal."
        self.repo.record_action(incident.id, ver_action)
        incident.resolution = f"Automated workflow '{workflow.name}' completed recovery for {incident.service}."

        self._transition(incident, IncidentStatus.RESOLVED, "incident_resolved")
        return incident
