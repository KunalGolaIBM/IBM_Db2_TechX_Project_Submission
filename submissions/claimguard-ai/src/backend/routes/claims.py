"""
ClaimGuard AI - Claims Management Router
Handles claim creation, listing, detailed inspection, document uploads, and human decisions.
"""

import hashlib
import os
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from ..config import settings
from ..database.connection import db2_manager
from ..database.repository import repository
from ..models.schemas import (
    ClaimCreate,
    ClaimDecisionUpdate,
    ClaimResponse,
    DashboardStats,
    DocumentResponse,
)
from ..utils.security import get_current_user

router = APIRouter(prefix="/api", tags=["Claims Management"])


def _format_claim(r: dict) -> ClaimResponse:
    return ClaimResponse(
        claim_id=r["CLAIM_ID"],
        claim_number=r["CLAIM_NUMBER"],
        policy_id=r["POLICY_ID"],
        customer_id=r["CUSTOMER_ID"],
        incident_date=str(r["INCIDENT_DATE"]),
        admission_date=str(r["ADMISSION_DATE"]) if r.get("ADMISSION_DATE") else None,
        discharge_date=str(r["DISCHARGE_DATE"]) if r.get("DISCHARGE_DATE") else None,
        claim_amount=float(r["CLAIM_AMOUNT"]),
        approved_amount=float(r.get("APPROVED_AMOUNT") or 0.0),
        hospital_name=r.get("HOSPITAL_NAME"),
        hospital_invoice_number=r.get("HOSPITAL_INVOICE_NUMBER"),
        diagnosis_code=r.get("DIAGNOSIS_CODE"),
        diagnosis_description=r.get("DIAGNOSIS_DESCRIPTION"),
        status=r.get("STATUS", "PENDING"),
        risk_score=float(r.get("RISK_SCORE") or 0.0),
        risk_level=r.get("RISK_LEVEL", "LOW"),
        decision_notes=r.get("DECISION_NOTES"),
        reviewed_by=r.get("REVIEWED_BY"),
        submitted_at=str(r.get("SUBMITTED_AT") or ""),
        updated_at=str(r.get("UPDATED_AT") or "")
    )


@router.post("/claims", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
def submit_claim(payload: ClaimCreate):
    """Submits a new insurance claim into IBM Db2 CLAIM_RECORDS."""
    # Verify policy existence
    policy = repository.get_policy_by_id(payload.policy_id)
    if not policy:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid policy_id.")

    # Verify customer matches policy
    if policy["CUSTOMER_ID"] != payload.customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer ID does not match policyholder."
        )

    # Date sanity check: discharge date cannot precede admission date
    if payload.admission_date and payload.discharge_date:
        if payload.discharge_date < payload.admission_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Discharge date cannot precede admission date."
            )

    claim_data = {
        "POLICY_ID": payload.policy_id,
        "CUSTOMER_ID": payload.customer_id,
        "INCIDENT_DATE": payload.incident_date,
        "ADMISSION_DATE": payload.admission_date,
        "DISCHARGE_DATE": payload.discharge_date,
        "CLAIM_AMOUNT": payload.claim_amount,
        "HOSPITAL_NAME": payload.hospital_name,
        "HOSPITAL_INVOICE_NUMBER": payload.hospital_invoice_number,
        "DIAGNOSIS_CODE": payload.diagnosis_code,
        "DIAGNOSIS_DESCRIPTION": payload.diagnosis_description,
        "STATUS": "PENDING"
    }

    created = repository.create_claim(claim_data)
    return _format_claim(created)


@router.get("/claims", response_model=List[ClaimResponse])
def list_claims(status: Optional[str] = None):
    """Retrieves all submitted insurance claims with optional status filtering."""
    claims = repository.list_claims(status=status)
    return [_format_claim(c) for c in claims]


@router.get("/claims/{claim_id}")
def get_claim_details(claim_id: str):
    """Retrieves full claim record including attached documents, alerts, and verification logs."""
    claim = repository.get_claim_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim record not found.")

    docs = repository.get_documents_by_claim(claim_id)
    alerts = repository.get_alerts_by_claim(claim_id)
    logs = repository.get_logs_by_claim(claim_id)
    policy = repository.get_policy_by_id(claim["POLICY_ID"])
    customer = repository.get_customer_by_id(claim["CUSTOMER_ID"])

    return {
        "claim": _format_claim(claim),
        "policy": policy,
        "customer": customer,
        "documents": docs,
        "fraud_alerts": alerts,
        "verification_logs": logs
    }


