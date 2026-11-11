"""
CivicConnect – FastAPI Backend Server
Exposes REST endpoints consumed by the React frontend and integrates
IBM Db2 (via ibm_db) as the primary complaint database with LangChain
AI-assisted classification.
"""

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db.db2_setup import setup_schema
from db.db2_repository import (
    seed_departments,
    fetch_all_departments,
    insert_complaint,
    fetch_all_complaints,
    fetch_complaints_by_category,
    update_complaint_status,
    get_category_summary,
    get_department_workload,
)
from ai.classifier import classify_complaint


# ---------------------------------------------------------------------------
# App startup / shutdown lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise IBM Db2 schema on startup."""
    try:
        setup_schema()
        seed_departments()
        print("[CivicConnect] IBM Db2 schema ready.")
    except Exception as exc:
        print(f"[CivicConnect] WARNING: Db2 init failed — {exc}")
    yield
    # Nothing to teardown; ibm_db connections are per-request


app = FastAPI(
    title="CivicConnect API",
    description="Smart Civic Complaint Management with IBM Db2 + LangChain",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(default="", max_length=2000)


class ClassifyResponse(BaseModel):
    category: str
    department: str
    priority: str
    keywords: list[str]
    summary: str
    ai_powered: bool


class ComplaintCreateRequest(BaseModel):
    user_id: str
    citizen_name: str
    citizen_email: str
    title: str
    description: str
    category: str
    location: str
    landmark: str = ""
    image_url: str = ""
    priority: str = "medium"
    ai_summary: str = ""
    ai_keywords: list[str] = []


class StatusUpdateRequest(BaseModel):
    new_status: str
    note: str
    updated_by: str
    updated_by_uid: str
    role: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# --- AI Classification ---

@app.post("/api/ai/classify", response_model=ClassifyResponse)
def ai_classify(req: ClassifyRequest):
    """
    AI-assisted complaint classification using LangChain + IBM watsonx.ai.
    Falls back to a deterministic heuristic if no LLM is configured.
    """
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Title is required for classification.")

    result = classify_complaint(req.title, req.description)
    return ClassifyResponse(**result)


# --- Departments ---

@app.get("/api/departments")
def list_departments():
    return {"departments": fetch_all_departments()}


# --- Complaints ---

@app.post("/api/complaints")
def create_complaint(req: ComplaintCreateRequest):
    """Persist a new complaint in IBM Db2."""
    complaint_id = _generate_complaint_id()
    data = {
        "id": str(uuid.uuid4()),
        "complaint_id": complaint_id,
        "user_id": req.user_id,
        "citizen_name": req.citizen_name,
        "citizen_email": req.citizen_email,
        "title": req.title,
        "description": req.description,
        "category": req.category,
        "location": req.location,
        "landmark": req.landmark,
        "image_url": req.image_url,
        "priority": req.priority,
        "status": "Submitted",
        "ai_summary": req.ai_summary,
        "ai_keywords": req.ai_keywords,
    }
    saved = insert_complaint(data)
    return {"success": True, "complaint": saved}


@app.get("/api/complaints")
def list_complaints(limit: int = 500):
    return {"complaints": fetch_all_complaints(limit=limit)}


@app.get("/api/complaints/category/{category}")
def complaints_by_category(category: str):
    return {"complaints": fetch_complaints_by_category(category)}


@app.patch("/api/complaints/{complaint_id}/status")
def patch_status(complaint_id: str, req: StatusUpdateRequest):
    update_complaint_status(
        complaint_id=complaint_id,
        new_status=req.new_status,
        note=req.note,
        updated_by=req.updated_by,
        updated_by_uid=req.updated_by_uid,
        role=req.role,
    )
    return {"success": True, "complaint_id": complaint_id, "new_status": req.new_status}


# --- Analytics ---

@app.get("/api/analytics/categories")
def analytics_categories():
    """Category-level complaint summary — powers the Admin Analytics dashboard."""
    return {"summary": get_category_summary()}


@app.get("/api/analytics/departments")
def analytics_departments():
    """Open complaint counts per department — used for workload balancing."""
    return {"workload": get_department_workload()}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_complaint_id() -> str:
    year = datetime.now().year
    suffix = str(uuid.uuid4().int)[:4]
    return f"CCMS-{year}-{suffix}"


# ---------------------------------------------------------------------------
# Dev entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
