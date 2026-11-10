import logging
import random
import math
import csv
import io
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from config import settings
from database import engine, get_db, wait_for_database, init_db
from models import Department, Grievance, GrievanceUpdate
from schemas import (
    GrievanceCreate,
    GrievanceOut,
    GrievanceStatusUpdate,
    GrievanceListResponse,
    DepartmentOut,
    StatsResponse,
    GrievanceCreateResponse,
    AskQuestionRequest,
    AskQuestionResponse,
    AnalyticsResponse,
    DraftActionRequest,
    DraftActionResponse,
    ResolveDocketRequest,
    OfficerDocketOut,
    WardGeoHotspotOut,
    GeoHotspotsResponse,
    SahayakChatRequest,
    SahayakChatResponse
)
from ai_service import (
    triage_grievance,
    generate_db2_sql,
    detect_ward_hotspots_and_duplicates,
    generate_natural_summary,
    draft_officer_action_order,
    run_sahayak_agent
)
from scripts.seed_data import seed_grievances

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown events
    Initializes IBM Db2 database schema and seeds initial dataset if empty.
    """
    logger.info("Starting CPGRAMS Grievance Redressal Backend for IBM Db2Hack 2026...")
    try:
        # Check database readiness (waits for IBM Db2 container startup)
        wait_for_database(max_retries=30, delay=2.5)

        # Create tables in IBM Db2
        init_db()

        # Seed realistic dataset (minimum 60 grievances) into IBM Db2
        from database import SessionLocal
        with SessionLocal() as db:
            seeded = seed_grievances(db)
            logger.info(f"IBM Db2 database initialization complete. Seeded/verified {seeded} grievances.")
    except Exception as e:
        logger.error(f"Startup initialization error: {e}")
        raise

    yield

    logger.info("Shutting down CPGRAMS API backend...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="CPGRAMS Citizen Grievance Portal API powered by IBM Db2 Community Edition & FastAPI.",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def generate_unique_tracking_id(db: Session) -> str:
    """
    Generates a unique tracking ID in the format GRV-2026-XXXX.
    Ensures no collision exists in IBM Db2 table.
    """
    for _ in range(20):
        random_digits = random.randint(1000, 9999)
        candidate = f"{settings.TRACKING_ID_PREFIX}{random_digits}"
        existing = db.query(Grievance.id).filter(Grievance.tracking_id == candidate).first()
        if not existing:
            return candidate
    # Fallback to timestamp-based sequence if collisions occur
    ts_suffix = str(int(datetime.utcnow().timestamp()))[-4:]
    return f"{settings.TRACKING_ID_PREFIX}{ts_suffix}"


def serialize_grievance(grv: Grievance) -> Dict[str, Any]:
    """
    Helper to serialize a Grievance ORM object with its department and updates.
    """
    dept_name = grv.department.name if grv.department else None
    return {
        "id": grv.id,
        "tracking_id": grv.tracking_id,
        "citizen_name": grv.citizen_name,
        "contact": grv.contact,
        "category": grv.category,
        "subject": grv.subject,
        "description": grv.description,
        "ward": grv.ward,
        "priority": grv.priority,
        "status": grv.status,
        "created_at": grv.created_at,
        "resolved_at": grv.resolved_at,
        "department_id": grv.department_id,
        "department_name": dept_name,
        "state": grv.state,
        "pincode": grv.pincode,
        "latitude": grv.latitude,
        "longitude": grv.longitude,
        "ai_category": getattr(grv, "ai_category", None),
        "ai_priority": getattr(grv, "ai_priority", None),
        "ai_summary": getattr(grv, "ai_summary", None),
        "updates": [
            {
                "id": u.id,
                "grievance_id": u.grievance_id,
                "previous_status": u.previous_status,
                "new_status": u.new_status,
                "notes": u.notes,
                "updated_by": u.updated_by,
                "created_at": u.created_at
            }
            for u in sorted(grv.updates, key=lambda x: x.id or 0)
        ]
    }


# ==============================================================================
# Health & Diagnostic Endpoints
# ==============================================================================

@app.get(f"{settings.API_PREFIX}/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """
    Verifies IBM Db2 database connectivity and returns system status.
    """
    try:
        db.execute(text("SELECT 1 FROM SYSIBM.SYSDUMMY1"))
        db2_status = "connected"
    except Exception as e:
        logger.error(f"IBM Db2 health check error: {e}")
        db2_status = f"unreachable: {str(e)}"

    total_records = db.query(Grievance).count() if db2_status == "connected" else 0

    return {
        "status": "healthy" if db2_status == "connected" else "degraded",
        "database": {
            "type": "IBM Db2",
            "host": settings.DB2_HOST,
            "database": settings.DB2_DATABASE,
            "status": db2_status,
            "total_grievances": total_records
        },
        "version": settings.APP_VERSION,
        "timestamp": datetime.utcnow().isoformat()
    }


# ==============================================================================
# Departments Endpoints
# ==============================================================================

@app.get(f"{settings.API_PREFIX}/departments", response_model=List[DepartmentOut], tags=["Departments"])
def list_departments(db: Session = Depends(get_db)):
    """
    List all government departments handling citizen grievances.
    """
    departments = db.query(Department).order_by(Department.name.asc()).all()
    return departments


# ==============================================================================
# Grievances Core Endpoints
# ==============================================================================

@app.post(
    f"{settings.API_PREFIX}/grievances",
    status_code=status.HTTP_201_CREATED,
    tags=["Grievances"]
)
def create_grievance(payload: GrievanceCreate, db: Session = Depends(get_db)):
    """
    Lodge a new grievance in IBM Db2 with automated AI Triage (LangChain)
    and Ward Hotspot / Duplicate Detection.
    - Runs LangChain prompt chain to extract AI category, priority, and summary.
    - Generates a unique tracking ID (format: GRV-2026-XXXX).
    - Checks IBM Db2 for open duplicate grievances and active ward hotspots.
    - Stores grievance record with all citizen, location, and AI triage details in Db2.
    - Automatically creates initial status history entry ('Filed').
    """
    tracking_id = generate_unique_tracking_id(db)

    # 1. Run AI Triage (LangChain Prompt Chain with Rule-Based Fallback)
    ai_triage_result = triage_grievance(
        description=payload.description,
        subject=payload.subject or "",
        category_hint=payload.category
    )

    # Priority determination: use AI triage priority unless citizen explicitly selected a non-default priority
    final_priority = payload.priority if (payload.priority and payload.priority != "Medium") else ai_triage_result.priority

    # Department resolution
    dept_id = payload.department_id
    if not dept_id:
        dept = db.query(Department).filter(
            or_(
                Department.code == payload.category.lower(),
                Department.name.ilike(f"%{payload.category}%")
            )
        ).first()
        if dept:
            dept_id = dept.id

    new_grv = Grievance(
        tracking_id=tracking_id,
        citizen_name=payload.citizen_name.strip(),
        contact=payload.contact.strip(),
        category=payload.category.strip(),
        subject=payload.subject.strip() if payload.subject else payload.description[:80],
        description=payload.description.strip(),
        ward=payload.ward.strip() if payload.ward else "Ward 14 - Rohini East",
        priority=final_priority,
        status="Filed",
        created_at=datetime.utcnow(),
        department_id=dept_id,
        state=payload.state or "Delhi (NCT)",
        pincode=payload.pincode,
        latitude=payload.latitude,
        longitude=payload.longitude,
        ai_category=ai_triage_result.category,
        ai_priority=ai_triage_result.priority,
        ai_summary=ai_triage_result.summary
    )

    db.add(new_grv)
    try:
        db.flush()
    except Exception as integrity_err:
        db.rollback()
        # Retry with a fresh tracking ID on collision
        tracking_id = generate_unique_tracking_id(db)
        new_grv.tracking_id = tracking_id
        db.add(new_grv)
        db.flush()

    # Create initial audit history row
    initial_update = GrievanceUpdate(
        grievance_id=new_grv.id,
        previous_status=None,
        new_status="Filed",
        notes=f"Grievance lodged via Citizen Portal. AI Triage classified priority as '{ai_triage_result.priority}' ({ai_triage_result.method}).",
        updated_by="CPGRAMS AI Intake",
        created_at=datetime.utcnow()
    )
    db.add(initial_update)
    db.commit()
    db.refresh(new_grv)

    # 2. Duplicate / Ward Hotspot Detection in IBM Db2
    hotspot_dup_info = detect_ward_hotspots_and_duplicates(
        db=db,
        ward=new_grv.ward,
        category=new_grv.category,
        description=new_grv.description,
        current_id=new_grv.id
    )

    logger.info(f"Successfully lodged grievance {tracking_id} (AI Priority: {ai_triage_result.priority}) for {new_grv.citizen_name} in IBM Db2.")

    return {
        "success": True,
        "tracking_id": tracking_id,
        "message": f"Grievance registered successfully with tracking number {tracking_id}",
        "ai_triage": {
            "category": ai_triage_result.category,
            "priority": ai_triage_result.priority,
            "summary": ai_triage_result.summary,
            "method": ai_triage_result.method
        },
        "hotspot_alert": hotspot_dup_info.get("hotspot_alert"),
        "potential_duplicates": hotspot_dup_info.get("potential_duplicates"),
        "data": serialize_grievance(new_grv)
    }


@app.get(
    f"{settings.API_PREFIX}/grievances",
    response_model=GrievanceListResponse,
    tags=["Grievances"]
)
def list_grievances(
    category: Optional[str] = Query(None, description="Filter by category (water, electricity, roads, sanitation, health, etc.)"),
    status: Optional[str] = Query(None, description="Filter by status (Filed, Under Review, Forwarded to Dept, Resolved)"),
    priority: Optional[str] = Query(None, description="Filter by priority (Low, Medium, High, Critical)"),
    ward: Optional[str] = Query(None, description="Filter by municipal ward"),
    search: Optional[str] = Query(None, description="Text search in subject, description, or citizen name"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Search and filter grievances stored in IBM Db2 with pagination.
    """
    query = db.query(Grievance)

    if category:
        query = query.filter(Grievance.category.ilike(f"%{category}%"))
    if status:
        query = query.filter(Grievance.status.ilike(f"%{status}%"))
    if priority:
        query = query.filter(Grievance.priority.ilike(f"%{priority}%"))
    if ward:
        query = query.filter(Grievance.ward.ilike(f"%{ward}%"))
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Grievance.subject.ilike(search_pattern),
                Grievance.description.ilike(search_pattern),
                Grievance.citizen_name.ilike(search_pattern),
                Grievance.tracking_id.ilike(search_pattern)
            )
        )

    total = query.count()
    offset = (page - 1) * limit
    items = query.order_by(Grievance.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": math.ceil(total / limit) if total > 0 else 0,
        "items": [serialize_grievance(g) for g in items]
    }


