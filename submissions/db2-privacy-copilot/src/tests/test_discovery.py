"""
Tests for schema discovery functionality.
"""
import pytest

from app.config import settings
from app.discovery import (
    columns,
    delete_order,
    fk_column_to_root,
    fk_edges,
    summary,
    tables,
)

pytestmark = pytest.mark.integration


def test_tables_returns_list():
    """Test that tables() returns a list of tables."""
    result = tables(settings.db2_schema)
    assert isinstance(result, list)
    assert len(result) > 0


def test_tables_contains_patient():
    """Test that PATIENT table is discovered."""
    result = tables(settings.db2_schema)
    table_names = [t[0].strip() for t in result]
    assert "PATIENT" in table_names


def test_columns_returns_list():
    """Test that columns() returns column information."""
    result = columns(settings.db2_schema)
    assert isinstance(result, list)
    assert len(result) > 0


def test_columns_structure():
    """Test that column tuples have expected structure."""
    result = columns(settings.db2_schema)
    # Each tuple should have: TABNAME, COLNAME, TYPENAME, LENGTH, NULLS
    assert len(result[0]) == 5


def test_patient_columns_discovered():
    """Test that PATIENT table columns are discovered correctly."""
    result = columns(settings.db2_schema)
    patient_cols = [
        (r[0].strip(), r[1].strip()) for r in result if r[0].strip() == "PATIENT"
    ]
    
    # Check for some key columns with ugly names
    col_names = [c[1] for c in patient_cols]
    assert "CUST_MAIL_ID" in col_names  # Email with ugly name
    assert "PH_NO" in col_names  # Phone as BIGINT
    assert "GOVT_ID" in col_names  # PAN/Aadhaar


def test_fk_edges_returns_list():
    """Test that fk_edges() returns foreign key relationships."""
    result = fk_edges(settings.db2_schema)
    assert isinstance(result, list)


def test_fk_edges_structure():
    """Test that FK edges have expected structure."""
    result = fk_edges(settings.db2_schema)
    if len(result) > 0:
        # Each tuple should have: child_table, parent_table, fk_cols, pk_cols
        assert len(result[0]) == 4


def test_appointment_references_patient():
    """Test that APPOINTMENT -> PATIENT FK is discovered."""
    result = fk_edges(settings.db2_schema)
    
    # Find APPOINTMENT -> PATIENT edge
    appointment_fks = [
        (r[0].strip(), r[1].strip())
        for r in result
        if r[0].strip() == "APPOINTMENT"
    ]
    
    parents = [fk[1] for fk in appointment_fks]
    assert "PATIENT" in parents


def test_delete_order_children_before_parents():
    """Test that delete order puts children before parents."""
    order = delete_order(settings.db2_schema, "PATIENT")
    
    # PATIENT should be last (deleted after all children)
    assert order[-1] == "PATIENT"
    
    # APPOINTMENT should be before PATIENT
    if "APPOINTMENT" in order:
        appt_idx = order.index("APPOINTMENT")
        patient_idx = order.index("PATIENT")
        assert appt_idx < patient_idx


def test_delete_order_includes_all_related_tables():
    """Test that delete order includes all tables with FKs to root."""
    order = delete_order(settings.db2_schema, "PATIENT")
    
    # Expected tables (those with FKs to PATIENT)
    expected = [
        "PATIENT",
        "APPOINTMENT",
        "BILLING",
        "PRESCRIPTION",
        "LAB_REPORT",
        "SUPPORT_TICKET",
        "MARKETING_LIST",
    ]
    
    for table in expected:
        assert table in order, f"{table} should be in delete order"


def test_delete_order_respects_fk_chain():
    """Test that multi-level FK chains are ordered correctly."""
    order = delete_order(settings.db2_schema, "PATIENT")
    
    # BILLING references both PATIENT and APPOINTMENT
    # So BILLING must be before APPOINTMENT
    if "BILLING" in order and "APPOINTMENT" in order:
        billing_idx = order.index("BILLING")
        appt_idx = order.index("APPOINTMENT")
        # BILLING should be deleted before or with APPOINTMENT
        # (both reference PATIENT, but BILLING also references APPOINTMENT)
        assert billing_idx <= appt_idx


def test_fk_column_to_root_patient():
    """Test FK column identification for PATIENT table."""
    # PATIENT itself should return its PK
    col = fk_column_to_root(settings.db2_schema, "PATIENT", "PATIENT")
    assert col is not None
    assert col.upper() in ["ID", "PATIENT_ID"]


def test_fk_column_to_root_appointment():
    """Test FK column identification for APPOINTMENT -> PATIENT."""
    col = fk_column_to_root(settings.db2_schema, "APPOINTMENT", "PATIENT")
    assert col is not None
    assert "PATIENT_ID" in col.upper()


def test_summary_structure():
    """Test that summary returns expected structure."""
    result = summary(settings.db2_schema)
    
    assert isinstance(result, dict)
    assert "schema" in result
    assert "tables" in result
    assert "column_count" in result
    assert "columns_by_table" in result
    assert "foreign_keys" in result
    assert "fk_count" in result


def test_summary_has_patient_columns():
    """Test that summary includes PATIENT table columns."""
    result = summary(settings.db2_schema)
    
    assert "PATIENT" in result["columns_by_table"]
    patient_cols = result["columns_by_table"]["PATIENT"]
    assert len(patient_cols) > 0
    
    # Check structure of column info
    assert "name" in patient_cols[0]
    assert "type" in patient_cols[0]
    assert "nullable" in patient_cols[0]


def test_summary_has_foreign_keys():
    """Test that summary includes FK information."""
    result = summary(settings.db2_schema)
    
    assert len(result["foreign_keys"]) > 0
    fk = result["foreign_keys"][0]
    assert "child" in fk
    assert "parent" in fk
    assert "fk_columns" in fk


def test_summary_column_count_accurate():
    """Test that column count matches actual columns."""
    result = summary(settings.db2_schema)
    
    # Count columns across all tables
    total_cols = sum(len(cols) for cols in result["columns_by_table"].values())
    assert result["column_count"] == total_cols


def test_delete_order_handles_missing_table():
    """Test delete order with a non-existent root table."""
    # This should raise an error or return empty list
    with pytest.raises((KeyError, ValueError)):
        delete_order(settings.db2_schema, "NONEXISTENT_TABLE")


def test_delete_order_rejects_missing_schema():
    with pytest.raises(KeyError):
        delete_order("NONEXISTENT_SCHEMA", "PATIENT")


def test_columns_empty_schema():
    """Test columns() with a non-existent schema."""
    result = columns("NONEXISTENT_SCHEMA")
    assert result == []


def test_tables_empty_schema():
    """Test tables() with a non-existent schema."""
    result = tables("NONEXISTENT_SCHEMA")
    assert result == []


@pytest.mark.parametrize(
    "table_name",
    ["APPOINTMENT", "BILLING", "PRESCRIPTION", "LAB_REPORT", "SUPPORT_TICKET", "MARKETING_LIST"],
)
def test_all_child_tables_have_patient_fk(table_name):
    """Test that all child tables can find their FK to PATIENT."""
    col = fk_column_to_root(settings.db2_schema, table_name, "PATIENT")
    # All these tables should have a FK to PATIENT
    assert col is not None, f"{table_name} should have FK to PATIENT"
