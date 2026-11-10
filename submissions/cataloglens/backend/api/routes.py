"""
CatalogLens FastAPI REST API Routes.
Exposes clean, documented endpoints for schema exploration,
relationship discovery, AI understanding, workflow analysis, and dependency tracing.
"""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..db.connection import Db2ConnectionManager
from ..db.metadata_extractor import MetadataExtractor
from ..models.schema import DbSchemaMetadata, DbTable
from ..models.relationship import RelationshipEdge
from ..models.analysis import TableUnderstanding, WorkflowGroup, DependencyInvestigation
from ..services.relationship_detector import RelationshipDetector
from ..services.dependency_analyzer import DependencyAnalyzer
from ..services.workflow_detector import WorkflowDetector
from ..graph.investigation_graph import create_investigation_graph

router = APIRouter()


# Request Models
class ConnectionTestRequest(BaseModel):
    host: str = "localhost"
    port: int = 50000
    database: str = "SAMPLE"
    username: str = "db2inst1"
    password: str = ""
    security: str = ""


class AnalyzeTableRequest(BaseModel):
    table_name: str
    schema_name: str = "ENTERPRISE"
    question: Optional[str] = None
    use_demo: bool = True
    force_refresh: bool = False


class AnalyzeWorkflowRequest(BaseModel):
    schema_name: str = "ENTERPRISE"
    use_demo: bool = True


class InvestigateDependenciesRequest(BaseModel):
    target_object: str  # e.g., "ORD_HDR" or "ORD_HDR.CUSTOMER_ID"
    schema_name: str = "ENTERPRISE"
    use_demo: bool = True


# Response Models
class HealthResponse(BaseModel):
    status: str
    version: str
    ibm_db_driver_installed: bool
    anthropic_configured: bool
    anthropic_model: str
    demo_mode: bool


# --- Endpoints ---

@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Returns application health and driver/API configuration status."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        ibm_db_driver_installed=Db2ConnectionManager.is_driver_available(),
        anthropic_configured=settings.has_anthropic_key(),
        anthropic_model=settings.anthropic_model,
        demo_mode=settings.demo_mode,
    )


@router.post("/connection/test", tags=["Db2 Connection"])
def test_connection(req: ConnectionTestRequest):
    """
    Attempts a real connection test to IBM Db2.
    Does not report success unless query execution actually succeeds.
    """
    mgr = Db2ConnectionManager(
        host=req.host,
        port=req.port,
        database=req.database,
        username=req.username,
        password=req.password,
        security=req.security,
    )
    result = mgr.test_connection()
    return result


@router.get("/schemas", response_model=List[str], tags=["Catalog Metadata"])
def get_schemas(use_demo: bool = Query(True, description="Whether to query demo dataset")):
    """Returns available database schemas."""
    extractor = MetadataExtractor()
    return extractor.list_schemas(use_demo=use_demo)


@router.get("/metadata", response_model=DbSchemaMetadata, tags=["Catalog Metadata"])
def get_metadata(
    schema_name: str = Query("ENTERPRISE", description="Target Db2 schema"),
    use_demo: bool = Query(True, description="Whether to query demo dataset"),
):
    """Retrieves full catalog metadata for the specified schema."""
    extractor = MetadataExtractor()
    return extractor.extract_schema_metadata(schema_name=schema_name, use_demo=use_demo)


@router.get("/tables", response_model=List[Dict[str, Any]], tags=["Catalog Metadata"])
def list_tables(
    schema_name: str = Query("ENTERPRISE", description="Target Db2 schema"),
    use_demo: bool = Query(True, description="Whether to query demo dataset"),
):
    """Returns summarized list of tables and views."""
    extractor = MetadataExtractor()
    meta = extractor.extract_schema_metadata(schema_name=schema_name, use_demo=use_demo)
    summary = []
    for tabname, tobj in meta.tables.items():
        summary.append({
            "name": tabname,
            "type": "TABLE",
            "columns_count": len(tobj.columns),
            "primary_keys": tobj.primary_keys,
            "foreign_keys_count": len(tobj.foreign_keys),
            "cardinality": tobj.card,
            "remarks": tobj.remarks,
        })
    for vname, vobj in meta.views.items():
        summary.append({
            "name": vname,
            "type": "VIEW",
            "columns_count": len(vobj.columns),
            "primary_keys": [],
            "foreign_keys_count": 0,
            "cardinality": vobj.card,
            "remarks": vobj.remarks,
        })
    return summary