@app.get(
    f"{settings.API_PREFIX}/grievances/{{tracking_id}}",
    tags=["Grievances"]
)
def get_grievance_by_tracking_id(tracking_id: str, db: Session = Depends(get_db)):
    """
    Retrieve full grievance details and timeline history using tracking ID.
    Supports case-insensitive queries (e.g. GRV-2026-4821 or grv-2026-4821).
    """
    normalized_id = tracking_id.strip().upper()
    
    grv = db.query(Grievance).filter(
        or_(
            func.upper(Grievance.tracking_id) == normalized_id,
            func.replace(func.upper(Grievance.tracking_id), '-', '') == normalized_id.replace('-', '')
        )
    ).first()

    if not grv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grievance with tracking ID '{tracking_id}' was not found in IBM Db2."
        )

    return {
        "success": True,
        "data": serialize_grievance(grv)
    }


@app.patch(
    f"{settings.API_PREFIX}/grievances/{{tracking_id}}/status",
    tags=["Grievances"]
)
def update_grievance_status(
    tracking_id: str,
    payload: GrievanceStatusUpdate,
    db: Session = Depends(get_db)
):
    """
    Update grievance status in IBM Db2 and append a row to grievance_updates audit history.
    If resolved, records resolution timestamp.
    """
    normalized_id = tracking_id.strip().upper()

    grv = db.query(Grievance).filter(
        or_(
            func.upper(Grievance.tracking_id) == normalized_id,
            func.replace(func.upper(Grievance.tracking_id), '-', '') == normalized_id.replace('-', '')
        )
    ).first()

    if not grv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grievance with tracking ID '{tracking_id}' was not found in IBM Db2."
        )

    old_status = grv.status
    new_status = payload.status.strip()

    grv.status = new_status
    if payload.priority:
        grv.priority = payload.priority.strip()

    if new_status.lower() == "resolved" and not grv.resolved_at:
        grv.resolved_at = datetime.utcnow()

    # Append new status history row
    history_note = payload.notes or f"Status transitioned from '{old_status}' to '{new_status}'."
    update_row = GrievanceUpdate(
        grievance_id=grv.id,
        previous_status=old_status,
        new_status=new_status,
        notes=history_note,
        updated_by=payload.updated_by or "Officer",
        created_at=datetime.utcnow()
    )
    db.add(update_row)
    db.commit()

    # Note: TRG_AUDIT_STATUS_CHANGE kernel trigger logs the transition atomically in Db2.
    # The application-layer audit row above already captures officer notes.
    # No additional trigger sync needed — the Db2 kernel trigger is the source of truth.

    db.expire_all()
    db.refresh(grv)

    logger.info(f"Grievance {tracking_id} updated: {old_status} -> {new_status} by {payload.updated_by}")

    return {
        "success": True,
        "tracking_id": grv.tracking_id,
        "status": grv.status,
        "message": f"Status updated to '{new_status}' successfully.",
        "data": serialize_grievance(grv)
    }


