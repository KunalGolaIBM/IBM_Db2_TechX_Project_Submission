"""DBA tool templates: static safety invariants and parameter validation."""

from __future__ import annotations

import re

import pytest
import sqlglot

from app.core.config import Settings
from app.dba.specs import (
    MAX_LIMIT,
    TOOLS,
    TOOLS_BY_ID,
    ToolParamError,
    resolve_params,
)

SETTINGS = Settings(_env_file=None)


def test_tool_ids_are_unique_and_namespaced():
    ids = [t.id for t in TOOLS]
    assert len(ids) == len(set(ids)) == len(TOOLS_BY_ID)
    assert all(re.fullmatch(r"(catalog|monitor)\.[a-z_]+", i) for i in ids)
    assert {t.kind for t in TOOLS} == {"catalog", "monitoring"}
    assert sum(t.kind == "catalog" for t in TOOLS) >= 5
    assert sum(t.kind == "monitoring" for t in TOOLS) >= 5


@pytest.mark.parametrize("spec", TOOLS, ids=lambda s: s.id)
def test_template_is_one_read_only_parameterized_select(spec):
    sql = spec.render(10)
    assert "{" not in sql and "}" not in sql
    assert ";" not in sql
    assert sql.lstrip().upper().startswith("SELECT")
    # Exactly one ? marker per bound name, in order.
    assert sql.count("?") == len(spec.bind)
    for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE ", "CALL "):
        assert forbidden not in sql.upper()
    # Row-bounded by construction.
    assert "FETCH FIRST 10 ROWS ONLY" in sql
    # Parses as a single SELECT in a generic dialect.
    tree = sqlglot.parse_one(sql, read="db2") if "db2" in sqlglot.Dialect.classes else sqlglot.parse_one(sql)
    assert tree is not None


@pytest.mark.parametrize("spec", TOOLS, ids=lambda s: s.id)
def test_bound_names_are_declared_params(spec):
    declared = {p.name for p in spec.params}
    assert set(spec.bind) <= declared
    assert ("limit" in declared) == spec.uses_limit


@pytest.mark.parametrize("spec", TOOLS, ids=lambda s: s.id)
def test_only_catalog_and_monitor_objects_are_referenced(spec):
    sql = spec.sql.upper()
    if spec.kind == "catalog":
        assert "SYSCAT." in sql and "MON_GET_" not in sql
    else:
        assert "MON_GET_" in sql


def test_render_clamps_and_validates_limit():
    spec = TOOLS_BY_ID["catalog.tables"]
    assert "FETCH FIRST 100 ROWS ONLY" in spec.render(10_000)
    assert "FETCH FIRST 1 ROWS ONLY" in spec.render(0)
    with pytest.raises(ToolParamError):
        spec.render("5; DROP TABLE X")  # type: ignore[arg-type]
    with pytest.raises(ToolParamError):
        spec.render(True)  # type: ignore[arg-type]


# -- parameter resolution --------------------------------------------------------
def test_defaults_use_application_schema_and_default_limit():
    resolved = resolve_params(TOOLS_BY_ID["catalog.tables"], None, SETTINGS)
    assert resolved.bound == ("APP",)
    assert resolved.limit == SETTINGS.dba_default_limit
    assert resolved.applied == {"schema": "APP", "limit": SETTINGS.dba_default_limit}


def test_identifiers_are_uppercased_and_trimmed():
    resolved = resolve_params(
        TOOLS_BY_ID["catalog.columns"],
        {"schema": " app ", "table": "demo_servers", "limit": 5},
        SETTINGS,
    )
    assert resolved.bound == ("APP", "DEMO_SERVERS")
    assert resolved.limit == 5


@pytest.mark.parametrize(
    "bad",
    [
        "T; DROP TABLE X",
        "T' OR '1'='1",
        "T--",
        "A B",
        "a.b",
        '"quoted"',
        "",
        "1TABLE",
        "x" * 129,
        "T\nDROP",
    ],
)
def test_injection_shaped_identifiers_are_rejected(bad):
    with pytest.raises(ToolParamError):
        resolve_params(TOOLS_BY_ID["catalog.columns"], {"table": bad}, SETTINGS)


@pytest.mark.parametrize("schema", ["SYSCAT", "sysibm", "SYSTOOLS", "SYSPROC", "NULLID", "SQLJ"])
def test_system_schemas_are_refused(schema):
    with pytest.raises(ToolParamError):
        resolve_params(TOOLS_BY_ID["catalog.tables"], {"schema": schema}, SETTINGS)


def test_table_is_required_where_declared():
    with pytest.raises(ToolParamError):
        resolve_params(TOOLS_BY_ID["catalog.indexes"], {}, SETTINGS)


def test_unknown_params_are_rejected_with_allowed_list():
    with pytest.raises(ToolParamError) as excinfo:
        resolve_params(TOOLS_BY_ID["catalog.tables"], {"where": "1=1"}, SETTINGS)
    assert excinfo.value.detail["unknown"] == ["where"]
    assert "limit" in excinfo.value.detail["allowed"]


@pytest.mark.parametrize("limit", [0, -1, MAX_LIMIT + 1, "5", 1.5, True, [1]])
def test_limit_must_be_a_bounded_integer(limit):
    with pytest.raises(ToolParamError):
        resolve_params(TOOLS_BY_ID["catalog.tables"], {"limit": limit}, SETTINGS)


def test_param_not_declared_for_tool_is_rejected():
    # monitor.slow_statements has no schema/table parameters.
    with pytest.raises(ToolParamError):
        resolve_params(TOOLS_BY_ID["monitor.slow_statements"], {"schema": "APP"}, SETTINGS)
