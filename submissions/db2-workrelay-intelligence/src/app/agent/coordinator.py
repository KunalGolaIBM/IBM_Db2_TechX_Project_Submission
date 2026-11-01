from __future__ import annotations

import logging
from typing import Any

from app.ai.knowledge_retriever import knowledge_retriever
from app.db.repository import Db2IncidentRepository
from app.models.incident import Incident, IncidentSeverity
from app.workflows.incident_workflow import IncidentWorkflowEngine

logger = logging.getLogger("incident_coordinator")


class IncidentCoordinator:
    """
    Coordinates incident ingestion, automatic severity classification,
    LlamaIndex knowledge retrieval, and deterministic workflow execution.
    """

    def __init__(self, repository: Db2IncidentRepository) -> None:
        self.repo = repository
        self.engine = IncidentWorkflowEngine(repository)
        self.retriever = knowledge_retriever

    def classify_severity(self, title: str, description: str) -> IncidentSeverity:
        """Classify incident severity based on problem keywords."""
        combined = f"{title} {description}".lower()
        if any(w in combined for w in ["outage", "p0", "critical", "database down", "security breach", "data loss"]):
            return IncidentSeverity.CRITICAL
        if any(w in combined for w in ["timeout", "deadlock", "failover", "502", "504", "high latency", "degraded"]):
            return IncidentSeverity.HIGH
        if any(w in combined for w in ["slow", "warning", "retry", "spike", "intermittent"]):
            return IncidentSeverity.MEDIUM
        return IncidentSeverity.LOW

    def handle(self, incident: Incident) -> Incident:
        """
        Handle incoming incident:
        1. Classify severity if not set explicitly.
        2. Query LlamaIndex knowledge base for matching operational runbooks.
        3. Persist incident into Db2.
        4. Execute deterministic lifecycle workflow.
        """
        # Auto-classify if default or requested
        if incident.metadata.get("auto_classify", True):
            incident.severity = self.classify_severity(incident.title, incident.description)

        # Knowledge retrieval for relevant runbooks
        ai_match = self.retriever.query(f"{incident.title} {incident.description}", service=incident.service)
        incident.metadata["ai_runbook_context"] = ai_match

        # Save to Db2
        self.repo.create(incident)

        # Run workflow
        return self.engine.execute(incident)