# ==============================================================================
# Aggregated Analytics & Statistics Endpoint
# ==============================================================================

@app.get(
    f"{settings.API_PREFIX}/stats",
    response_model=StatsResponse,
    tags=["Analytics"]
)
def get_grievance_stats(db: Session = Depends(get_db)):
    """
    Returns real-time grievance redressal metrics aggregated from IBM Db2.
    """
    total = db.query(Grievance).count()

    status_counts = dict(
        db.query(Grievance.status, func.count(Grievance.id))
        .group_by(Grievance.status)
        .all()
    )

    category_counts = dict(
        db.query(Grievance.category, func.count(Grievance.id))
        .group_by(Grievance.category)
        .all()
    )

    priority_counts = dict(
        db.query(Grievance.priority, func.count(Grievance.id))
        .group_by(Grievance.priority)
        .all()
    )

    resolved_count = status_counts.get("Resolved", 0)
    pending_count = total - resolved_count
    rate = round((resolved_count / total * 100), 1) if total > 0 else 0.0

    return {
        "total_grievances": total,
        "status_breakdown": status_counts,
        "category_breakdown": category_counts,
        "priority_breakdown": priority_counts,
        "resolved_count": resolved_count,
        "pending_count": pending_count,
        "resolution_rate": rate
    }


# ==============================================================================
# Feature: IBM Db2 System Catalog Inspector (SYSCAT)
# ==============================================================================

