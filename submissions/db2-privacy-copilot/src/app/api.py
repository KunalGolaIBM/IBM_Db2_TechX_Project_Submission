"""
FastAPI backend for Db2 Privacy Copilot.

Provides REST API for:
- Schema discovery and classification
- Consent management
- Rights requests and approval
- Audit log viewing

Authentication: Simple token-based (upgrade to OAuth2/JWT for production)

Security Recommendations for Production:
1. Replace mock USERS dict with database-backed authentication
2. Implement proper JWT token validation
3. Add rate limiting (e.g., slowapi or nginx)
4. Enable HTTPS only (TLS 1.2+)
5. Implement CSRF protection
6. Add request logging and monitoring
7. Use environment variables for secrets
8. Implement API versioning (/v1/)
9. Add request validation and sanitization
10. Enable audit logging for all sensitive operations
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app import agents, audit, consent, erasure
from app.config import settings
from app.db import query

# FastAPI app
app = FastAPI(
    title="Db2 Privacy Copilot API",
    description="DPDP compliance system for IBM Db2",
    version="0.1.0",
)

# CORS middleware (configure for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple authentication (upgrade for production)
security = HTTPBearer()

# Mock users (replace with real user database)
USERS = {
    "viewer_token": {"email": "viewer@example.com", "role": "VIEWER"},
    "analyst_token": {"email": "analyst@example.com", "role": "ANALYST"},
    "dpo_token": {"email": "dpo@example.com", "role": "DPO"},
}


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """Get current user from token."""
    token = credentials.credentials
    user = USERS.get(token)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    
    return user


def require_role(required_role: str):
    """Dependency to require a specific role."""
    def check_role(user: dict = Depends(get_current_user)):
        # Role hierarchy: VIEWER < ANALYST < DPO
        roles = {"VIEWER": 1, "ANALYST": 2, "DPO": 3}
        
        user_level = roles.get(user["role"], 0)
        required_level = roles.get(required_role, 99)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {required_role} role",
            )
        
        return user
    
    return check_role


# Request/Response models

class SchemaDiscoveryResponse(BaseModel):
    schema: str
    tables: list[str]
    column_count: int
    fk_count: int
    columns_by_table: dict


class ClassificationSummary(BaseModel):
    total_columns: int
    pii_columns: int
    needs_review: int
    by_label: dict


class ConsentGrantRequest(BaseModel):
    patient_id: int
    purpose: str
    start: str
    end: str = "9999-12-30"
    
    @property
    def validate_purpose(self):
        """Validate purpose is one of allowed values."""
        allowed = ["MARKETING", "RESEARCH", "TREATMENT", "ANALYTICS", "INSURANCE"]
        if self.purpose not in allowed:
            raise ValueError(f"Purpose must be one of: {', '.join(allowed)}")
        return self.purpose


class ConsentWithdrawRequest(BaseModel):
    patient_id: int
    purpose: str
    effective: str


class ErasureRequest(BaseModel):
    subject_id: int
    schema: Optional[str] = None


class ErasurePlan(BaseModel):
    subject_id: int
    plan_hash: str
    total_steps: int
    total_rows: int
    steps: list[dict]
    has_unverified: bool


class ApprovalRequest(BaseModel):
    approval_id: str
    approver_notes: Optional[str] = None


# Routes

@app.get("/")
def root():
    """API root endpoint."""
    return {
        "name": "Db2 Privacy Copilot API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/healthz")
def healthz():
    """Health check for the API and its Db2 connection."""
    version = query("SELECT SERVICE_LEVEL FROM SYSIBMADM.ENV_INST_INFO")
    if not version:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database health check returned no version",
        )
    query("SELECT 1 FROM SYSIBM.SYSDUMMY1")
    return {"status": "ok", "db2": version[0][0]}


@app.get("/health")
def health():
    """Health check endpoint with detailed component status."""
    try:
        # Test database connection
        result = query("SELECT 1 FROM SYSIBM.SYSDUMMY1")
        db_ok = result is not None
        db_error = None
    except Exception as e:
        db_ok = False
        db_error = str(e)
    
    # Check if tables exist
    try:
        tables_result = query("""
            SELECT COUNT(*) FROM SYSCAT.TABLES 
            WHERE TABSCHEMA = ?
        """, (settings.db2_schema,))
        tables_ok = tables_result is not None
        table_count = tables_result[0][0] if tables_result else 0
    except Exception as e:
        tables_ok = False
        table_count = 0
    
    overall_status = "healthy" if (db_ok and tables_ok) else "unhealthy"
    
    response = {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": {
                "status": "up" if db_ok else "down",
                "error": db_error
            },
            "schema": {
                "status": "ok" if tables_ok else "missing",
                "table_count": table_count
            }
        }
    }
    
    status_code = 200 if overall_status == "healthy" else 503
    return JSONResponse(content=response, status_code=status_code)


# Discovery endpoints

@app.get("/discovery/{schema}", response_model=SchemaDiscoveryResponse)
def discover_schema(
    schema: str,
    user: dict = Depends(require_role("VIEWER"))
):
    """Discover database schema."""
    result = agents.discover_schema(schema)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# Classification endpoints

@app.get("/classification/{schema}", response_model=ClassificationSummary)
def classify_schema(
    schema: str,
    user: dict = Depends(require_role("ANALYST"))
):
    """Classify columns as PII."""
    result = agents.classify_schema(schema)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@app.get("/classification/{schema}/details")
def classification_details(
    schema: str,
    user: dict = Depends(require_role("ANALYST"))
):
    """Get detailed classification results."""
    result = agents.classify_schema(schema)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


# Consent endpoints

@app.post("/consent/grant")
def grant_consent(
    request: ConsentGrantRequest,
    user: dict = Depends(require_role("ANALYST"))
):
    """Grant consent for a purpose."""
    try:
        consent.grant(
            request.patient_id,
            request.purpose,
            request.start,
            request.end
        )
        
        # Log action
        audit.append(
            user["email"],
            "CONSENT_GRANTED",
            request.patient_id,
            {"purpose": request.purpose, "start": request.start, "end": request.end}
        )
        
        return {"status": "granted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/consent/withdraw")
def withdraw_consent(
    request: ConsentWithdrawRequest,
    user: dict = Depends(require_role("ANALYST"))
):
    """Withdraw consent."""
    try:
        consent.withdraw(
            request.patient_id,
            request.purpose,
            request.effective
        )
        
        # Log action
        audit.append(
            user["email"],
            "CONSENT_WITHDRAWN",
            request.patient_id,
            {"purpose": request.purpose, "effective": request.effective}
        )
        
        return {"status": "withdrawn"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/consent/{patient_id}")
def get_consents(
    patient_id: int,
    user: dict = Depends(require_role("VIEWER"))
):
    """Get current consents for a patient."""
    try:
        consents = consent.current_consents(patient_id)
        return {"patient_id": patient_id, "consents": consents}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Rights request endpoints

@app.post("/requests", response_model=ErasurePlan)
def create_request(
    request: ErasureRequest,
    user: dict = Depends(require_role("ANALYST"))
):
    """Create an erasure request (generates plan)."""
    try:
        result = agents.plan_erasure(request.subject_id, request.schema)
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Store request in database
        import json
        plan_json = json.dumps(result)
        
        query("""
            INSERT INTO REQUESTS (REQUEST_TYPE, SUBJECT_ID, STATUS, DUE_AT, PLAN_JSON, PLAN_HASH)
            VALUES ('ERASURE', ?, 'PENDING_APPROVAL', ?, ?, ?)
        """, (
            request.subject_id,
            (datetime.now() + timedelta(days=settings.default_request_deadline_days)).isoformat(),
            plan_json,
            result["plan_hash"]
        ))
        
        # Log action
        audit.append(
            user["email"],
            "REQUEST_CREATED",
            request.subject_id,
            {"type": "ERASURE", "plan_hash": result["plan_hash"]}
        )
        
        return {
            "subject_id": result["subject_id"],
            "plan_hash": result["plan_hash"],
            "total_steps": result["simulation"]["total_steps"],
            "total_rows": result["simulation"]["total_rows"],
            "steps": result["steps"],
            "has_unverified": result["simulation"]["has_unverified"],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/requests")
def list_requests(
    status_filter: Optional[str] = None,
    user: dict = Depends(require_role("VIEWER"))
):
    """List all requests."""
    try:
        if status_filter:
            rows = query("""
                SELECT ID, REQUEST_TYPE, SUBJECT_ID, STATUS, RECEIVED_AT, DUE_AT
                FROM REQUESTS
                WHERE STATUS = ?
                ORDER BY RECEIVED_AT DESC
            """, (status_filter,))
        else:
            rows = query("""
                SELECT ID, REQUEST_TYPE, SUBJECT_ID, STATUS, RECEIVED_AT, DUE_AT
                FROM REQUESTS
                ORDER BY RECEIVED_AT DESC
            """)
        
        requests = []
        if rows:
            for row in rows:
                requests.append({
                    "id": row[0],
                    "type": row[1],
                    "subject_id": row[2],
                    "status": row[3],
                    "received_at": str(row[4]),
                    "due_at": str(row[5]),
                })
        
        return {"requests": requests}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/requests/{request_id}")
def get_request(
    request_id: int,
    user: dict = Depends(require_role("VIEWER"))
):
    """Get request details."""
    try:
        rows = query("""
            SELECT ID, REQUEST_TYPE, SUBJECT_ID, STATUS, PLAN_JSON, PLAN_HASH, 
                   RECEIVED_AT, DUE_AT, APPROVED_BY, APPROVED_AT
            FROM REQUESTS
            WHERE ID = ?
        """, (request_id,))
        
        if not rows:
            raise HTTPException(status_code=404, detail="Request not found")
        
        row = rows[0]
        import json
        
        return {
            "id": row[0],
            "type": row[1],
            "subject_id": row[2],
            "status": row[3],
            "plan": json.loads(row[4]) if row[4] else None,
            "plan_hash": row[5],
            "received_at": str(row[6]),
            "due_at": str(row[7]),
            "approved_by": row[8],
            "approved_at": str(row[9]) if row[9] else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/requests/{request_id}/approve")
def approve_request(
    request_id: int,
    approval: ApprovalRequest,
    user: dict = Depends(require_role("DPO"))
):
    """Approve and execute an erasure request."""
    try:
        # Get request
        rows = query("""
            SELECT SUBJECT_ID, PLAN_JSON, PLAN_HASH, STATUS
            FROM REQUESTS
            WHERE ID = ?
        """, (request_id,))
        
        if not rows:
            raise HTTPException(status_code=404, detail="Request not found")
        
        subject_id, plan_json, plan_hash, status = rows[0]
        
        if status != "PENDING_APPROVAL":
            raise HTTPException(status_code=400, detail=f"Request status is {status}")
        
        # Parse plan
        import json
        plan_data = json.loads(plan_json)
        
        # Reconstruct steps
        from app.erasure import Step
        steps = []
        for step_data in plan_data["steps"]:
            # We need to rebuild the full Step objects from stored data
            # For simplicity, regenerate the plan
            pass
        
        # Regenerate plan to get full Step objects
        from app.erasure import plan as generate_plan
        steps = generate_plan(subject_id)
        
        # Update request status
        query("""
            UPDATE REQUESTS
            SET STATUS = 'APPROVED', APPROVED_BY = ?, APPROVED_AT = CURRENT TIMESTAMP,
                APPROVAL_ID = ?
            WHERE ID = ?
        """, (user["email"], approval.approval_id, request_id))
        
        # Execute
        erasure.execute(
            steps,
            subject_id,
            user["email"],
            approval.approval_id,
            plan_hash
        )
        
        return {
            "status": "completed",
            "subject_id": subject_id,
            "approver": user["email"],
            "approval_id": approval.approval_id,
        }
    
    except erasure.PlanChanged as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Audit endpoints

@app.get("/audit")
def get_audit_log(
    limit: int = 100,
    user: dict = Depends(require_role("VIEWER"))
):
    """Get audit log entries."""
    try:
        records = audit.get_all_records()
        
        # Return most recent N records
        recent = records[-limit:] if len(records) > limit else records
        
        return {
            "total": len(records),
            "returned": len(recent),
            "records": [
                {
                    "id": r.id,
                    "actor": r.actor,
                    "action": r.action,
                    "subject": r.subject,
                    "detail": r.detail,
                    "created_at": str(r.created_at),
                    "hash": r.hash[:16] + "...",
                }
                for r in reversed(recent)
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/audit/verify")
def verify_audit_chain(user: dict = Depends(require_role("DPO"))):
    """Verify audit chain integrity."""
    try:
        is_valid, error = audit.verify_chain()
        
        return {
            "valid": is_valid,
            "error": error,
            "message": "Chain is intact" if is_valid else f"Tampering detected: {error}",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/audit/subject/{subject_id}")
def get_audit_by_subject(
    subject_id: int,
    user: dict = Depends(require_role("VIEWER"))
):
    """Get audit records for a specific subject."""
    try:
        records = audit.get_records_by_subject(subject_id)
        
        return {
            "subject_id": subject_id,
            "record_count": len(records),
            "records": [
                {
                    "id": r.id,
                    "actor": r.actor,
                    "action": r.action,
                    "detail": r.detail,
                    "created_at": str(r.created_at),
                }
                for r in records
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("Starting Db2 Privacy Copilot API")
    print("=" * 60)
    print(f"\nAPI Documentation: http://localhost:{settings.api_port}/docs")
    print("\nTest tokens:")
    print("  Viewer:  viewer_token")
    print("  Analyst: analyst_token")
    print("  DPO:     dpo_token")
    print("\nExample:")
    print('  curl -H "Authorization: Bearer viewer_token" http://localhost:8000/health')
    print("\n" + "=" * 60)
    
    uvicorn.run(
        "app.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
