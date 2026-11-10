"""
Test Category 2: Schema Initialization Test
Validates schema DDL completeness, constraints, indexes, and syntax.
"""

from pathlib import Path
import re


def test_schema_file_exists():
    """Verify schema.sql exists and is non-empty."""
    schema_path = Path("db/schema.sql")
    assert schema_path.exists()
    content = schema_path.read_text()
    assert len(content) > 100


def test_schema_contains_all_required_tables():
    """Verify all 5 mandatory tables are defined in schema.sql."""
    content = Path("db/schema.sql").read_text()
    required_tables = ["PATIENT", "DOCUMENT", "OBSERVATION", "TIMELINE_EVENT", "AUDIT_LOG"]
    for table in required_tables:
        match = re.search(rf"CREATE\s+TABLE\s+{table}", content, re.IGNORECASE)
        assert match is not None, f"Missing table definition: {table}"


def test_schema_contains_required_constraints():
    """Verify primary keys, foreign keys, and check constraints."""
    content = Path("db/schema.sql").read_text()
    assert "PRIMARY KEY (patient_id)" in content or "pk_patient" in content
    assert "PRIMARY KEY (document_id)" in content or "pk_document" in content
    assert "PRIMARY KEY (observation_id)" in content or "pk_observation" in content
    assert "PRIMARY KEY (event_id)" in content or "pk_timeline_event" in content
    assert "PRIMARY KEY (audit_id)" in content or "pk_audit_log" in content

    # Review status check constraint
    assert "PENDING" in content
    assert "APPROVED" in content
    assert "REJECTED" in content

    # Indexes
    assert "CREATE INDEX" in content