@app.get(
    f"{settings.API_PREFIX}/db2/catalog",
    tags=["IBM Db2 Native Capabilities"]
)
def get_db2_catalog_info(db: Session = Depends(get_db)):
    """
    Queries IBM Db2 System Catalog (SYSCAT) to expose live schema metadata.
    Demonstrates deep Db2 integration via SYSCAT.TABLES, SYSCAT.INDEXES, and SYSCAT.TRIGGERS.
    """
    try:
        # 1. Table statistics from SYSCAT.TABLES
        tables_query = text(
            "SELECT TABNAME, CARD, NPAGES, FPAGES "
            "FROM SYSCAT.TABLES "
            "WHERE TABSCHEMA = CURRENT SCHEMA "
            "ORDER BY TABNAME"
        )
        tables_res = db.execute(tables_query).fetchall()
        tables_info = [
            {
                "table_name": r[0],
                "row_count_estimate": int(r[1]) if r[1] is not None and r[1] >= 0 else "stats_pending",
                "data_pages": int(r[2]) if r[2] is not None and r[2] >= 0 else 0,
                "free_pages": int(r[3]) if r[3] is not None and r[3] >= 0 else 0
            }
            for r in tables_res
        ]

        # 2. Index count per table from SYSCAT.INDEXES
        idx_query = text(
            "SELECT TABNAME, COUNT(*) AS index_count "
            "FROM SYSCAT.INDEXES "
            "WHERE TABSCHEMA = CURRENT SCHEMA "
            "GROUP BY TABNAME "
            "ORDER BY TABNAME"
        )
        idx_res = db.execute(idx_query).fetchall()
        index_info = {r[0]: int(r[1]) for r in idx_res}

        # 3. Active Db2 Triggers from SYSCAT.TRIGGERS
        triggers_query = text(
            "SELECT TRIGNAME, TABNAME, TRIGEVENT, TRIGTIME "
            "FROM SYSCAT.TRIGGERS "
            "WHERE TABSCHEMA = CURRENT SCHEMA "
            "FETCH FIRST 20 ROWS ONLY"
        )
        triggers_res = db.execute(triggers_query).fetchall()
        triggers_info = [
            {
                "trigger_name": r[0],
                "table_name": r[1],
                "event": r[2],
                "timing": r[3]
            }
            for r in triggers_res
        ]

        # 4. Active Stored Procedures from SYSCAT.ROUTINES
        procs_query = text(
            "SELECT ROUTINENAME, ROUTINETYPE "
            "FROM SYSCAT.ROUTINES "
            "WHERE ROUTINESCHEMA = CURRENT SCHEMA "
            "FETCH FIRST 10 ROWS ONLY"
        )
        procs_res = db.execute(procs_query).fetchall()
        procs_info = [{"procedure_name": r[0], "type": r[1]} for r in procs_res]

        # Enrich tables with index count
        for t in tables_info:
            t["index_count"] = index_info.get(t["table_name"], 0)

        return {
            "database": settings.DB2_DATABASE,
            "schema": "CURRENT SCHEMA",
            "tables": tables_info,
            "triggers": triggers_info,
            "stored_procedures": procs_info,
            "catalog_source": "SYSCAT.TABLES / SYSCAT.INDEXES / SYSCAT.TRIGGERS / SYSCAT.ROUTINES"
        }

    except Exception as e:
        logger.error(f"Error querying IBM Db2 SYSCAT: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SYSCAT query error: {str(e)}"
        )


# ==============================================================================
# Feature: "Ask the Data" Natural Language Query Engine (IBM Db2 + LangChain)
# ==============================================================================

@app.post(
    f"{settings.API_PREFIX}/ask",
    response_model=AskQuestionResponse,
    tags=["AI & Natural Language"]
)
def ask_grievance_data(payload: AskQuestionRequest, db: Session = Depends(get_db)):
    """
    'Ask the Data' Natural Language to IBM Db2 SQL Query Engine.
    - Translates plain-English citizen/officer queries into IBM Db2 SQL using LangChain.
    - Strictly enforces security guardrails:
      * Only single SELECT queries permitted.
      * Whitelist tables: departments, grievances, grievance_updates.
      * Rejects INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, semicolons, comments.
      * Enforces Db2 'FETCH FIRST 50 ROWS ONLY' clause.
    - Executes directly against IBM Db2 GRIEVDB and returns both the generated SQL and live rows.
    """
    start_time = datetime.utcnow()
    question = payload.question.strip()

    try:
        sql, method = generate_db2_sql(question)
    except ValueError as ve:
        logger.warning(f"Guardrail rejection on question '{question}': {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        logger.error(f"SQL generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate database query."
        )

    # Execute securely on IBM Db2
    try:
        result_proxy = db.execute(text(sql))
        columns = list(result_proxy.keys())
        raw_rows = result_proxy.fetchall()

        rows = []
        for r in raw_rows:
            row_dict = {}
            for idx, col in enumerate(columns):
                val = r[idx]
                if isinstance(val, datetime):
                    row_dict[col] = val.isoformat()
                elif hasattr(val, '__float__') and not isinstance(val, (int, float)):
                    row_dict[col] = float(val)
                else:
                    row_dict[col] = val
            rows.append(row_dict)

        duration_ms = round((datetime.utcnow() - start_time).total_seconds() * 1000, 2)
        natural_summary = generate_natural_summary(question, sql, rows, len(rows))

        return {
            "question": question,
            "generated_sql": sql,
            "method": method,
            "execution_time_ms": duration_ms,
            "row_count": len(rows),
            "columns": columns,
            "rows": rows,
            "explanation": f"Executed against IBM Db2 database '{settings.DB2_DATABASE}'. Returned {len(rows)} rows in {duration_ms}ms.",
            "natural_summary": natural_summary
        }
    except Exception as e:
        logger.error(f"IBM Db2 execution failure: {e} | Query: {sql}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"IBM Db2 execution error: {str(e)}"
        )


