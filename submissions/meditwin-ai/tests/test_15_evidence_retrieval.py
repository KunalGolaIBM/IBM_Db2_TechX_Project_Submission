"""
Test Category 15: Evidence Retrieval Test
Validates test code extraction, alias resolution, and evidence grouping.
"""

from services.retrieval_service import identify_test_code, identify_test_name_keyword, TEST_CODE_ALIASES


def test_alias_resolution():
    """Verify various phrasing resolves to standard clinical codes."""
    assert identify_test_code("What is the latest HbA1c?") == "HBA1C"
    assert identify_test_code("How did hemoglobin a1c change?") == "HBA1C"
    assert identify_test_code("Check fasting blood sugar") == "FBS"
    assert identify_test_code("Show total cholesterol") == "CHOL"
    assert identify_test_code("What is the latest TSH level?") == "TSH"
    assert identify_test_code("Show creatinine measurements") == "CREAT"


def test_keyword_extraction():
    """Verify keyword extraction when explicit abbreviation is absent."""
    kw = identify_test_name_keyword("Show me recent cholesterol tests")
    assert kw == "cholesterol"

