"""
Test Category 17: Missing Evidence Response Test
Ensures honest response when insufficient evidence is found in Db2.
"""

from unittest.mock import MagicMock
from services.answer_service import AnswerService


def test_missing_evidence_exact_response():
    """When no approved records exist, must return the mandated insufficient evidence statement."""
    mock_repo = MagicMock()
    mock_repo.get_approved_observations.return_value = []
    mock_repo.search_observations_by_keyword.return_value = []
    mock_repo.get_latest_observation.return_value = None

    service = AnswerService(mock_repo, api_key="")
    result = service.answer_question(patient_id=1, question="What was my ferritin level?")

    assert result["has_evidence"] is False
    assert result["answer"] == "I could not find sufficient approved records to answer this question."
    assert result["evidence_cards"] == []

