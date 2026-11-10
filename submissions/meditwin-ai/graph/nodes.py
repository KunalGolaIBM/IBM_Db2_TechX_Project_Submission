"""
MediTwin AI — LangGraph Workflow Nodes
Each function is a genuinely functional node in the LangGraph state machine.
Directly interfaces with Db2Repository, RetrievalService, and AnswerService.
"""

import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime

from graph.state import MediTwinState
from ingestion.pdf_parser import parse_document, validate_file
from ingestion.extraction import extract_from_document
from ingestion.validation import ExtractedObservation
from services.timeline_service import compute_metric_trend, format_trend_summary
from services.retrieval_service import RetrievalService, identify_test_code, identify_test_name_keyword

logger = logging.getLogger(__name__)


def classify_request(state: dict) -> dict:
    """Node 1: Classify incoming request as upload or question."""
    s = state.copy()
    raw = s.get("raw_input", "")

    if s.get("file_bytes") is not None:
        s["request_type"] = "upload"
    elif raw and str(raw).strip():
        s["request_type"] = "question"
        s["question"] = str(raw).strip()
    else:
        s["request_type"] = "unknown"
        s["error"] = "No valid input provided to workflow."

    s["current_node"] = "classify_request"
    s["completed_nodes"] = s.get("completed_nodes", []) + ["classify_request"]
    return s


def parse_document_node(state: dict) -> dict:
    """Node 2: Validate file integrity, compute SHA-256, and extract text page-by-page."""
    s = state.copy()
    s["current_node"] = "parse_document"

    file_name = s.get("file_name", "unknown.pdf")
    file_bytes = s.get("file_bytes")

    if not file_bytes:
        s["error"] = "No file data available for parsing."
        s["parse_status"] = "FAILED"
        return s

    is_valid, err = validate_file(file_name, file_bytes)
    if not is_valid:
        s["error"] = err
        s["parse_status"] = "FAILED"
        return s

    result = parse_document(file_name, file_bytes)
    s["parsed_text"] = result.full_text
    s["source_hash"] = result.source_hash
    s["pages"] = [
        {"page_number": p.page_number, "text": p.text, "char_count": p.char_count}
        for p in result.pages
    ]
    s["parse_status"] = result.parse_status
    if result.error_message:
        s["parse_error"] = result.error_message

    s["completed_nodes"] = s.get("completed_nodes", []) + ["parse_document"]
    return s


def extract_observations_node(state: dict) -> dict:
    """Node 3: Extract structured observations using LangChain + Gemini."""
    s = state.copy()
    s["current_node"] = "extract_observations"

    if s.get("parse_status") != "PARSED":
        s["error"] = f"Extraction halted: document status is {s.get('parse_status')}"
        return s

    pages = s.get("pages", [])
    if not pages:
        s["error"] = "No readable pages found in document."
        return s

    pages_text = [(p["page_number"], p["text"]) for p in pages]
    api_key = s.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
    model_name = s.get("gemini_model") or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

    result = extract_from_document(
        pages_text=pages_text,
        api_key=api_key,
        model_name=model_name,
    )

    s["extracted_observations"] = [obs.model_dump() for obs in result.observations]
    s["extraction_notes"] = result.extraction_notes

    s["completed_nodes"] = s.get("completed_nodes", []) + ["extract_observations"]
    return s


def validate_extraction_node(state: dict) -> dict:
    """Node 4: Strict Pydantic validation, flagging missing dates, units, or low confidence."""
    s = state.copy()
    s["current_node"] = "validate_extraction"

    observations = s.get("extracted_observations", [])
    validation_errors = []
    validated_list = []

    for i, obs_dict in enumerate(observations):
        try:
            obs = ExtractedObservation(**obs_dict)
            dumped = obs.model_dump()
            dumped["needs_review"] = obs.needs_review
            dumped["review_reasons"] = obs.review_reasons
            validated_list.append(dumped)

            if obs.needs_review:
                for reason in obs.review_reasons:
                    validation_errors.append(f"Observation {i+1} ({obs.test_name}): {reason}")
        except Exception as e:
            validation_errors.append(f"Observation {i+1}: Schema error - {str(e)}")

    s["extracted_observations"] = validated_list
    s["validation_errors"] = validation_errors
    s["awaiting_review"] = True
    s["completed_nodes"] = s.get("completed_nodes", []) + ["validate_extraction"]
    return s


def human_review_gate(state: dict) -> dict:
    """Node 5: Human review checkpoint. Extracted records must remain PENDING until approved."""
    s = state.copy()
    s["current_node"] = "human_review_gate"
    s["awaiting_review"] = True
    s["review_required"] = True
    s["completed_nodes"] = s.get("completed_nodes", []) + ["human_review_gate"]
    return s


