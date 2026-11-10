"""
Security Tests: Cross-Patient Data Isolation & Integrity
"""

import pytest
from unittest.mock import MagicMock
from db.repository import Db2Repository


def test_cross_patient_document_reference_rejected():
    mock_conn = MagicMock()
    repo = Db2Repository(mock_conn)

    # Document 100 belongs to patient 2
    repo.get_document = MagicMock(return_value={"DOCUMENT_ID": 100, "PATIENT_ID": 2})

    # Attempting to insert an observation for patient 1 referencing document 100 must fail
    with pytest.raises(ValueError) as excinfo:
        repo.create_observation(
            patient_id=1,
            document_id=100,
            test_name="Glucose",
            value_numeric=110,
        )

    assert "Cross-patient integrity violation" in str(excinfo.value)

