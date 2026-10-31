"""In-memory and Db2 Run Repository Interface.

Provides application-scoped persistence for CloudChange runs with deterministic
test isolation capability and automatic routing to IBM Db2 when configured.
"""

from typing import Any, Optional

from backend.app.models.run import Run


class RunRepository:
    """Application-scoped in-memory repository for CloudChange Runs."""

    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}

    def save(self, run: Run) -> Run:
        """Store or update a Run."""
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> Optional[Run]:
        """Retrieve a Run by its UUID."""
        return self._runs.get(run_id)

    def list_all(self) -> list[Run]:
        """List all stored Runs."""
        return list(self._runs.values())

    def clear(self) -> None:
        """Clear all stored Runs (for deterministic test isolation)."""
        self._runs.clear()

    def count(self) -> int:
        """Count currently stored Runs."""
        return len(self._runs)

    def delete(self, run_id: str) -> bool:
        """Delete a Run by its UUID."""
        if run_id in self._runs:
            del self._runs[run_id]
            return True
        return False

    def get_audit_history(self, run_id: str) -> list[dict[str, Any]]:
        """In-memory fallback for audit history."""
        return []

    def get_findings_by_severity(self, severity: str) -> list[dict[str, Any]]:
        """In-memory fallback for severity filtering."""
        results = []
        for run in self._runs.values():
            for f in run.findings:
                sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
                if sev.upper() == severity.upper():
                    results.append(f.model_dump())
        return results

    def get_high_risk_changes(self) -> list[dict[str, Any]]:
        """In-memory fallback for high-risk changes."""
        results = []
        for run in self._runs.values():
            for c in run.changes:
                if c.requires_replacement:
                    results.append(c.model_dump())
        return results

    def get_verification_metrics(self) -> dict[str, Any]:
        """In-memory fallback for verification metrics."""
        metrics = {"total": 0, "by_status": {}}
        for run in self._runs.values():
            for res in run.verification_results:
                st = res.status.value if hasattr(res.status, "value") else str(res.status)
                metrics["by_status"][st] = metrics["by_status"].get(st, 0) + 1
                metrics["total"] += 1
        return metrics


# Application-scoped singleton repository instance
_DEFAULT_RUN_REPOSITORY = RunRepository()


def get_run_repository() -> RunRepository:
    """FastAPI dependency provider returning either Db2RunRepository or in-memory RunRepository."""
    from backend.app.config import settings

    if settings.DATABASE_BACKEND.lower() == "db2":
        from backend.app.repositories.db2_repo import get_db2_run_repository
        return get_db2_run_repository()

    return _DEFAULT_RUN_REPOSITORY