@app.post(
    f"{settings.API_PREFIX}/escalate-overdue",
    tags=["IBM Db2 Native Capabilities"]
)
def run_db2_escalate_stored_procedure(db: Session = Depends(get_db)):
    """
    Executes native IBM Db2 Stored Procedure: SP_ESCALATE_OVERDUE (with SQL fallback).
    Evaluates continuous date arithmetic on Db2 engine: (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15
    Automatically elevates lingering complaints to Critical and returns total escalated count.
    """
    try:
        # Count total overdue (open and not yet Critical)
        pre_count = db.execute(text(
            "SELECT COUNT(*) FROM grievances "
            "WHERE status != 'Resolved' "
            "AND priority != 'Critical' "
            "AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15"
        )).scalar() or 0

        # Count total currently breaching SLA (regardless of priority)
        total_sla_breach = db.execute(text(
            "SELECT COUNT(*) FROM grievances "
            "WHERE status != 'Resolved' "
            "AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15"
        )).scalar() or 0

        # Try native IBM Db2 Stored Procedure first
        escalated_count = 0
        method_used = "sql_fallback"
        try:
            raw_conn = db.connection().connection
            cursor = raw_conn.cursor()
            result_params = cursor.callproc('SP_ESCALATE_OVERDUE', [0])
            # IBM Db2 ibm_db driver returns OUT params in result_params list
            if result_params and len(result_params) > 0:
                escalated_count = int(result_params[0]) if result_params[0] is not None else pre_count
            else:
                escalated_count = pre_count
            cursor.close()
            method_used = "native_stored_procedure"
            logger.info(f"SP_ESCALATE_OVERDUE executed via native callproc. Escalated: {escalated_count}")
        except Exception as sp_err:
            logger.info(f"SP callproc not available ({sp_err}), using direct IBM Db2 SQL escalation.")
            # Direct IBM Db2 date arithmetic UPDATE — semantically identical to SP
            db.execute(text(
                "UPDATE grievances SET priority = 'Critical' "
                "WHERE status != 'Resolved' "
                "AND priority != 'Critical' "
                "AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15"
            ))
            escalated_count = pre_count
            method_used = "db2_sql_date_arithmetic"

        db.commit()

        return {
            "success": True,
            "procedure": "SP_ESCALATE_OVERDUE",
            "escalated_count": escalated_count,
            "total_sla_breach_count": int(total_sla_breach),
            "execution_method": method_used,
            "db2_query_used": "DAYS(CURRENT DATE) - DAYS(DATE(created_at)) > 15",
            "message": (
                f"IBM Db2 SP_ESCALATE_OVERDUE: Elevated {escalated_count} overdue docket(s) to Critical priority. "
                f"Total SLA breaches (open >15 days): {total_sla_breach}. Method: {method_used}."
            )
        }

    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute IBM Db2 escalation: {str(err)}"
        )


# ==============================================================================
# Feature: Advanced Analytics Dashboard (IBM Db2 Date Arithmetic & SLAs)
# ==============================================================================

@app.get(
    f"{settings.API_PREFIX}/analytics",
    response_model=AnalyticsResponse,
    tags=["Analytics"]
)
def get_advanced_analytics(db: Session = Depends(get_db)):
    """
    Returns advanced civic analytics powered by IBM Db2 date arithmetic:
    - Overall resolution rate & average resolution time in days (using Db2 DAYS() arithmetic).
    - SLA breaches: grievances pending > 15 days (DAYS(CURRENT DATE) - DAYS(DATE(created_at)) > 15).
    - Department and Ward distributions.
    - Priority and Category distributions.
    """
    try:
        # 1. Total and status counts
        total = db.query(Grievance).count()
        resolved_count = db.query(Grievance).filter(Grievance.status == "Resolved").count()
        pending_count = total - resolved_count
        rate = round((resolved_count / total * 100), 2) if total > 0 else 0.0

        # 2. Average resolution time in days using Db2 date arithmetic
        avg_days_query = text(
            "SELECT AVG(CAST(DAYS(DATE(resolved_at)) - DAYS(DATE(created_at)) AS FLOAT)) "
            "FROM grievances WHERE resolved_at IS NOT NULL"
        )
        avg_res_val = db.execute(avg_days_query).scalar()
        avg_resolution_days = round(float(avg_res_val), 1) if avg_res_val is not None else 0.0

        # 3. SLA Breaches: open > 15 days using Db2 date arithmetic
        sla_count_query = text(
            "SELECT COUNT(*) FROM grievances "
            "WHERE status != 'Resolved' AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15"
        )
        sla_breaches_count = db.execute(sla_count_query).scalar() or 0

        # 4. Detailed SLA breached dockets
        sla_dockets_query = text(
            "SELECT tracking_id, citizen_name, category, ward, priority, status, created_at, "
            "(DAYS(CURRENT DATE) - DAYS(DATE(created_at))) AS days_open "
            "FROM grievances "
            "WHERE status != 'Resolved' AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15 "
            "ORDER BY days_open DESC "
            "FETCH FIRST 50 ROWS ONLY"
        )
        sla_cursor = db.execute(sla_dockets_query)
        sla_dockets = []
        for r in sla_cursor.fetchall():
            sla_dockets.append({
                "tracking_id": r[0],
                "citizen_name": r[1],
                "category": r[2],
                "ward": r[3],
                "priority": r[4],
                "status": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
                "days_open": int(r[7]) if r[7] is not None else 0
            })

        # 5. Department breakdown
        dept_query = text(
            "SELECT COALESCE(d.name, g.category) AS dept_name, COUNT(g.id) AS total "
            "FROM grievances g LEFT JOIN departments d ON g.department_id = d.id "
            "GROUP BY COALESCE(d.name, g.category) "
            "ORDER BY total DESC "
            "FETCH FIRST 20 ROWS ONLY"
        )
        dept_cursor = db.execute(dept_query)
        department_breakdown = [{"department": r[0], "count": int(r[1])} for r in dept_cursor.fetchall()]

        # 6. Ward breakdown
        ward_query = text(
            "SELECT ward, COUNT(*) AS total "
            "FROM grievances "
            "GROUP BY ward "
            "ORDER BY total DESC "
            "FETCH FIRST 20 ROWS ONLY"
        )
        ward_cursor = db.execute(ward_query)
        ward_breakdown = [{"ward": r[0], "count": int(r[1])} for r in ward_cursor.fetchall()]

        # 7. Priority breakdown
        priority_query = text("SELECT priority, COUNT(*) FROM grievances GROUP BY priority")
        priority_cursor = db.execute(priority_query)
        priority_breakdown = {str(r[0]): int(r[1]) for r in priority_cursor.fetchall()}

        # 8. Category breakdown
        category_query = text("SELECT category, COUNT(*) FROM grievances GROUP BY category")
        category_cursor = db.execute(category_query)
        category_breakdown = {str(r[0]): int(r[1]) for r in category_cursor.fetchall()}

        return {
            "total_grievances": total,
            "resolved_count": resolved_count,
            "pending_count": pending_count,
            "resolution_rate": rate,
            "avg_resolution_days": avg_resolution_days,
            "sla_breaches_count": sla_breaches_count,
            "sla_breached_dockets": sla_dockets,
            "department_breakdown": department_breakdown,
            "ward_breakdown": ward_breakdown,
            "priority_breakdown": priority_breakdown,
            "category_breakdown": category_breakdown
        }
    except Exception as e:
        logger.error(f"Error computing IBM Db2 analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error computing Db2 analytics: {str(e)}"
        )


