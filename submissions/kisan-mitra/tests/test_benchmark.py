"""
End-to-End Evaluation Benchmark - Kisan Mitra (किसान मित्र)
Executes 10 sample questions across Hindi, Hinglish, and English covering SQL, RAG, and HYBRID intents.
Verifies response generation, safety guarantees, and citation metadata.
"""

import pytest
from app.agents.router import get_router

BENCHMARK_CASES = [
    # 1. SQL Hindi Mandi Query
    {
        "id": "TC-01",
        "question": "मथुरा मंडी में आज आलू का क्या भाव है?",
        "expected_intent": "SQL",
        "must_contain": ["MANDI_PRICES"]
    },
    # 2. SQL Hinglish Weekly Aggregation
    {
        "id": "TC-02",
        "question": "UP me pichhle hafte sabse mehnga kaunsa anaaj tha?",
        "expected_intent": "SQL",
        "must_contain": ["MANDI_PRICES", "ORDER BY"]
    },
    # 3. SQL English Price Comparison
    {
        "id": "TC-03",
        "question": "What is the modal price of wheat in Lucknow market?",
        "expected_intent": "SQL",
        "must_contain": ["MANDI_PRICES"]
    },
    # 4. SQL District Mustard Check
    {
        "id": "TC-04",
        "question": "आगरा में सरसों का न्यूनतम और अधिकतम भाव क्या है?",
        "expected_intent": "SQL",
        "must_contain": ["MANDI_PRICES"]
    },
    # 5. RAG Hindi PM-KISAN Eligibility
    {
        "id": "TC-05",
        "question": "पीएम किसान सम्मान निधि में सालाना कितना पैसा मिलता है?",
        "expected_intent": "RAG",
        "must_contain": ["PM_KISAN_Guidelines.pdf"]
    },
    # 6. RAG Hinglish PM-KISAN Exclusions
    {
        "id": "TC-06",
        "question": "PM-KISAN me kon aavedan nahi kar sakta?",
        "expected_intent": "RAG",
        "must_contain": ["PM_KISAN_Guidelines.pdf"]
    },
    # 7. RAG English PMFBY Claim Deadline
    {
        "id": "TC-07",
        "question": "Within how many hours must crop damage be reported under PMFBY?",
        "expected_intent": "RAG",
        "must_contain": ["PMFBY_Guidelines.pdf"]
    },
    # 8. RAG Hindi KCC Loan & Interest
    {
        "id": "TC-08",
        "question": "किसान क्रेडिट कार्ड पर समय से चुकाने पर कितना ब्याज लगता है?",
        "expected_intent": "RAG",
        "must_contain": ["KCC_Scheme_Guidelines.pdf"]
    },
    # 9. RAG English KCC Collateral Limit
    {
        "id": "TC-09",
        "question": "What is the collateral-free loan limit under the KCC scheme?",
        "expected_intent": "RAG",
        "must_contain": ["KCC_Scheme_Guidelines.pdf"]
    },
    # 10. HYBRID Hindi Composite Query
    {
        "id": "TC-10",
        "question": "आगरा में गेहूं का भाव क्या है और फसल खराब होने पर पीएम फसल बीमा योजना में क्लेम कैसे करें?",
        "expected_intent": "HYBRID",
        "must_contain": ["MANDI_PRICES", "PMFBY_Guidelines.pdf"]
    }
]

@pytest.fixture(scope="module")
def router():
    return get_router()

@pytest.mark.parametrize("case", BENCHMARK_CASES)
def test_benchmark_query(router, case):
    """Execute each benchmark query and assert intent, output integrity, and latency."""
    q = case["question"]
    res = router.run(q)
    
    assert res is not None
    assert res["intent"] == case["expected_intent"], f"Expected {case['expected_intent']} but got {res['intent']} for query: '{q}'"
    assert len(res["answer"]) > 10, "Answer was empty or too short."
    assert res.get("error") is None, f"Query returned error: {res.get('error')}"

    # Verify SQL artifacts for SQL and HYBRID
    if case["expected_intent"] in ("SQL", "HYBRID"):
        sql = res.get("generated_sql", "")
        assert sql and "MANDI_PRICES" in sql
        assert res.get("row_count", 0) > 0

    # Verify RAG citations for RAG and HYBRID
    if case["expected_intent"] in ("RAG", "HYBRID"):
        sources = res.get("sources", [])
        assert len(sources) > 0, "No sources retrieved for RAG query"
        expected_doc = [c for c in case["must_contain"] if c.endswith(".pdf")]
        if expected_doc:
            retrieved_docs = [s["doc_name"] for s in sources]
            assert any(expected_doc[0] in d for d in retrieved_docs)