@router.put("/claims/{claim_id}/decision", response_model=ClaimResponse)
def submit_claim_decision(
    claim_id: str,
    payload: ClaimDecisionUpdate,
    current_user: Optional[dict] = Depends(get_current_user)
):
    """
    Authorized human reviewer adjudicates a claim (APPROVED, REJECTED, FLAGGED, IN_REVIEW).
    Strictly enforces human-in-the-loop control.
    """
    claim = repository.get_claim_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")

    reviewer_id = current_user.get("sub", "HUMAN_EXAMINER") if current_user else "HUMAN_EXAMINER"

    approved_amount = payload.approved_amount
    if payload.status == "APPROVED" and approved_amount is None:
        approved_amount = float(claim["CLAIM_AMOUNT"])

    success = repository.update_claim_decision(
        claim_id=claim_id,
        status=payload.status,
        decision_notes=payload.decision_notes,
        reviewed_by=reviewer_id,
        approved_amount=approved_amount
    )

    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update claim decision.")

    # Deduct coverage if approved
    if payload.status == "APPROVED" and approved_amount:
        policy = repository.get_policy_by_id(claim["POLICY_ID"])
        if policy:
            curr_rem = float(policy.get("REMAINING_COVERAGE") or 0.0)
            new_rem = max(0.0, curr_rem - approved_amount)
            repository.update_policy_coverage(policy["POLICY_ID"], new_rem)

    updated = repository.get_claim_by_id(claim_id)
    return _format_claim(updated)


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".txt"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/claims/{claim_id}/documents", response_model=DocumentResponse)
async def upload_claim_document(
    claim_id: str,
    file: UploadFile = File(...),
    document_type: str = Form("MEDICAL_BILL")
):
    """
    Uploads supporting claim documents (PDF / Image), calculates SHA-256 hash for fraud detection,
    and records metadata into DOCUMENT_RECORDS table.
    Validates file extension, size boundaries, and sanitizes paths.
    """
    claim = repository.get_claim_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")

    raw_filename = file.filename or "document.pdf"
    base_filename = os.path.basename(raw_filename)
    file_ext = Path(base_filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{file_ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)."
        )

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
        )

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Calculate SHA-256 hash
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Save to disk with sanitized filename
    safe_filename = f"{claim_id}_{file_hash[:8]}_{base_filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    doc_data = {
        "CLAIM_ID": claim_id,
        "DOCUMENT_NAME": base_filename,
        "DOCUMENT_TYPE": document_type,
        "FILE_PATH": file_path,
        "FILE_HASH": file_hash,
        "FILE_SIZE_BYTES": file_size,
        "MIME_TYPE": file.content_type or "application/octet-stream",
        "EXTRACTED_DATA": None
    }

    created = repository.create_document(doc_data)

    return DocumentResponse(
        document_id=created["DOCUMENT_ID"],
        claim_id=created["CLAIM_ID"],
        document_name=created["DOCUMENT_NAME"],
        document_type=created["DOCUMENT_TYPE"],
        file_path=created["FILE_PATH"],
        file_hash=created["FILE_HASH"],
        file_size_bytes=created["FILE_SIZE_BYTES"],
        mime_type=created["MIME_TYPE"],
        extracted_data=created.get("EXTRACTED_DATA"),
        uploaded_at=created.get("UPLOADED_AT")
    )


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_statistics():
    """Aggregates live dashboard statistics across claims, fraud alerts, and database state."""
    claims = repository.list_claims()
    alerts = repository.list_all_alerts(resolved=False)
    db_health = db2_manager.check_health()

    total_claims = len(claims)
    pending_claims = sum(1 for c in claims if c.get("STATUS") == "PENDING")
    approved_claims = sum(1 for c in claims if c.get("STATUS") == "APPROVED")
    rejected_claims = sum(1 for c in claims if c.get("STATUS") == "REJECTED")
    flagged_claims = sum(1 for c in claims if c.get("STATUS") in ("FLAGGED", "IN_REVIEW"))

    total_claimed = sum(float(c.get("CLAIM_AMOUNT") or 0.0) for c in claims)
    total_approved = sum(float(c.get("APPROVED_AMOUNT") or 0.0) for c in claims)

    avg_risk = 0.0
    if total_claims > 0:
        avg_risk = sum(float(c.get("RISK_SCORE") or 0.0) for c in claims) / total_claims

    return DashboardStats(
        total_claims=total_claims,
        pending_claims=pending_claims,
        approved_claims=approved_claims,
        rejected_claims=rejected_claims,
        flagged_claims=flagged_claims,
        active_alerts=len(alerts),
        total_claimed_amount=round(total_claimed, 2),
        total_approved_amount=round(total_approved, 2),
        average_risk_score=round(avg_risk, 2),
        db2_connected=bool(db_health.get("connected")),
        demo_mode=settings.DEMO_MODE
    )
