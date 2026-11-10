"""
CrewAI agent definitions and crew orchestration.

IMPORTANT: Agents can propose and plan, but NEVER execute.
Execution requires human approval through the API.

Safety principle: Agents propose, humans approve, code executes.

Note: CrewAI is optional — if unavailable, only the tool functions work (no orchestration).
"""
import json
from typing import Any

# Try importing CrewAI — fallback gracefully if unavailable
try:
    from crewai import Agent, Crew, Task
    from crewai.tools import tool
    CREWAI_AVAILABLE = True
except ImportError:
    print("[agents] crewai not available — agent orchestration disabled (direct tools still work)")
    CREWAI_AVAILABLE = False
    # Mock decorator so @tool syntax doesn't fail
    def tool(name=None):  # type: ignore[misc]
        def decorator(func):
            return func
        return decorator if name else decorator
    Agent = Crew = Task = None  # type: ignore[misc,assignment]

from app import classify, discovery, erasure
from app.config import settings


# Tool definitions (agents can only observe and plan, not execute)

@tool("scan_catalog")
def scan_catalog(schema: str) -> str:
    """
    Scan database schema and discover tables, columns, and foreign keys.
    
    Returns metadata only - never returns actual data values.
    
    Args:
        schema: Database schema name (e.g., 'DB2INST1')
        
    Returns:
        JSON string with tables, columns, and FK relationships
    """
    try:
        summary = discovery.summary(schema)
        return json.dumps(summary, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("classify_columns")
def classify_columns_tool(schema: str) -> str:
    """
    Classify columns as PII or not using value rules and name similarity.
    
    Returns labels and confidences - NEVER returns actual data values.
    
    Args:
        schema: Database schema name
        
    Returns:
        JSON string with classification results
    """
    try:
        results = classify.run(schema)
        
        # Return summary only (no PII values)
        summary = {
            "total_columns": len(results),
            "pii_columns": sum(1 for r in results if r.label != "NOT_PII"),
            "needs_review": sum(1 for r in results if r.needs_review),
            "by_label": {},
        }
        
        for result in results:
            if result.label not in summary["by_label"]:
                summary["by_label"][result.label] = []
            
            summary["by_label"][result.label].append({
                "table": result.table,
                "column": result.column,
                "confidence": result.confidence,
                "method": result.method,
                "needs_review": result.needs_review,
            })
        
        return json.dumps(summary, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("build_erasure_plan")
def build_erasure_plan_tool(subject_id: int, schema: str = None) -> str:
    """
    Build a DRY-RUN erasure plan for a subject.
    
    IMPORTANT: This tool DOES NOT execute anything.
    It only plans what would happen.
    
    Args:
        subject_id: Subject ID (e.g., patient ID)
        schema: Database schema (optional, defaults to config)
        
    Returns:
        JSON string with plan steps and statistics
    """
    try:
        if schema is None:
            schema = settings.db2_schema
        
        steps = erasure.plan(subject_id, schema)
        sim = erasure.simulate(steps)
        
        plan_data = {
            "subject_id": subject_id,
            "plan_hash": erasure.plan_hash(steps),
            "simulation": sim,
            "steps": [
                {
                    "table": s.table,
                    "action": s.action,
                    "reason": s.reason,
                    "est_rows": s.est_rows,
                    "rule_verified": s.rule_verified,
                    "has_sql": s.sql is not None,
                }
                for s in steps
            ],
        }
        
        return json.dumps(plan_data, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# NOTE: There is deliberately NO execute_erasure tool
# Execution happens only through authenticated API with approval


# Agent definitions (only if CrewAI is available)
if CREWAI_AVAILABLE:
    discovery_agent = Agent(
        role="Data Discovery Analyst",
        goal="Map where personal data lives in the database and identify relationships",
        backstory="""You are a meticulous data analyst who examines database schemas 
        to understand data relationships. You never guess - when uncertain, you flag 
        items for human review. You understand foreign keys, referential integrity, 
        and safe deletion order.""",
        tools=[scan_catalog],
        allow_delegation=False,
        verbose=True,
    )

    classification_agent = Agent(
        role="PII Classification Specialist",
        goal="Identify and classify personal data with high accuracy",
        backstory="""You are a privacy expert who identifies personal data using 
        pattern matching and semantic analysis. You understand PII types like email, 
        phone, Aadhaar, PAN, health data, and more. You flag uncertain cases for 
        human review and never overstate confidence.""",
        tools=[classify_columns_tool],
        allow_delegation=False,
        verbose=True,
    )

    rights_agent = Agent(
        role="Rights Request Officer",
        goal="Draft safe, reviewable erasure plans that respect retention rules",
        backstory="""You are a compliance officer who handles data subject rights 
        requests. You follow retention rules strictly, explain every exception, and 
        always present plans for human approval before any action. You understand 
        that some data must be retained for legal compliance.""",
        tools=[build_erasure_plan_tool],
        allow_delegation=False,
        verbose=True,
    )
else:
    discovery_agent = classification_agent = rights_agent = None  # type: ignore[assignment]


# Crew definitions for common workflows

def create_discovery_crew(schema: str):  # type: ignore[misc]
    """
    Create a crew for schema discovery and classification.
    
    Args:
        schema: Database schema to analyze
        
    Returns:
        Configured Crew instance
    """
    if not CREWAI_AVAILABLE:
        raise RuntimeError("CrewAI not available — install with: pip install crewai")
    
    tasks = [
        Task(
            description=f"Scan and map the schema '{schema}'. List all tables, columns, and foreign key relationships.",
            agent=discovery_agent,
            expected_output="Complete schema map with tables, columns, and FK relationships",
        ),
        Task(
            description=f"Classify columns in schema '{schema}' as PII or not. Flag uncertain cases.",
            agent=classification_agent,
            expected_output="Classification results with labels, confidences, and review flags",
        ),
    ]
    
    return Crew(
        agents=[discovery_agent, classification_agent],
        tasks=tasks,
        verbose=True,
    )


def create_rights_request_crew(subject_id: int, schema: str = None):  # type: ignore[misc]
    """
    Create a crew for handling a rights request.
    
    Args:
        subject_id: Subject ID (e.g., patient ID)
        schema: Database schema
        
    Returns:
        Configured Crew instance
    """
    if not CREWAI_AVAILABLE:
        raise RuntimeError("CrewAI not available — install with: pip install crewai")
    
    if schema is None:
        schema = settings.db2_schema
    
    tasks = [
        Task(
            description=f"Build an erasure plan for subject ID {subject_id} in schema '{schema}'.",
            agent=rights_agent,
            expected_output="Detailed erasure plan with actions, reasons, and row estimates",
        ),
    ]
    
    return Crew(
        agents=[rights_agent],
        tasks=tasks,
        verbose=True,
    )


# Convenience functions for direct tool use (without agent wrapper)

def _call_tool(tool_object: Any, *args: Any) -> str:
    function = getattr(tool_object, "func", tool_object)
    return function(*args)


def discover_schema(schema: str) -> dict[str, Any]:
    """
    Discover schema without agent wrapper.
    
    Args:
        schema: Schema name
        
    Returns:
        Schema summary dict
    """
    result = _call_tool(scan_catalog, schema)
    return json.loads(result)


def classify_schema(schema: str) -> dict[str, Any]:
    """
    Classify schema without agent wrapper.
    
    Args:
        schema: Schema name
        
    Returns:
        Classification summary dict
    """
    result = _call_tool(classify_columns_tool, schema)
    return json.loads(result)


def plan_erasure(subject_id: int, schema: str = None) -> dict[str, Any]:
    """
    Plan erasure without agent wrapper.
    
    Args:
        subject_id: Subject ID
        schema: Schema name (optional)
        
    Returns:
        Erasure plan dict
    """
    result = _call_tool(build_erasure_plan_tool, subject_id, schema)
    return json.loads(result)


if __name__ == "__main__":
    """Demonstrate agent tools."""
    print("=" * 60)
    print("Agent Tools Demo")
    print("=" * 60)
    
    schema = settings.db2_schema
    
    # Test discovery tool
    print(f"\n1. Testing scan_catalog tool...")
    result = discover_schema(schema)
    print(f"   Found {len(result.get('tables', []))} tables")
    print(f"   Found {result.get('column_count', 0)} columns")
    print(f"   Found {result.get('fk_count', 0)} foreign keys")
    
    # Test classification tool
    print(f"\n2. Testing classify_columns tool...")
    result = classify_schema(schema)
    print(f"   Classified {result.get('total_columns', 0)} columns")
    print(f"   Found {result.get('pii_columns', 0)} PII columns")
    print(f"   {result.get('needs_review', 0)} columns need review")
    
    # Test erasure planning tool
    print(f"\n3. Testing build_erasure_plan tool...")
    from app.db import query
    patient_result = query("SELECT ID FROM PATIENT FETCH FIRST 1 ROW ONLY")
    
    if patient_result:
        patient_id = patient_result[0][0]
        result = plan_erasure(patient_id)
        
        print(f"   Plan for patient {patient_id}:")
        print(f"   Total steps: {result['simulation']['total_steps']}")
        print(f"   Total rows: {result['simulation']['total_rows']}")
        print(f"   Plan hash: {result['plan_hash'][:16]}...")
        
        if result['simulation']['has_unverified']:
            print(f"   ⚠️  {result['simulation']['unverified_rules']} unverified rules")
    else:
        print("   No patients in database")
    
    print("\n" + "=" * 60)
    print("NOTE: Agents can only plan - they CANNOT execute")
    print("Execution requires human approval through the API")
    print("=" * 60)
