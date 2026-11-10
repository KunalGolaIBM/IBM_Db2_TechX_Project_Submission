"""
LangGraph Investigation Workflow for CatalogLens.
Orchestrates an agentic 6-step stateful investigation pipeline:
1. MetadataRetriever
2. SchemaAnalyzer
3. RelationshipInvestigator
4. ClaudeReasoner
5. EvidenceValidator
6. ReportGenerator
"""
import logging
from typing import Any, Dict, List
from langgraph.graph import StateGraph, START, END

from .state import InvestigationState
from ..db.metadata_extractor import MetadataExtractor
from ..services.relationship_detector import RelationshipDetector
from ..services.evidence_service import EvidenceService
from ..agents.claude_client import ClaudeClient
from ..models.relationship import RelationshipType

logger = logging.getLogger("CatalogLens.InvestigationGraph")


def node_metadata_retriever(state: InvestigationState) -> Dict[str, Any]:
    """Node 1: Retrieves schema metadata from Db2 or demo dataset."""
    schema_name = state.get("schema_name", "ENTERPRISE")
    use_demo = state.get("use_demo", True)
    extractor = MetadataExtractor()
    metadata = extractor.extract_schema_metadata(schema_name=schema_name, use_demo=use_demo)

    selected_table = state.get("selected_table", "").strip().upper()
    table_obj = metadata.get_object(selected_table)

    errors = list(state.get("errors", []))
    if not table_obj:
        errors.append(f"Table '{selected_table}' was not found in schema '{schema_name}'.")

    return {
        "metadata": metadata,
        "errors": errors,
    }


def node_schema_analyzer(state: InvestigationState) -> Dict[str, Any]:
    """Node 2: Constructs ground-truth evidence ledger and analyzes structural baseline."""
    metadata = state.get("metadata")
    selected_table = state.get("selected_table", "").strip().upper()

    if not metadata or not metadata.get_object(selected_table):
        return {"table_evidence_ledger": []}

    evidence_svc = EvidenceService(metadata)
    initial_ledger = evidence_svc.build_table_evidence_ledger(selected_table)
    return {"table_evidence_ledger": initial_ledger}


def node_relationship_investigator(state: InvestigationState) -> Dict[str, Any]:
    """Node 3: Deterministically discovers declared and candidate inferred relationships."""
    metadata = state.get("metadata")
    if not metadata:
        return {"declared_relationships": [], "inferred_relationships": []}

    detector = RelationshipDetector()
    all_rels = detector.discover_relationships(metadata)

    declared = [r for r in all_rels if r.relationship_type == RelationshipType.DECLARED]
    inferred = [r for r in all_rels if r.relationship_type == RelationshipType.INFERRED]

    return {
        "declared_relationships": declared,
        "inferred_relationships": inferred,
    }


def node_claude_reasoner(state: InvestigationState) -> Dict[str, Any]:
    """Node 4: Uses Anthropic Claude (or heuristic engine) to synthesize semantic meaning."""
    metadata = state.get("metadata")
    selected_table = state.get("selected_table", "").strip().upper()
    errors = state.get("errors", [])

    if not metadata or errors:
        return {"ai_understanding": None}

    table_obj = metadata.get_object(selected_table)
    if not table_obj:
        return {"ai_understanding": None}

    all_rels = state.get("declared_relationships", []) + state.get("inferred_relationships", [])
    claude_client = ClaudeClient()
    understanding = claude_client.explain_table(
        table=table_obj,
        relationships=all_rels,
        schema_name=state.get("schema_name", "ENTERPRISE"),
    )

    return {"ai_understanding": understanding}


def node_evidence_validator(state: InvestigationState) -> Dict[str, Any]:
    """Node 5: Validates all AI claims programmatically against schema catalog facts."""
    metadata = state.get("metadata")
    understanding = state.get("ai_understanding")

    if not metadata or not understanding:
        return {"validated_evidence": [], "discrepancies": []}

    evidence_svc = EvidenceService(metadata)
    validated_claims = []
    all_discrepancies = []

    # Include initial ground-truth ledger
    for claim in state.get("table_evidence_ledger", []):
        validated_claims.append(claim)

    # Validate AI-generated claims
    for claim in understanding.evidence:
        validated = evidence_svc.validate_claim(claim)
        validated_claims.append(validated)
        if validated.discrepancies:
            all_discrepancies.extend(validated.discrepancies)

    # Update understanding object with validated claims
    understanding.evidence = validated_claims

    return {
        "validated_evidence": validated_claims,
        "discrepancies": all_discrepancies,
        "ai_understanding": understanding,
    }


def node_report_generator(state: InvestigationState) -> Dict[str, Any]:
    """Node 6: Compiles final evidence-backed investigation report."""
    understanding = state.get("ai_understanding")
    metadata = state.get("metadata")
    selected_table = state.get("selected_table", "")
    all_rels = state.get("declared_relationships", []) + state.get("inferred_relationships", [])
    related = [r for r in all_rels if r.source_table == selected_table or r.target_table == selected_table]

    report = {
        "table_name": selected_table,
        "schema_name": state.get("schema_name", "ENTERPRISE"),
        "investigation_question": state.get("investigation_question"),
        "table_understanding": (understanding.model_dump() if hasattr(understanding, "model_dump") else understanding.dict()) if understanding else None,
        "relevant_relationships_count": len(related),
        "declared_relationships_count": len([r for r in related if r.relationship_type.value == "DECLARED"]),
        "inferred_relationships_count": len([r for r in related if r.relationship_type.value == "INFERRED"]),
        "total_evidence_claims": len(state.get("validated_evidence", [])),
        "discrepancies": state.get("discrepancies", []),
        "success": len(state.get("errors", [])) == 0,
        "errors": state.get("errors", []),
    }

    return {"final_report": report}


def create_investigation_graph():
    """Builds and compiles the stateful LangGraph workflow."""
    workflow = StateGraph(InvestigationState)

    # Add Nodes
    workflow.add_node("MetadataRetriever", node_metadata_retriever)
    workflow.add_node("SchemaAnalyzer", node_schema_analyzer)
    workflow.add_node("RelationshipInvestigator", node_relationship_investigator)
    workflow.add_node("ClaudeReasoner", node_claude_reasoner)
    workflow.add_node("EvidenceValidator", node_evidence_validator)
    workflow.add_node("ReportGenerator", node_report_generator)

    # Define Linear Execution Flow
    workflow.add_edge(START, "MetadataRetriever")
    workflow.add_edge("MetadataRetriever", "SchemaAnalyzer")
    workflow.add_edge("SchemaAnalyzer", "RelationshipInvestigator")
    workflow.add_edge("RelationshipInvestigator", "ClaudeReasoner")
    workflow.add_edge("ClaudeReasoner", "EvidenceValidator")
    workflow.add_edge("EvidenceValidator", "ReportGenerator")
    workflow.add_edge("ReportGenerator", END)

    return workflow.compile()
