"""
Tests for Gramin Mitra (Rural Conversational Agent)
Verifies simplification for illiterate/neo-literate farmers and voice formatting.
"""

import pytest
from app.agents.rural_agent import get_rural_agent

@pytest.fixture
def rural_agent():
    return get_rural_agent()

def test_normalize_rural_colloquial_query(rural_agent):
    """Test mapping of village expressions to search intents."""
    q1 = "khet me paani bhar gya kya karein"
    norm1 = rural_agent.normalize_rural_query(q1)
    assert "fasal bima" in norm1.lower() or "flood" in norm1.lower()

    q2 = "chhe hazar kab aayenge"
    norm2 = rural_agent.normalize_rural_query(q2)
    assert "pm-kisan" in norm2.lower()

def test_rural_simplification_pm_kisan(rural_agent):
    """Ensure PM-KISAN answer is transformed into plain-language bullet points."""
    tech_answer = "Under PM-KISAN operational guidelines, institutional landholders and income tax payees are excluded."
    simplified = rural_agent.simplify_for_farmer("PM-KISAN me kon aavedan nahi kar sakta?", tech_answer)
    assert "₹" in simplified or "रुपये" in simplified or "पैसा" in simplified or "लाभ" in simplified
    assert len(simplified) > 20

def test_rural_simplification_pmfby(rural_agent):
    """Ensure PMFBY crop damage answer emphasizes the 72-hour timeline simply."""
    tech_answer = "As per PMFBY Section 7, localized calamities require post-harvest loss intimation within 72 hours."
    simplified = rural_agent.simplify_for_farmer("baadh se fasal kharab ho gayi to kya karein", tech_answer)
    assert "72" in simplified or "3 दिन" in simplified
    assert "14447" in simplified or "नुकसान" in simplified or "बैंक" in simplified

def test_to_speech_text_cleans_markdown(rural_agent):
    """Ensure speech text strips markdown syntax for smooth text-to-speech audio."""
    sample_md = "**राम-राम किसान भाई!**\n• आपको ₹6,000 मिलेंगे (100% गारंटी)।\n[विस्तार देखें](http://pmkisan.gov.in)"
    speech_ready = rural_agent.to_speech_text(sample_md)
    # No markdown asterisks
    assert "*" not in speech_ready
    # No brackets or URLs
    assert "http" not in speech_ready
    # Currency symbol normalized to readable Hindi word
    assert "रुपये" in speech_ready
    assert "प्रतिशत" in speech_ready
