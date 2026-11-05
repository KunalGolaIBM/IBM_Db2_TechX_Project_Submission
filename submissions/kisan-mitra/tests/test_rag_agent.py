"""
Native Db2 Vector RAG Test Suite - Kisan Mitra (किसान मित्र)
Tests semantic retrieval via VECTOR_DISTANCE (Cosine) and official citation grounding.
"""

import pytest
from app.agents.rag_agent import get_rag_agent

@pytest.fixture
def rag_agent():
    return get_rag_agent()

def test_pm_kisan_benefit_retrieval(rag_agent):
    """Test retrieval of PM-KISAN 6,000 INR benefit."""
    res = rag_agent.run("PM-KISAN योजना में किसानों को कितने पैसे मिलते हैं?")
    assert len(res["sources"]) > 0
    top_doc = res["sources"][0]["doc_name"]
    assert "PM_KISAN" in top_doc
    assert res["sources"][0]["distance"] < 0.6
    assert "6,000" in res["answer"] or "6000" in res["answer"]

def test_pm_kisan_exclusion_criteria(rag_agent):
    """Test retrieval of PM-KISAN exclusion criteria (page 3)."""
    res = rag_agent.run("PM-KISAN me kon aavedan nahi kar sakta?")
    assert len(res["sources"]) > 0
    # Must retrieve exclusion page (page 3)
    pages = [s["page_number"] for s in res["sources"]]
    assert 3 in pages
    assert "अपात्र" in res["answer"] or "Exclusion" in res["answer"] or "ineligible" in res["answer"].lower()

def test_pmfby_72_hour_claim_rule(rag_agent):
    """Test PMFBY 72-hour localized calamity intimation rule."""
    res = rag_agent.run("फसल नष्ट होने पर कितने घंटे में क्लेम करना होता है?")
    assert len(res["sources"]) > 0
    docs = [s["doc_name"] for s in res["sources"]]
    assert any("PMFBY" in d for d in docs)
    assert "72" in res["answer"]

def test_kcc_effective_interest_rate(rag_agent):
    """Test KCC concessional interest rate (4% with prompt repayment)."""
    res = rag_agent.run("Kisan Credit Card (KCC) par kitna byaj lagta hai?")
    assert len(res["sources"]) > 0
    docs = [s["doc_name"] for s in res["sources"]]
    assert any("KCC" in d for d in docs)
    assert "4%" in res["answer"] or "7%" in res["answer"]

def test_kcc_collateral_free_waiver(rag_agent):
    """Test KCC collateral-free loan limit (up to 1.60 lakh)."""
    res = rag_agent.run("KCC me bina guarantee ya collateral ke kitna loan milta hai?")
    assert len(res["sources"]) > 0
    docs = [s["doc_name"] for s in res["sources"]]
    assert any("KCC" in d for d in docs)
    pages = [s["page_number"] for s in res["sources"]]
    assert 4 in pages or 3 in pages
    assert "1.60" in res["answer"] or "1.6" in res["answer"] or "1,60,000" in res["answer"]
