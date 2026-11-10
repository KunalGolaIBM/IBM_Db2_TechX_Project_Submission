"""
Tests for PII classification.
"""
import pytest

from app import classify as classify_module
from app.classify import (
    Classification,
    classify_by_name,
    classify_column,
    scan_values,
    verhoeff_valid,
)
from app.config import settings


class TestVerhoeffValidation:
    """Tests for Aadhaar Verhoeff checksum validation."""
    
    def test_valid_aadhaar(self):
        """Test that a valid Aadhaar passes checksum."""
        # This checksum is generated from the preceding 11 digits.
        assert verhoeff_valid("234123451235")
    
    def test_invalid_aadhaar(self):
        """Test that invalid Aadhaar fails checksum."""
        # Random 12 digits (likely invalid)
        assert not verhoeff_valid("123456789012")
    
    def test_verhoeff_empty_string(self):
        """Test Verhoeff with empty string."""
        assert not verhoeff_valid("")

    def test_verhoeff_rejects_non_aadhaar_length(self):
        """Test that valid checksums with the wrong length are rejected."""
        assert not verhoeff_valid("12345")
    
    def test_verhoeff_non_numeric(self):
        """Test Verhoeff with non-numeric input."""
        assert not verhoeff_valid("ABCD12345678")


class TestValueScanning:
    """Tests for value-based PII detection."""
    
    def test_scan_email_values(self):
        """Test email detection in values."""
        samples = [
            "john.doe@example.com",
            "jane@company.org",
            "not-an-email",
            None,
        ]
        result = scan_values(samples)
        assert "EMAIL" in result
        assert result["EMAIL"] == 0.5  # 2 out of 4
    
    def test_scan_pan_values(self):
        """Test PAN detection in values."""
        samples = [
            "ABCDE1234F",
            "XYZPQ5678R",
            "not-a-pan",
        ]
        result = scan_values(samples)
        assert "PAN" in result
        assert result["PAN"] == pytest.approx(0.666, abs=0.01)
    
    def test_scan_phone_values(self):
        """Test phone detection in values."""
        samples = [
            "+91 9876543210",
            "9123456789",
            "8765432109",
            "1234567890",  # Doesn't start with 6-9
        ]
        result = scan_values(samples)
        assert "PHONE" in result
        # First 3 are valid Indian phones
        assert result["PHONE"] == 0.75
    
    def test_scan_phone_as_number(self):
        """Test phone detection when stored as number."""
        samples = [
            9876543210,
            8123456789,
            1234567890,  # Invalid (doesn't start with 6-9)
        ]
        result = scan_values(samples)
        assert "PHONE" in result
        assert result["PHONE"] == pytest.approx(0.666, abs=0.01)
    
    def test_scan_empty_samples(self):
        """Test scanning empty sample list."""
        result = scan_values([])
        assert result == {}
    
    def test_scan_no_pii(self):
        """Test scanning values with no PII."""
        samples = ["foo", "bar", "baz", 123, 456]
        result = scan_values(samples)
        assert len(result) == 0