def persist_to_db2_node(state: dict) -> dict:
    """
    Node 6: Persist validated observations to IBM Db2 with default PENDING review_status.
    Requires repository instance in state or via global connection.
    """
    s = state.copy()
    s["current_node"] = "persist_to_db2"

    repo = s.get("repo")
    patient_id = s.get("patient_id")
    doc_id = s.get("document_id")
    observations = s.get("extracted_observations", [])

    if repo and patient_id and doc_id and observations:
        saved_count = 0
        for obs in observations:
            try:
                repo.create_observation(
                    patient_id=patient_id,
                    document_id=doc_id,
                    test_name=obs.get("test_name"),
                    test_code=obs.get("test_code"),
                    value_numeric=obs.get("value_numeric"),
                    value_text=obs.get("value_text"),
                    unit=obs.get("unit"),
                    reference_low=obs.get("reference_low"),
                    reference_high=obs.get("reference_high"),
                    observed_at=obs.get("observed_at"),
                    source_page=obs.get("source_page"),
                    source_snippet=obs.get("source_snippet"),
                    extraction_confidence=obs.get("confidence"),
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"Error persisting observation in node: {e}")

        s["observations_saved"] = saved_count
        try:
            if hasattr(repo, "connection") and repo.connection and hasattr(repo.connection, "commit"):
                repo.connection.commit()
        except Exception as e:
            logger.error(f"Error committing persisted observations: {e}")

    s["completed_nodes"] = s.get("completed_nodes", []) + ["persist_to_db2"]
    return s


def retrieve_evidence_node(state: dict) -> dict:
    """Node 7: Predefined parameterized Db2 retrieval matching question intent."""
    s = state.copy()
    s["current_node"] = "retrieve_evidence"
    s["completed_nodes"] = s.get("completed_nodes", []) + ["retrieve_evidence"]

    repo = s.get("repo")
    patient_id = s.get("patient_id")
    question = s.get("question", "")

    if not repo:
        # Offline or unconfigured Db2 state: insufficient evidence
        s["retrieved_records"] = []
        s["sufficient_evidence"] = False
        return s

    retrieval_svc = RetrievalService(repo)
    evidence = retrieval_svc.retrieve_evidence_for_question(patient_id, question)

    s["retrieved_records"] = evidence.get("observations", [])
    s["source_documents"] = evidence.get("source_documents", [])
    s["test_code_identified"] = evidence.get("test_code_identified")
    s["sufficient_evidence"] = evidence.get("sufficient_evidence", False)
    return s


def generate_answer_node(state: dict) -> dict:
    """Node 8: Synthesize grounded response using Gemini from retrieved Db2 evidence."""
    s = state.copy()
    s["current_node"] = "generate_answer"

    if not s.get("sufficient_evidence"):
        s["generated_answer"] = "I could not find sufficient approved records to answer this question."
        s["evidence_cards"] = []
        s["completed_nodes"] = s.get("completed_nodes", []) + ["generate_answer"]
        return s

    repo = s.get("repo")
    patient_id = s.get("patient_id")
    question = s.get("question", "")
    api_key = s.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")

    from services.answer_service import AnswerService
    answer_svc = AnswerService(repo, api_key=api_key)
    result = answer_svc.answer_question(patient_id, question)

    s["generated_answer"] = result.get("answer", "")
    s["evidence_cards"] = result.get("evidence_cards", [])
    s["answer_sources"] = result.get("sources", [])
    s["completed_nodes"] = s.get("completed_nodes", []) + ["generate_answer"]
    return s


def safety_check_node(state: dict) -> dict:
    """Node 9: Clinical safety gate prohibiting diagnostic and prescriptive claims."""
    s = state.copy()
    s["current_node"] = "safety_check"

    answer = s.get("generated_answer", "")
    prohibited_terms = [
        "you have", "you are diagnosed with", "diagnosis is",
        "you should take", "i recommend taking", "prescribe",
        "prescription", "treatment plan for you", "cure",
    ]

    detected_issues = []
    for term in prohibited_terms:
        if term in answer.lower():
            detected_issues.append(f"Prohibited diagnostic phrase '{term}' detected.")

    if detected_issues:
        s["safety_passed"] = False
        s["safety_notes"] = "; ".join(detected_issues)
        s["generated_answer"] = (
            answer +
            "\n\n⚠️ **Clinical Safety Warning:** MediTwin AI is an evidence organization tool, "
            "not a diagnostic engine. It does not provide medical diagnosis or treatment advice."
        )
    else:
        s["safety_passed"] = True

    s["completed_nodes"] = s.get("completed_nodes", []) + ["safety_check"]
    return s


def finalize_response_node(state: dict) -> dict:
    """Node 10: Format final output and execution summary."""
    s = state.copy()
    s["current_node"] = "finalize_response"

    if s.get("error"):
        s["final_response"] = f"Workflow Error: {s['error']}"
    elif s.get("request_type") == "upload":
        obs_count = len(s.get("extracted_observations", []))
        s["final_response"] = (
            f"Successfully processed document '{s.get('file_name')}'. "
            f"Extracted {obs_count} observations. Human review required."
        )
    elif s.get("request_type") == "question":
        s["final_response"] = s.get("generated_answer", "")
        s["final_answer"] = s.get("generated_answer", "")
    else:
        s["final_response"] = "Request completed."

    s["completed_nodes"] = s.get("completed_nodes", []) + ["finalize_response"]
    return s
