"""IBM Db2 Repository implementation for CloudChange Runs.

Wraps Db2PersistenceAdapter to provide application-level repository semantics
interfacing with FastAPI dependency injection.
"""

from typing import Any, Optional
from backend.app.db2.adapter import Db2PersistenceAdapter
from backend.app.db2.config import Db2Config
from backend.app.db2.connection import Db2ConnectionManager
from backend.app.models.run import Run
from backend.app.repositories.run_repo import RunRepository


class Db2RunRepository(RunRepository):
    """Application repository backed by IBM Db2 relational storage."""

    def __init__(
        self,
        config: Optional[Db2Config] = None,
        adapter: Optional[Db2PersistenceAdapter] = None,
    ) -> None:
        super().__init__()
        self.config = config or Db2Config.from_env()
        self.adapter = adapter or Db2PersistenceAdapter(config=self.config)

    def save(self, run: Run) -> Run:
        """Store or update a Run in IBM Db2 within an atomic transaction."""
        return self.adapter.save_run(run)

    def get(self, run_id: str) -> Optional[Run]:
        """Retrieve a Run by its UUID from IBM Db2."""
        return self.adapter.get_run(run_id)

    def list_all(self) -> list[Run]:
        """List all stored Runs from IBM Db2."""
        return self.adapter.list_runs()

    def clear(self) -> None:
        """Clear all stored Runs from IBM Db2 (for test isolation)."""
        self.adapter.clear()

    def count(self) -> int:
        """Count currently stored Runs in IBM Db2."""
        return self.adapter.count_runs()

    def delete(self, run_id: str) -> bool:
        """Delete a run from IBM Db2."""
        return self.adapter.delete_run(run_id)

    def get_audit_history(self, run_id: str) -> list[dict[str, Any]]:
        """Retrieve audit history from IBM Db2."""
        return self.adapter.get_audit_history(run_id)

    def get_findings_by_severity(self, severity: str) -> list[dict[str, Any]]:
        """Query impact findings matching severity across all runs in IBM Db2."""
        return self.adapter.get_findings_by_severity(severity)

    def get_high_risk_changes(self) -> list[dict[str, Any]]:
        """Query high-risk canonical changes requiring resource replacement."""
        return self.adapter.get_high_risk_changes()

    def get_verification_metrics(self) -> dict[str, Any]:
        """Aggregate post-deployment verification outcomes from IBM Db2."""
        return self.adapter.get_verification_metrics()


# Global or lazy singleton provider
_DB2_REPOSITORY_INSTANCE: Optional[Db2RunRepository] = None


def get_db2_run_repository() -> Db2RunRepository:
    """FastAPI dependency provider returning an active Db2RunRepository."""
    global _DB2_REPOSITORY_INSTANCE
    if _DB2_REPOSITORY_INSTANCE is None:
        _DB2_REPOSITORY_INSTANCE = Db2RunRepository()
    return _DB2_REPOSITORY_INSTANCE