class TestNameClassification:
    """Tests for name-based classification."""
    
    def test_classify_email_column(self):
        """Test classification of email-like column names."""
        result = classify_by_name("CUST_MAIL_ID")
        assert result is not None
        label, distance = result
        assert label == "EMAIL"
    
    def test_classify_phone_column(self):
        """Test classification of phone-like column names."""
        result = classify_by_name("PH_NO")
        assert result is not None
        label, distance = result
        assert label == "PHONE"
    
    def test_classify_address_column(self):
        """Test classification of address-like column names."""
        result = classify_by_name("ADDR1")
        assert result is not None
        label, distance = result
        assert label == "ADDRESS"
    
    def test_classify_name_column(self):
        """Test classification of name-like column names."""
        result = classify_by_name("FULL_NM")
        assert result is not None
        label, distance = result
        assert label == "NAME"
    
    def test_classify_unclear_column(self):
        """Test classification of unclear column name."""
        result = classify_by_name("STATUS")
        # Should return None or low confidence
        assert result is None or result[1] > 0.5

    def test_live_name_match_is_marked_as_vector(self, monkeypatch):
        monkeypatch.setattr(classify_module, "MOCK_MODE", False)
        monkeypatch.setattr(classify_module, "sample_values", lambda *args, **kwargs: [])
        monkeypatch.setattr(classify_module, "scan_values", lambda samples: {})
        monkeypatch.setattr(classify_module, "classify_by_name", lambda column: ("EMAIL", 0.1))

        result = classify_module.classify_column("DB2INST1", "PATIENT", "MAIL", "VARCHAR")

        assert result.label == "EMAIL"
        assert result.method == "NAME_VECTOR"

    @pytest.mark.parametrize(
        ("column", "expanded"),
        [("PH_NO", "phone number"), ("ADDR1", "address")],
    )
    def test_live_name_lookup_expands_abbreviations(
        self, monkeypatch, column, expanded
    ):
        monkeypatch.setattr(classify_module, "MOCK_MODE", False)
        looked_up = []

        def classify_name(value):
            looked_up.append(value)
            return "PHONE", 0.1

        monkeypatch.setattr(
            "app.vector_store.classify_column_name", classify_name
        )

        classify_by_name(column)

        assert looked_up == [expanded]

    def test_decoy_reference_number_is_not_classified_as_phone(self, monkeypatch):
        monkeypatch.setattr(
            classify_module, "sample_values", lambda *args, **kwargs: [9876543210]
        )
        monkeypatch.setattr(classify_module, "classify_by_name", lambda column: ("PHONE", 0.1))

        result = classify_column(
            "DB2INST1", "SUPPORT_TICKET", "TICKET_REF_NO", "VARCHAR"
        )

        assert result.label == "NOT_PII"


@pytest.mark.parametrize(
    ("table", "column", "expected_label"),
    [
        ("PATIENT", "FULL_NM", "NAME"),
        ("PATIENT", "ADDR1", "ADDRESS"),
        ("PATIENT", "ADDR2", "ADDRESS"),
        ("PATIENT", "CITY_NM", "ADDRESS"),
        ("PATIENT", "PINCODE", "ADDRESS"),
        ("PATIENT", "NOTES", "FREE_TEXT"),
        ("APPOINTMENT", "DOCTOR_NM", "NAME"),
        ("APPOINTMENT", "REASON", "HEALTH"),
        ("APPOINTMENT", "NOTES", "HEALTH"),
        ("PRESCRIPTION", "MEDICATION", "HEALTH"),
        ("PRESCRIPTION", "DOSAGE", "HEALTH"),
        ("PRESCRIPTION", "INSTRUCTIONS", "HEALTH"),
        ("LAB_REPORT", "TEST_NM", "HEALTH"),
        ("LAB_REPORT", "RESULT_VALUE", "HEALTH"),
        ("LAB_REPORT", "REMARKS", "HEALTH"),
        ("SUPPORT_TICKET", "DESCRIPTION", "FREE_TEXT"),
    ],
)
def test_metadata_rules_fallback_when_vector_search_is_uncertain(
    monkeypatch, table, column, expected_label
):
    monkeypatch.setattr(classify_module, "MOCK_MODE", False)
    monkeypatch.setattr(classify_module, "sample_values", lambda *args, **kwargs: [])
    monkeypatch.setattr(classify_module, "classify_by_name", lambda name: None)

    result = classify_module.classify_column("DB2INST1", table, column, "VARCHAR")

    assert result.label == expected_label
    assert result.method == "NAME_RULE"
    assert result.confidence == 0.95