DELHI_WARD_COORDINATES: Dict[str, Dict[str, float]] = {
    "Ward 01 - Civil Lines": {"lat": 28.6811, "lng": 77.2228},
    "Ward 04 - Timarpur": {"lat": 28.7011, "lng": 77.2185},
    "Ward 07 - Chandni Chowk": {"lat": 28.6506, "lng": 77.2303},
    "Ward 12 - Karol Bagh": {"lat": 28.6550, "lng": 77.1912},
    "Ward 14 - Rohini East": {"lat": 28.7150, "lng": 77.1200},
    "Ward 18 - Pitampura": {"lat": 28.6990, "lng": 77.1384},
    "Ward 18 - Vasant Kunj": {"lat": 28.5244, "lng": 77.1558},
    "Ward 22 - Connaught Place": {"lat": 28.6328, "lng": 77.2197},
    "Ward 28 - Patel Nagar": {"lat": 28.6577, "lng": 77.1654},
    "Ward 35 - Mayur Vihar Phase 1": {"lat": 28.6083, "lng": 77.2964},
    "Ward 42 - Hauz Khas": {"lat": 28.5494, "lng": 77.2001},
    "Ward 49 - Greater Kailash": {"lat": 28.5367, "lng": 77.2410},
    "Ward 53 - Lajpat Nagar": {"lat": 28.5677, "lng": 77.2433},
    "Ward 58 - Dwarka Sector 6": {"lat": 28.5921, "lng": 77.0648},
    "Ward 62 - Janakpuri West": {"lat": 28.6297, "lng": 77.0818},
    "Ward 67 - Okhla Industrial Area": {"lat": 28.5307, "lng": 77.2711},
    "Ward 72 - Shahdara North": {"lat": 28.6738, "lng": 77.2917},
    "Ward 80 - Mehrauli": {"lat": 28.5177, "lng": 77.1856},
    "Ward 85 - Najafgarh": {"lat": 28.6092, "lng": 76.9798},
}


@app.get(
    f"{settings.API_PREFIX}/analytics/geo-hotspots",
    response_model=GeoHotspotsResponse,
    tags=["Analytics", "GIS"]
)
def get_geo_hotspots(db: Session = Depends(get_db)):
    """
    Municipal Ward Geospatial Command Map Endpoint:
    Aggregates open grievances by ward in IBM Db2, returning:
    - Geo-coordinates (lat, lng) accurately mapped across Delhi NCT
    - Open dockets volume (total_cases)
    - Critical severity volume (critical_cases)
    - SLA breaches (sla_breaches, open > 15 days using Db2 date math)
    - Hotspot classification (is_hotspot: total_cases > 3)
    - Primary civic category per ward
    - GeoJSON FeatureCollection format for GIS mapping clients (Leaflet.js)
    """
    try:
        # 1. Aggregate ward statistics for open dockets using native Db2 date arithmetic
        ward_sql = text("""
            SELECT 
                g.ward,
                COUNT(*) AS total_cases,
                SUM(CASE WHEN g.priority = 'Critical' THEN 1 ELSE 0 END) AS critical_cases,
                SUM(CASE WHEN (DAYS(CURRENT DATE) - DAYS(DATE(g.created_at))) > 15 THEN 1 ELSE 0 END) AS sla_breaches,
                AVG(g.latitude) AS avg_lat,
                AVG(g.longitude) AS avg_lng
            FROM grievances g
            WHERE g.status != 'Resolved'
            GROUP BY g.ward
            ORDER BY total_cases DESC
        """)
        ward_rows = db.execute(ward_sql).fetchall()

        # 2. Get dominant/primary category per ward in open dockets
        cat_sql = text("""
            SELECT ward, category, COUNT(*) as cnt 
            FROM grievances 
            WHERE status != 'Resolved' 
            GROUP BY ward, category 
            ORDER BY ward, cnt DESC
        """)
        cat_rows = db.execute(cat_sql).fetchall()
        ward_primary_cat = {}
        for w, c, _ in cat_rows:
            if w and w not in ward_primary_cat:
                ward_primary_cat[w] = c

        results = []
        for r in ward_rows:
            ward_name = str(r[0]) if r[0] else "Unassigned Ward"
            total_cases = int(r[1]) if r[1] is not None else 0
            critical_cases = int(r[2]) if r[2] is not None else 0
            sla_breaches = int(r[3]) if r[3] is not None else 0
            
            # Use average lat/lng from records if valid, otherwise lookup Delhi ward coordinate
            fallback_coords = DELHI_WARD_COORDINATES.get(ward_name, {"lat": 28.6139, "lng": 77.2090})
            lat = round(float(r[4]), 4) if (r[4] is not None and float(r[4]) != 0.0) else fallback_coords["lat"]
            lng = round(float(r[5]), 4) if (r[5] is not None and float(r[5]) != 0.0) else fallback_coords["lng"]

            # Hotspot criteria: >3 open complaints
            is_hotspot = total_cases > 3
            primary_cat = ward_primary_cat.get(ward_name, "general")

            results.append({
                "ward": ward_name,
                "lat": lat,
                "lng": lng,
                "total_cases": total_cases,
                "critical_cases": critical_cases,
                "sla_breaches": sla_breaches,
                "is_hotspot": is_hotspot,
                "primary_category": primary_cat
            })

        # GeoJSON representation for standard GIS consumers
        geojson_features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [w["lng"], w["lat"]]
                },
                "properties": w
            }
            for w in results
        ]
        geojson = {
            "type": "FeatureCollection",
            "features": geojson_features
        }

        hotspots_count = sum(1 for w in results if w["is_hotspot"])

        return {
            "success": True,
            "total_wards": len(results),
            "hotspots_count": hotspots_count,
            "wards": results,
            "geojson": geojson
        }
    except Exception as e:
        logger.error(f"Error fetching geo hotspots: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate ward geo hotspots: {str(e)}"
        )


