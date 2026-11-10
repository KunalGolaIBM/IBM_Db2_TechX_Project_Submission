"""
MediTwin AI — Audit Service
Records all important actions for traceability.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class AuditService:
    """Manages audit logging for all MediTwin operations."""

    def __init__(self, repository):
        self.repo = repository

    def log_upload(self, document_id: int, file_name: str,
                   patient_id: int, actor: str = "SYSTEM"):
        """Log a document upload event."""
        self.repo.log_audit(
            action="DOCUMENT_UPLOAD",
            entity_type="DOCUMENT",
            entity_id=document_id,
            actor_id=actor,
            details={
                "file_name": file_name,
                "patient_id": patient_id,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_extraction(self, document_id: int, observation_count: int,
                       actor: str = "SYSTEM"):
        """Log an extraction event."""
        self.repo.log_audit(
            action="EXTRACTION_COMPLETE",
            entity_type="DOCUMENT",
            entity_id=document_id,
            actor_id=actor,
            details={
                "observations_extracted": observation_count,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_approval(self, observation_id: int, reviewer: str,
                     original_value: float = None, corrected_value: float = None):
        """Log an observation approval."""
        details = {
            "reviewer": reviewer,
            "timestamp": datetime.now().isoformat(),
        }
        if corrected_value is not None and original_value != corrected_value:
            details["original_value"] = original_value
            details["corrected_value"] = corrected_value

        self.repo.log_audit(
            action="OBSERVATION_APPROVED",
            entity_type="OBSERVATION",
            entity_id=observation_id,
            actor_id=reviewer,
            details=details,
        )

    def log_rejection(self, observation_id: int, reviewer: str,
                      reason: str = None):
        """Log an observation rejection."""
        self.repo.log_audit(
            action="OBSERVATION_REJECTED",
            entity_type="OBSERVATION",
            entity_id=observation_id,
            actor_id=reviewer,
            details={
                "reason": reason or "Rejected by reviewer",
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_question(self, patient_id: int, question: str,
                     had_evidence: bool, actor: str = "USER"):
        """Log a Q&A interaction."""
        self.repo.log_audit(
            action="QUESTION_ASKED",
            entity_type="PATIENT",
            entity_id=patient_id,
            actor_id=actor,
            details={
                "question": question,
                "had_evidence": had_evidence,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_edit(self, observation_id: int, field: str,
                 old_value: str, new_value: str, editor: str = "REVIEWER"):
        """Log a value edit during review."""
        self.repo.log_audit(
            action="OBSERVATION_EDITED",
            entity_type="OBSERVATION",
            entity_id=observation_id,
            actor_id=editor,
            details={
                "field": field,
                "old_value": str(old_value),
                "new_value": str(new_value),
                "timestamp": datetime.now().isoformat(),
            },
        )

    def get_recent_activity(self, limit: int = 20) -> List[Dict]:
        """Get recent audit log entries."""
        return self.repo.get_audit_log(limit=limit)

    def get_entity_history(self, entity_type: str,
                           limit: int = 50) -> List[Dict]:
        """Get audit log for a specific entity type."""
        return self.repo.get_audit_log(entity_type=entity_type, limit=limit)