@router.get("/tables/{table_name}", response_model=DbTable, tags=["Catalog Metadata"])
def get_table_details(
    table_name: str,
    schema_name: str = Query("ENTERPRISE", description="Target Db2 schema"),
    use_demo: bool = Query(True, description="Whether to query demo dataset"),
):
    """Retrieves complete structural definition for a single table or view."""
    extractor = MetadataExtractor()
    meta = extractor.extract_schema_metadata(schema_name=schema_name, use_demo=use_demo)
    obj = meta.get_object(table_name)
    if not obj:
        raise HTTPException(status_code=404, detail=f"Table or view '{table_name}' not found.")
    return obj


@router.get("/relationships", response_model=List[RelationshipEdge], tags=["Intelligence"])
def get_relationships(
    schema_name: str = Query("ENTERPRISE", description="Target Db2 schema"),
    use_demo: bool = Query(True, description="Whether to query demo dataset"),
):
    """Discovers declared and inferred foreign key relationships."""
    extractor = MetadataExtractor()
    meta = extractor.extract_schema_metadata(schema_name=schema_name, use_demo=use_demo)
    detector = RelationshipDetector()
    return detector.discover_relationships(meta)


@router.post("/analyze/table", tags=["Intelligence"])
def analyze_table(req: AnalyzeTableRequest):
    """
    Runs the agentic LangGraph investigation pipeline on the selected table.
    Performs metadata retrieval, schema analysis, relationship investigation,
    Claude reasoning, and programmatic evidence validation.
    """
    graph = create_investigation_graph()
    initial_state = {
        "schema_name": req.schema_name,
        "selected_table": req.table_name,
        "investigation_question": req.question,
        "use_demo": req.use_demo,
        "metadata": None,
        "declared_relationships": [],
        "inferred_relationships": [],
        "table_evidence_ledger": [],
        "ai_understanding": None,
        "validated_evidence": [],
        "discrepancies": [],
        "final_report": None,
        "errors": [],
    }

    final_state = graph.invoke(initial_state)

    if final_state.get("errors"):
        raise HTTPException(status_code=400, detail="; ".join(final_state["errors"]))

    return final_state.get("final_report", {})


@router.post("/analyze/workflow", response_model=List[WorkflowGroup], tags=["Intelligence"])
def analyze_workflows(req: AnalyzeWorkflowRequest):
    """Discovers business workflows from clusters of connected tables."""
    extractor = MetadataExtractor()
    meta = extractor.extract_schema_metadata(schema_name=req.schema_name, use_demo=req.use_demo)
    detector = RelationshipDetector()
    rels = detector.discover_relationships(meta)
    wf_detector = WorkflowDetector()
    return wf_detector.discover_workflows(meta, rels)


@router.post("/investigate/dependencies", response_model=DependencyInvestigation, tags=["Intelligence"])
def investigate_dependencies(req: InvestigateDependenciesRequest):
    """
    Performs impact and dependency analysis on an object (e.g. 'ORD_HDR' or 'ORD_HDR.CUSTOMER_ID').
    """
    extractor = MetadataExtractor()
    meta = extractor.extract_schema_metadata(schema_name=req.schema_name, use_demo=req.use_demo)
    detector = RelationshipDetector()
    rels = detector.discover_relationships(meta)
    analyzer = DependencyAnalyzer(meta, rels)
    return analyzer.investigate(req.target_object)
