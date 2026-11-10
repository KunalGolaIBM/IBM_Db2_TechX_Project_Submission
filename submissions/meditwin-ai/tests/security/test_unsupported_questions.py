"""
Security Tests: Out-of-Domain & Unsupported Question Handling
"""

from services.retrieval_service import identify_test_code, identify_test_name_keyword


def test_out_of_domain_queries_suppressed():
    unsupported = [
        "What is the weather in Delhi?",
        "Write a poem about databases.",
        "Who won the match yesterday?",
        "Can you prescribe antibiotics for my cough?",
    ]
    for q in unsupported:
        assert identify_test_code(q) is None
        assert identify_test_name_keyword(q) is None

