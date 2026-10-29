"""FastAPI Router for IBM Db2 AI & Analytics Toolkit.

Exposes REST API endpoints for:
- Database health and driver mode
- Transpiling SQL to Db2 LUW syntax
- Natural language Text-to-SQL execution
- Semantic RAG vector retrieval
- Autonomous CrewAI risk audits
- Langflow visual flow templates
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from db2_toolkit.connection import get_db2_pool
from db2_toolkit.crewai_agents import Db2Crew
from db2_toolkit.dialect_transpiler import Db2DialectTranspiler
from db2_toolkit.langchain_agent import Db2TextToSqlAgent, Db2VectorStore
from db2_toolkit.langflow_components import Db2LangflowBuilder

router = APIRouter(prefix="/api/v1/db2", tags=["IBM Db2 AI & Analytics Toolkit"])


# ── Pydantic Request / Response Models ────────────────────────────────────────

class TranspileRequest(BaseModel):
    sql: str = Field(..., description="Source SQL query to transpile")
    source_dialect: str = Field(default="postgres", description="Source SQL dialect (postgres, sqlite, mysql)")


class TranspileResponse(BaseModel):
    original_sql: str
    transpiled_sql: str
    source_dialect: str
    target_dialect: str
    rules_applied: List[str]


class QueryRequest(BaseModel):
    sql: Optional[str] = Field(default=None, description="Direct SQL query to execute")
    question: Optional[str] = Field(default=None, description="Natural language question to translate to SQL")
    params: Optional[List[Any]] = Field(default=None, description="Optional parameterized bind variables")


class RagSearchRequest(BaseModel):
    query: str = Field(..., description="Search query string")
    top_k: int = Field(default=3, description="Number of top documents to retrieve")


class CrewAuditRequest(BaseModel):
    symbol: str = Field(default="AAPL", description="Asset ticker symbol to audit")
    alpha: float = Field(default=0.05, description="Significance level for conformal prediction (1 - alpha coverage)")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/health")
def get_db2_health() -> Dict[str, Any]:
    """Checks the health and connectivity of IBM Db2 or active MockDb2Sandbox."""
    pool = get_db2_pool()
    return pool.ping()


@router.get("/schema")
def get_db2_schema() -> Dict[str, Any]:
    """Inspects all tables and schema definitions in the Db2 instance."""
    agent = Db2TextToSqlAgent()
    return {"tables": agent.inspect_schema()}


@router.post("/transpile", response_model=TranspileResponse)
def transpile_sql(req: TranspileRequest) -> TranspileResponse:
    """Transpiles a query from PostgreSQL/SQLite/MySQL into valid IBM Db2 syntax."""
    transpiler = Db2DialectTranspiler(default_source_dialect=req.source_dialect)
    res = transpiler.transpile(req.sql, req.source_dialect)
    return TranspileResponse(
        original_sql=res.original_sql,
        transpiled_sql=res.transpiled_sql,
        source_dialect=res.source_dialect,
        target_dialect=res.target_dialect,
        rules_applied=res.rules_applied,
    )


@router.post("/query")
def execute_query(req: QueryRequest) -> Dict[str, Any]:
    """Executes a direct SQL statement or runs a natural language Text-to-SQL pipeline."""
    pool = get_db2_pool()

    if req.question:
        agent = Db2TextToSqlAgent(connection_manager=pool)
        return agent.run(req.question)

    if req.sql:
        try:
            transpiler = Db2DialectTranspiler()
            clean_sql = transpiler.transpile(req.sql).transpiled_sql
            results = pool.execute_query(clean_sql, req.params)
            return {
                "executed_sql": clean_sql,
                "row_count": len(results),
                "data": results,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Db2 query execution failed: {exc}")

    raise HTTPException(status_code=400, detail="Either 'sql' or 'question' must be provided.")


@router.post("/rag/search")
def search_rag_documents(req: RagSearchRequest) -> Dict[str, Any]:
    """Performs semantic vector search across financial documents stored in IBM Db2."""
    store = Db2VectorStore()
    results = store.similarity_search(req.query, k=req.top_k)
    return {
        "query": req.query,
        "count": len(results),
        "results": [
            {
                "id": doc.id,
                "content": doc.page_content,
                "score": round(score, 4),
                "metadata": doc.metadata,
            }
            for doc, score in results
        ],
    }


@router.post("/crew/audit")
def run_crew_audit(req: CrewAuditRequest) -> Dict[str, Any]:
    """Triggers autonomous CrewAI multi-agent risk evaluation over Db2 market & conformal data."""
    crew = Db2Crew()
    return crew.run_risk_audit(symbol=req.symbol, alpha=req.alpha)


@router.get("/langflow/flow")
def export_langflow_template() -> Dict[str, Any]:
    """Exports reusable Langflow visual flow JSON for IBM Db2 pipelines."""
    builder = Db2LangflowBuilder()
    return builder.export_flow_dict()

