"""
MediTwin AI — LangGraph Workflow Definition
Defines the state graph with conditional routing for ingestion and query pipelines.
"""

import logging
from langgraph.graph import StateGraph, END

from graph.nodes import (
    classify_request,
    parse_document_node,
    extract_observations_node,
    validate_extraction_node,
    human_review_gate,
    persist_to_db2_node,
    retrieve_evidence_node,
    generate_answer_node,
    safety_check_node,
    finalize_response_node,
)

logger = logging.getLogger(__name__)


def route_after_classify(state: dict) -> str:
    """Route based on request type."""
    req_type = state.get("request_type")
    if req_type == "upload":
        return "parse_document"
    elif req_type == "question":
        return "retrieve_evidence"
    else:
        return "finalize_response"


def route_after_parse(state: dict) -> str:
    """Route based on parse result."""
    if state.get("parse_status") == "PARSED":
        return "extract_observations"
    else:
        return "finalize_response"


def route_after_validate(state: dict) -> str:
    """Always go to human review after validation."""
    return "human_review_gate"


def build_meditwin_graph() -> StateGraph:
    """
    Build the MediTwin AI LangGraph workflow.

    Two pipelines:
    1. Upload: classify → parse → extract → validate → review → persist → finalize
    2. Question: classify → retrieve → generate → safety → finalize
    """
    # Use dict-based state for simplicity with LangGraph
    workflow = StateGraph(dict)

    # Add all nodes
    workflow.add_node("classify_request", classify_request)
    workflow.add_node("parse_document", parse_document_node)
    workflow.add_node("extract_observations", extract_observations_node)
    workflow.add_node("validate_extraction", validate_extraction_node)
    workflow.add_node("human_review_gate", human_review_gate)
    workflow.add_node("persist_to_db2", persist_to_db2_node)
    workflow.add_node("retrieve_evidence", retrieve_evidence_node)
    workflow.add_node("generate_answer", generate_answer_node)
    workflow.add_node("safety_check", safety_check_node)
    workflow.add_node("finalize_response", finalize_response_node)

    # Set entry point
    workflow.set_entry_point("classify_request")

    # Conditional routing after classification
    workflow.add_conditional_edges(
        "classify_request",
        route_after_classify,
        {
            "parse_document": "parse_document",
            "retrieve_evidence": "retrieve_evidence",
            "finalize_response": "finalize_response",
        }
    )

    # Upload pipeline
    workflow.add_conditional_edges(
        "parse_document",
        route_after_parse,
        {
            "extract_observations": "extract_observations",
            "finalize_response": "finalize_response",
        }
    )
    workflow.add_edge("extract_observations", "validate_extraction")
    workflow.add_edge("validate_extraction", "human_review_gate")
    workflow.add_edge("human_review_gate", "persist_to_db2")
    workflow.add_edge("persist_to_db2", "finalize_response")

    # Question pipeline
    workflow.add_edge("retrieve_evidence", "generate_answer")
    workflow.add_edge("generate_answer", "safety_check")
    workflow.add_edge("safety_check", "finalize_response")

    # End
    workflow.add_edge("finalize_response", END)

    return workflow


def compile_workflow():
    """Compile and return the runnable workflow."""
    graph = build_meditwin_graph()
    return graph.compile()


# Pre-compiled workflow instance
_compiled_workflow = None


def get_workflow():
    """Get or create the compiled workflow."""
    global _compiled_workflow
    if _compiled_workflow is None:
        _compiled_workflow = compile_workflow()
    return _compiled_workflow


def run_upload_workflow(file_name: str, file_bytes: bytes,
                        patient_id: int = None,
                        repo = None,
                        document_id: int = None,
                        gemini_api_key: str = None,
                        gemini_model: str = "gemini-2.0-flash") -> dict:
    """Run the upload pipeline through the LangGraph workflow."""
    wf = get_workflow()
    initial_state = {
        "raw_input": "",
        "file_name": file_name,
        "file_bytes": file_bytes,
        "patient_id": patient_id,
        "document_id": document_id,
        "repo": repo,
        "gemini_api_key": gemini_api_key,
        "gemini_model": gemini_model,
        "request_type": None,
        "completed_nodes": [],
        "extracted_observations": [],
        "validation_errors": [],
        "pages": [],
    }
    result = wf.invoke(initial_state)
    return result


def run_question_workflow(question: str, patient_id: int = None,
                          repo = None,
                          gemini_api_key: str = None,
                          gemini_model: str = "gemini-2.0-flash") -> dict:
    """Run the question pipeline through the LangGraph workflow."""
    wf = get_workflow()
    initial_state = {
        "raw_input": question,
        "patient_id": patient_id,
        "repo": repo,
        "gemini_api_key": gemini_api_key,
        "gemini_model": gemini_model,
        "request_type": None,
        "completed_nodes": [],
        "retrieved_records": [],
        "evidence_cards": [],
        "answer_sources": [],
    }
    result = wf.invoke(initial_state)
    return result