# ==============================================================================
# Feature: Officer Redressal Console & LangChain AI Action Drafter
# ==============================================================================

@app.get(
    f"{settings.API_PREFIX}/officer/dockets",
    response_model=List[OfficerDocketOut],
    tags=["Officer Console"]
)
def get_officer_dockets(
    department: Optional[str] = Query(None, description="Department code or category filter"),
    status: Optional[str] = Query(None, description="Filter status (default: open tickets)"),
    priority: Optional[str] = Query(None, description="Filter priority (Critical, High, Medium, Low)"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Officer Redressal Console docket list.
    Queries IBM Db2 with computed days_open (using native Db2 date arithmetic),
    enriched with department details and SLA breach indicators.
    """
    days_expr = (func.days(func.current_date()) - func.days(func.date(Grievance.created_at))).label("days_open")
    query = db.query(Grievance, days_expr).outerjoin(Department, Grievance.department_id == Department.id)

    # Status filtering (default to active/open dockets)
    if not status or status.lower() == "open":
        query = query.filter(Grievance.status.in_(["Filed", "Under Review", "Forwarded to Dept"]))
    elif status.lower() != "all":
        query = query.filter(Grievance.status.ilike(f"%{status}%"))

    # Department filtering
    if department and department.lower() != "all":
        dept_term = department.strip().lower()
        query = query.filter(
            or_(
                Grievance.category.ilike(f"%{dept_term}%"),
                Department.code.ilike(f"%{dept_term}%"),
                Department.name.ilike(f"%{dept_term}%")
            )
        )

    # Priority filtering
    if priority and priority.lower() != "all":
        query = query.filter(Grievance.priority.ilike(f"%{priority}%"))

    # Order by longest open first (urgency queue)
    results = query.order_by(days_expr.desc(), Grievance.created_at.asc()).limit(limit).all()

    dockets = []
    for grv, days_val in results:
        days_int = int(days_val) if days_val is not None else 0
        dept_name = grv.department.name if grv.department else None
        dockets.append({
            "id": grv.id,
            "tracking_id": grv.tracking_id,
            "citizen_name": grv.citizen_name,
            "contact": grv.contact,
            "category": grv.category,
            "subject": grv.subject,
            "description": grv.description,
            "ward": grv.ward,
            "priority": grv.priority,
            "status": grv.status,
            "created_at": grv.created_at,
            "days_open": days_int,
            "is_sla_breached": days_int > 15 and grv.status != "Resolved",
            "department_id": grv.department_id,
            "department_name": dept_name,
            "ai_category": getattr(grv, "ai_category", None),
            "ai_priority": getattr(grv, "ai_priority", None),
            "ai_summary": getattr(grv, "ai_summary", None)
        })

    return dockets


@app.post(
    f"{settings.API_PREFIX}/officer/draft-action",
    response_model=DraftActionResponse,
    tags=["Officer Console"]
)
def draft_officer_action(payload: DraftActionRequest, db: Session = Depends(get_db)):
    """
    Officer AI Action Drafter powered by LangChain.
    Loads grievance from IBM Db2 and drafts a formal administrative notice / compliance directive.
    """
    normalized_id = payload.tracking_id.strip().upper()
    days_expr = (func.days(func.current_date()) - func.days(func.date(Grievance.created_at))).label("days_open")

    result = db.query(Grievance, days_expr).filter(
        or_(
            func.upper(Grievance.tracking_id) == normalized_id,
            func.replace(func.upper(Grievance.tracking_id), '-', '') == normalized_id.replace('-', '')
        )
    ).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grievance docket '{payload.tracking_id}' was not found in IBM Db2."
        )

    grv, days_val = result
    days_int = int(days_val) if days_val is not None else 1

    grievance_data = {
        "tracking_id": grv.tracking_id,
        "citizen_name": grv.citizen_name,
        "category": grv.category,
        "priority": grv.priority,
        "subject": grv.subject or grv.description[:80],
        "description": grv.description,
        "ward": grv.ward or "Municipal Ward",
        "days_open": days_int
    }

    # Run LangChain Action Drafter Chain
    drafted_result = draft_officer_action_order(grievance_data)

    return {
        "tracking_id": grv.tracking_id,
        "action_type": drafted_result.get("action_type", "Field Inspection"),
        "target_officer": drafted_result.get("target_officer", "Zonal Assistant Engineer"),
        "statutory_deadline_days": drafted_result.get("statutory_deadline_days", 3),
        "drafted_order_text": drafted_result.get("drafted_order_text", ""),
        "recommended_status": drafted_result.get("recommended_status", "Forwarded to Dept"),
        "generated_by": drafted_result.get("generated_by", "LangChain Action Drafter")
    }


@app.post(
    f"{settings.API_PREFIX}/officer/resolve",
    tags=["Officer Console"]
)
def resolve_officer_docket(payload: ResolveDocketRequest, db: Session = Depends(get_db)):
    """
    Officer Quick Resolve action.
    Executes an atomic IBM Db2 transaction:
    - Marks grievance status as 'Resolved'
    - Records resolved_at timestamp
    - Updates ai_summary with officer resolution summary
    - Inserts full Action Taken Report (ATR) note into grievance_updates audit table
    """
    normalized_id = payload.tracking_id.strip().upper()

    grv = db.query(Grievance).filter(
        or_(
            func.upper(Grievance.tracking_id) == normalized_id,
            func.replace(func.upper(Grievance.tracking_id), '-', '') == normalized_id.replace('-', '')
        )
    ).first()

    if not grv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Grievance docket '{payload.tracking_id}' was not found in IBM Db2."
        )

    old_status = grv.status
    now = datetime.utcnow()

    grv.status = "Resolved"
    grv.resolved_at = now
    grv.ai_summary = payload.resolution_summary.strip()

    # Create detailed audit history entry
    update_row = GrievanceUpdate(
        grievance_id=grv.id,
        previous_status=old_status,
        new_status="Resolved",
        notes=payload.officer_notes.strip(),
        updated_by=payload.officer_name.strip() or "Executive Nodal Officer",
        created_at=now
    )
    db.add(update_row)
    db.commit()

    # TRG_AUDIT_STATUS_CHANGE kernel trigger has already logged the Resolved transition atomically.
    # The application audit row above captures officer ATR notes — no double-write needed.

    db.expire_all()
    db.refresh(grv)

    logger.info(f"Docket {grv.tracking_id} successfully resolved in IBM Db2 by {payload.officer_name}.")

    return {
        "success": True,
        "tracking_id": grv.tracking_id,
        "status": "Resolved",
        "message": f"Docket {grv.tracking_id} has been formally resolved and archived with audit trail.",
        "data": serialize_grievance(grv)
    }


# ==============================================================================
# Feature 4: Agentic Tool-Calling for CPGRAMS Sahayak Assistant
# ==============================================================================

@app.post(
    f"{settings.API_PREFIX}/sahayak/chat",
    response_model=SahayakChatResponse,
    tags=["Agentic AI Assistant"]
)
def sahayak_agent_chat(payload: SahayakChatRequest, db: Session = Depends(get_db)):
    """
    CPGRAMS Sahayak Agentic Tool-Calling Endpoint:
    Processes user messages in Hindi or English, dynamically determining and executing
    native tools connected to IBM Db2 (docket tracking, municipal ward telemetry,
    or Citizen Charter knowledge base).
    """
    try:
        agent_result = run_sahayak_agent(
            message=payload.message,
            db=db,
            language=payload.language or "en"
        )
        return {
            "reply": agent_result["reply"],
            "tool_used": agent_result.get("tool_used"),
            "data_payload": agent_result.get("data_payload"),
            "session_id": payload.session_id
        }
    except Exception as e:
        logger.error(f"Error in Sahayak Agent execution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sahayak Agent execution error: {str(e)}"
        )


# ==============================================================================
# Feature: CSV Data Export Endpoint
# ==============================================================================

@app.get(
    f"{settings.API_PREFIX}/export/csv",
    tags=["Data Export"]
)
def export_grievances_csv(
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    sla_breached: Optional[bool] = Query(None, description="If true, only export SLA-breached grievances"),
    db: Session = Depends(get_db)
):
    """
    Export grievances from IBM Db2 as a CSV file.
    Supports filtering by status, category, priority, and SLA breach status.
    """
    try:
        if sla_breached:
            sql = text(
                "SELECT tracking_id, citizen_name, contact, category, subject, ward, priority, status, "
                "created_at, resolved_at, ai_priority, ai_summary, "
                "(DAYS(CURRENT DATE) - DAYS(DATE(created_at))) AS days_open "
                "FROM grievances "
                "WHERE status != 'Resolved' "
                "AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15 "
                "ORDER BY days_open DESC "
                "FETCH FIRST 500 ROWS ONLY"
            )
            rows = db.execute(sql).fetchall()
            columns = ["tracking_id", "citizen_name", "contact", "category", "subject", "ward",
                      "priority", "status", "created_at", "resolved_at", "ai_priority", "ai_summary", "days_open"]
        else:
            query = db.query(Grievance)
            if status_filter:
                query = query.filter(Grievance.status.ilike(f"%{status_filter}%"))
            if category:
                query = query.filter(Grievance.category.ilike(f"%{category}%"))
            if priority:
                query = query.filter(Grievance.priority.ilike(f"%{priority}%"))
            items = query.order_by(Grievance.created_at.desc()).limit(500).all()
            rows = [(
                g.tracking_id, g.citizen_name, g.contact, g.category, g.subject,
                g.ward, g.priority, g.status,
                g.created_at.isoformat() if g.created_at else "",
                g.resolved_at.isoformat() if g.resolved_at else "",
                getattr(g, "ai_priority", ""), getattr(g, "ai_summary", "")
            ) for g in items]
            columns = ["tracking_id", "citizen_name", "contact", "category", "subject",
                      "ward", "priority", "status", "created_at", "resolved_at", "ai_priority", "ai_summary"]

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([str(v) if v is not None else "" for v in row])

        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=cpgrams_export.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV export error: {str(e)}")
