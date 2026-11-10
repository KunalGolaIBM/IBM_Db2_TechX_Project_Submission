"""
Unit tests for CatalogLens REST API route functions and responses.
"""
import pytest
from backend.api.routes import (
    health_check,
    get_schemas,
    get_metadata,
    list_tables,
    get_table_details,
    get_relationships,
    analyze_workflows,
    investigate_dependencies,
    AnalyzeWorkflowRequest,
    InvestigateDependenciesRequest,
    ConnectionTestRequest,
    test_connection as api_test_connection,
)
from backend.models.schema import DbSchemaMetadata, DbTable


def test_health_endpoint():
    res = health_check()
    assert res.status == "healthy"
    assert res.version == "1.0.0"
    assert res.demo_mode is False


def test_schemas_endpoint():
    schemas = get_schemas(use_demo=True)
    assert isinstance(schemas, list)
    assert "ENTERPRISE" in schemas


def test_metadata_endpoint():
    meta = get_metadata(schema_name="ENTERPRISE", use_demo=True)
    assert isinstance(meta, DbSchemaMetadata)
    assert meta.schema_name == "ENTERPRISE"
    assert "CUSTOMER_MST" in meta.tables
    assert meta.total_tables == 13
    assert meta.total_views == 2


def test_tables_summary_endpoint():
    tables = list_tables(schema_name="ENTERPRISE", use_demo=True)
    assert len(tables) == 15
    t_names = [t["name"] for t in tables]
    assert "ORD_HDR" in t_names
    assert "V_ACTIVE_ORDERS" in t_names


def test_single_table_details_endpoint():
    table = get_table_details(table_name="ORD_HDR", schema_name="ENTERPRISE", use_demo=True)
    assert isinstance(table, DbTable)
    assert table.tabname == "ORD_HDR"
    assert len(table.columns) == 8
    assert table.primary_keys == ["ORDER_ID"]


def test_relationships_endpoint():
    rels = get_relationships(schema_name="ENTERPRISE", use_demo=True)
    assert len(rels) >= 10
    # Both declared and inferred relationships present
    declared = [r for r in rels if r.relationship_type.value == "DECLARED"]
    inferred = [r for r in rels if r.relationship_type.value == "INFERRED"]
    assert len(declared) > 0
    assert len(inferred) > 0


def test_analyze_workflow_endpoint():
    req = AnalyzeWorkflowRequest(schema_name="ENTERPRISE", use_demo=True)
    wfs = analyze_workflows(req)
    assert len(wfs) >= 2
    wf_names = [w.name for w in wfs]
    assert any("Order-to-Cash" in name for name in wf_names)


def test_investigate_dependencies_endpoint():
    req = InvestigateDependenciesRequest(target_object="ORD_HDR", schema_name="ENTERPRISE", use_demo=True)
    inv = investigate_dependencies(req)
    assert inv.target_object == "ORD_HDR"
    assert inv.impact_severity in ("HIGH", "CRITICAL")
    assert len(inv.direct_dependencies) > 0


def test_connection_test_failure_on_unreachable_host():
    req = ConnectionTestRequest(
        host="unreachable.db2.example.com",
        port=50000,
        database="SAMPLE",
        username="fake_user",
        password="fake_password",
    )
    res = api_test_connection(req)
    # Must report real failure and never fabricate success
    assert res["success"] is False