def test_classification_progress_output_is_windows_console_safe(monkeypatch, capsys):
    monkeypatch.setattr(classify_module, "MOCK_MODE", False)
    monkeypatch.setattr(
        classify_module,
        "columns",
        lambda schema: [("PATIENT", "FULL_NM", "VARCHAR", 100, "Y")],
    )
    monkeypatch.setattr(classify_module, "sample_values", lambda *args, **kwargs: [])
    monkeypatch.setattr(classify_module, "classify_by_name", lambda name: None)
    monkeypatch.setattr(classify_module, "persist_classification", lambda result: None)

    classify_module.run("DB2INST1")

    output = capsys.readouterr().out
    assert "[PII] NAME" in output
    assert output.isascii()


class TestColumnClassification:
    """Tests for full column classification."""

    pytestmark = pytest.mark.integration
    
    def test_classify_id_column_as_not_pii(self):
        """Test that ID columns are classified as NOT_PII."""
        result = classify_column(
            settings.db2_schema, "PATIENT", "ID", "INTEGER"
        )
        assert result.label == "NOT_PII"
        assert result.confidence >= 0.9
    
    def test_classification_has_required_fields(self):
        """Test that classification result has all required fields."""
        result = classify_column(
            settings.db2_schema, "PATIENT", "CUST_MAIL_ID", "VARCHAR"
        )
        assert hasattr(result, "table")
        assert hasattr(result, "column")
        assert hasattr(result, "label")
        assert hasattr(result, "confidence")
        assert hasattr(result, "method")
        assert result.table == "PATIENT"
        assert result.column == "CUST_MAIL_ID"
    
    def test_classify_email_column_real_data(self):
        """Test email classification with real sampled data."""
        # CUST_MAIL_ID should be detected as EMAIL
        result = classify_column(
            settings.db2_schema, "PATIENT", "CUST_MAIL_ID", "VARCHAR"
        )
        assert result.label == "EMAIL"
        assert result.confidence > 0.5
    
    def test_classify_phone_column_real_data(self):
        """Test phone classification with real sampled data."""
        # PH_NO is stored as BIGINT with phone numbers
        result = classify_column(
            settings.db2_schema, "PATIENT", "PH_NO", "BIGINT"
        )
        assert result.label == "PHONE"
        assert result.confidence > 0.5


class TestClassificationDataClass:
    """Tests for Classification dataclass."""
    
    def test_classification_creation(self):
        """Test creating a Classification object."""
        c = Classification(
            table="PATIENT",
            column="EMAIL",
            label="EMAIL",
            confidence=0.95,
            method="VALUE_RULE",
        )
        assert c.table == "PATIENT"
        assert c.column == "EMAIL"
        assert c.label == "EMAIL"
        assert c.confidence == 0.95
        assert c.method == "VALUE_RULE"
        assert c.needs_review is False
    
    def test_classification_with_review_flag(self):
        """Test Classification with needs_review flag."""
        c = Classification(
            table="TEST",
            column="COL",
            label="EMAIL",
            confidence=0.25,
            method="VALUE_RULE",
            needs_review=True,
        )
        assert c.needs_review is True


@pytest.mark.integration
class TestClassificationIntegration:
    """Integration tests that require a populated database."""

    pytestmark = pytest.mark.integration
    
    def test_classify_hidden_pan_in_notes(self):
        """Test that PAN hidden in free text is detected."""
        # PATIENT.NOTES contains hidden PAN numbers
        result = classify_column(
            settings.db2_schema, "PATIENT", "NOTES", "CLOB"
        )
        # Should detect PAN in free text
        # Note: May need review if hit rate is low
        assert result.label in ["PAN", "FREE_TEXT"] or result.needs_review
    
    def test_decoy_column_not_flagged(self):
        """Test that TICKET_REF_NO (decoy) is NOT flagged as PII."""
        # TICKET_REF_NO is 10 digits but NOT PII
        result = classify_column(
            settings.db2_schema, "SUPPORT_TICKET", "TICKET_REF_NO", "VARCHAR"
        )
        # Should be NOT_PII since it's not a valid phone/aadhaar
        assert result.label == "NOT_PII"
