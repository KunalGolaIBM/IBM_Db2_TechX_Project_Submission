"""
Test Category 16: Unsupported Question Test
Validates handling of irrelevant, nonsensical, or out-of-domain questions.
"""

from services.retrieval_service import identify_test_code, identify_test_name_keyword


def test_unsupported_questions_return_none():
    """Questions not asking about recorded metrics return None."""
    unsupported = [
        "What is the weather in Paris?",
        "Write me a poem about databases.",
        "Who won the 2026 World Cup?",
        "Can you prescribe antibiotics for my cough?",
    ]
    for q in unsupported:
        assert identify_test_code(q) is None
        assert identify_test_name_keyword(q) is None

