"""
Tests for Db2 metadata normalization and schema models.
"""
import pytest
from backend.db.sample_catalog import get_sample_enterprise_metadata
from backend.models.schema import DbSchemaMetadata


def test_sample_metadata_structure():
    meta = get_sample_enterprise_metadata()
    assert isinstance(meta, DbSchemaMetadata)
    assert meta.schema_name == "ENTERPRISE"
    assert meta.total_tables == 13
    assert meta.total_views == 2
    assert meta.total_columns > 80
    assert meta.declared_relationships_count >= 10


def test_table_column_lookup():
    meta = get_sample_enterprise_metadata()
    ord_hdr = meta.get_object("ORD_HDR")
    assert ord_hdr is not None
    assert ord_hdr.tabname == "ORD_HDR"
    assert len(ord_hdr.primary_keys) == 1
    assert ord_hdr.primary_keys[0] == "ORDER_ID"

    # Test column lookup case insensitivity
    col = ord_hdr.get_column("total_amt")
    assert col is not None
    assert col.colname == "TOTAL_AMT"
    assert col.typename == "DECIMAL"


def test_view_metadata():
    meta = get_sample_enterprise_metadata()
    v = meta.get_object("V_ACTIVE_ORDERS")
    assert v is not None
    assert v.table_type == "V"
    assert v.view_definition is not None
    assert "JOIN ENTERPRISE.CUSTOMER_MST" in v.view_definition
