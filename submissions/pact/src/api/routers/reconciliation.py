"""Reconciliation execution router for PACT."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from api.db import db_transaction
from api.models import ReconciliationRunResult
from api.services.cases import populate_cases_from_reconciliation

router = APIRouter(prefix="/api/v1/reconciliation-runs", tags=["Reconciliation"])


@router.post("", response_model=ReconciliationRunResult, summary="Execute 3-Way Reconciliation Run")
def trigger_reconciliation():
    """Execute complete 3-way reconciliation audit across all live Db2 PO lines and generate cases."""
    try:
        with db_transaction() as conn:
            result = populate_cases_from_reconciliation(conn)
            return ReconciliationRunResult(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "RECONCILIATION_RUN_FAILED",
                    "message": f"Failed executing reconciliation run: {str(e)}",
                    "retryable": False,
                }
            },
        )

