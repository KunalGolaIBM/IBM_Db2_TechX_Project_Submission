"""
ClaimGuard AI - Audit & Fraud Alerts Router
Handles fraud investigation alerts, audit logging, and explainable AI reporting.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from ..database.repository import repository
from ..models.schemas import (
    AlertResolveRequest,
    FraudAlertResponse,
    VerificationLogResponse,
)
from ..utils.security import get_current_user

router = APIRouter(prefix="/api", tags=["Audit & Fraud Investigation"])


@router.get("/fraud/alerts", response_model=List[FraudAlertResponse])
def list_fraud_alerts(resolved: Optional[bool] = None):
    """Retrieves fraud alerts from IBM Db2 FRAUD_ALERTS table."""
    rows = repository.list_all_alerts(resolved=resolved)
    return [
        FraudAlertResponse(
            alert_id=r["ALERT_ID"],
            claim_id=r["CLAIM_ID"],
            alert_type=r["ALERT_TYPE"],
            severity=r["SEVERITY"],
            description=r["DESCRIPTION"],
            evidence_details=r.get("EVIDENCE_DETAILS"),
            is_resolved=int(r.get("IS_RESOLVED") or 0),
            resolved_by=r.get("RESOLVED_BY"),
            resolution_notes=r.get("RESOLUTION_NOTES"),
            created_at=str(r.get("CREATED_AT") or "")
        )
        for r in rows
    ]


@router.post("/fraud/alerts/{alert_id}/resolve")
def resolve_fraud_alert(
    alert_id: str,
    payload: AlertResolveRequest,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Marks a fraud alert as investigated and resolved by an examiner."""
    resolver = current_user.get("username", "examiner") if current_user else "examiner"
    success = repository.resolve_alert(alert_id, resolver, payload.resolution_notes)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fraud alert not found.")
    return {"status": "success", "alert_id": alert_id, "resolved_by": resolver}


@router.get("/audit-logs", response_model=List[VerificationLogResponse])
def get_audit_logs(limit: int = 50):
    """Retrieves recent verification logs from IBM Db2 VERIFICATION_LOGS."""
    rows = repository.list_recent_logs(limit=limit)
    return [
        VerificationLogResponse(
            log_id=r["LOG_ID"],
            claim_id=r["CLAIM_ID"],
            agent_name=r["AGENT_NAME"],
            action=r["ACTION"],
            status=r["STATUS"],
            details=r.get("DETAILS"),
            execution_time_ms=int(r.get("EXECUTION_TIME_MS") or 0),
            created_at=str(r.get("CREATED_AT") or "")
        )
        for r in rows
    ]


@router.get("/reports/{claim_id}")
def generate_claim_report(claim_id: str):
    """
    Generates an explainable verification report synthesizing claim details,
    policy constraints, document hashes, detected anomalies, and agent audit trail.
    """
    claim = repository.get_claim_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")

    policy = repository.get_policy_by_id(claim["POLICY_ID"])
    customer = repository.get_customer_by_id(claim["CUSTOMER_ID"])
    alerts = repository.get_alerts_by_claim(claim_id)
    docs = repository.get_documents_by_claim(claim_id)
    logs = repository.get_logs_by_claim(claim_id)

    # Build recommendations
    recommendation = "APPROVE"
    reasons = []

    if alerts:
        unresolved = [a for a in alerts if not a.get("IS_RESOLVED")]
        if unresolved:
            recommendation = "FLAG_FOR_MANUAL_REVIEW"
            for a in unresolved:
                reasons.append(f"[{a['SEVERITY']}] {a['ALERT_TYPE']}: {a['DESCRIPTION']}")

    if policy:
        rem_cov = float(policy.get("REMAINING_COVERAGE") or 0.0)
        claim_amt = float(claim.get("CLAIM_AMOUNT") or 0.0)
        if claim_amt > rem_cov:
            recommendation = "ADJUST_OR_REJECT"
            reasons.append(f"Claim amount (${claim_amt:,.2f}) exceeds policy remaining coverage (${rem_cov:,.2f}).")

    if not docs:
        if recommendation != "ADJUST_OR_REJECT":
            recommendation = "REQUEST_ADDITIONAL_DOCUMENTS"
        reasons.append("No medical or financial documentation uploaded.")

    return {
        "claim_id": claim_id,
        "claim_number": claim["CLAIM_NUMBER"],
        "customer": {
            "name": f"{customer['FIRST_NAME']} {customer['LAST_NAME']}" if customer else "N/A",
            "email": customer.get("EMAIL") if customer else "N/A",
            "national_id": customer.get("NATIONAL_ID") if customer else "N/A"
        },
        "policy": {
            "policy_number": policy.get("POLICY_NUMBER") if policy else "N/A",
            "policy_type": policy.get("POLICY_TYPE") if policy else "N/A",
            "remaining_coverage": float(policy.get("REMAINING_COVERAGE") or 0.0) if policy else 0.0,
            "deductible": float(policy.get("DEDUCTIBLE") or 0.0) if policy else 0.0
        },
        "risk_assessment": {
            "risk_score": float(claim.get("RISK_SCORE") or 0.0),
            "risk_level": claim.get("RISK_LEVEL", "LOW"),
            "recommendation": recommendation,
            "reasons": reasons
        },
        "evidence": {
            "documents_count": len(docs),
            "alerts_count": len(alerts),
            "audit_steps_count": len(logs)
        },
        "verification_history": logs
    }
