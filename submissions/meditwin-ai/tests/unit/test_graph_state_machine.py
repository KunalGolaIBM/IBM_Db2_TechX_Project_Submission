"""
Unit Tests: LangGraph Workflow State Transitions
"""

from graph.workflow import build_meditwin_graph, compile_workflow
from graph.nodes import classify_request, human_review_gate, safety_check_node


def test_graph_compilation():
    graph = compile_workflow()
    assert graph is not None


def test_classify_request_node():
    s_upload = classify_request({"file_bytes": b"123"})
    assert s_upload["request_type"] == "upload"

    s_question = classify_request({"raw_input": "What was HbA1c?"})
    assert s_question["request_type"] == "question"
    assert s_question["question"] == "What was HbA1c?"


def test_safety_check_node_detects_diagnostic_language():
    state = {"generated_answer": "Based on records, you are diagnosed with diabetes."}
    res = safety_check_node(state)
    assert res["safety_passed"] is False
    assert "Clinical Safety Warning" in res["generated_answer"]


def test_safety_check_node_passes_clean_evidence():
    state = {"generated_answer": "The latest recorded HbA1c was 6.8% on 2026-11-08 in SyntheticReport_B.pdf."}
    res = safety_check_node(state)
    assert res["safety_passed"] is True

