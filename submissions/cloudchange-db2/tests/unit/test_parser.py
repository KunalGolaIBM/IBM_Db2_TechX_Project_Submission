"""Unit tests for Terraform Plan Parser."""

import json
from pathlib import Path
import pytest

from backend.app.engine.exceptions import PlanValidationError, UnsupportedResourceError
from backend.app.engine.parser import PlanParser, SUPPORTED_RESOURCE_TYPES

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(filename: str) -> dict:
    """Helper to load a fixture JSON file."""
    path = FIXTURES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_parser_valid_plan():
    """Verify parsing a valid plan extracts all raw resource changes."""
    plan = load_fixture("create_ec2.json")
    parser = PlanParser()
    parsed = parser.parse(plan)
    assert len(parsed) == 1
    assert parsed[0]["address"] == "aws_instance.web"
    assert parsed[0]["type"] == "aws_instance"


def test_parser_multiple_supported_resources():
    """Verify parser accepts multiple supported resource types."""
    plan = load_fixture("multiple_resources.json")
    parser = PlanParser()
    parsed = parser.parse(plan)
    assert len(parsed) == 3
    types = [c["type"] for c in parsed]
    assert types == ["aws_instance", "aws_security_group", "aws_db_instance"]


def test_parser_handles_noops():
    """Verify parser safely identifies no-op entries without raising errors."""
    plan = load_fixture("plan_with_noops.json")
    parser = PlanParser()
    parsed = parser.parse(plan)
    assert len(parsed.actionable_changes) == 1
    assert parsed.actionable_changes[0]["address"] == "aws_instance.api_server"
    assert "aws_security_group.default_sg" in parsed.ignored_noops


def test_parser_handles_data_source_reads():
    """Verify parser safely identifies data sources and read actions without raising errors."""
    plan = load_fixture("plan_with_data_sources.json")
    parser = PlanParser()
    parsed = parser.parse(plan)
    assert len(parsed.actionable_changes) == 1
    assert parsed.actionable_changes[0]["address"] == "aws_instance.bastion"
    assert "data.aws_ami.ubuntu" in parsed.ignored_reads


def test_parser_mixed_supported_and_unsupported_resources():
    """Verify parser extracts supported actionable changes and preserves structured warnings for unsupported."""
    plan = load_fixture("plan_mixed_supported_unsupported.json")
    parser = PlanParser()
    parsed = parser.parse(plan)
    
    # 2 supported actionable changes: aws_instance.frontend and aws_security_group.frontend_sg
    assert len(parsed.actionable_changes) == 2
    actionable_addresses = [c["address"] for c in parsed.actionable_changes]
    assert "aws_instance.frontend" in actionable_addresses
    assert "aws_security_group.frontend_sg" in actionable_addresses

    # 2 unsupported resources: aws_s3_bucket.static_assets and aws_vpc.main_network
    assert len(parsed.unsupported_resources) == 2
    warn_addresses = [w.resource_address for w in parsed.unsupported_resources]
    assert "aws_s3_bucket.static_assets" in warn_addresses
    assert "aws_vpc.main_network" in warn_addresses
    assert "Phase 1 supported scope" in parsed.unsupported_resources[0].reason


def test_parser_strict_mode_rejects_unsupported_resource_type():
    """When strict_supported_only is True, parser raises UnsupportedResourceError."""
    plan = load_fixture("unsupported_resource_s3.json")
    parser = PlanParser()
    with pytest.raises(UnsupportedResourceError) as exc_info:
        parser.parse(plan, strict_supported_only=True)

    err = exc_info.value
    assert err.resource_type == "aws_s3_bucket"
    assert err.resource_address == "aws_s3_bucket.data_archive"
    assert set(err.supported_types) == SUPPORTED_RESOURCE_TYPES
    assert "Phase 1 strictly supports" in str(err)


def test_parser_default_mode_warns_on_unsupported_resource_type():
    """When strict_supported_only is False (default), parser records structured warning."""
    plan = load_fixture("unsupported_resource_s3.json")
    parser = PlanParser()
    parsed = parser.parse(plan)
    assert len(parsed.actionable_changes) == 0
    assert len(parsed.unsupported_resources) == 1
    assert parsed.unsupported_resources[0].resource_address == "aws_s3_bucket.data_archive"


def test_parser_rejects_non_dict_plan():
    """Parser must reject non-dictionary inputs cleanly."""
    parser = PlanParser()
    with pytest.raises(PlanValidationError, match="must be a JSON object"):
        parser.parse(["not", "a", "dict"])


def test_parser_rejects_missing_format_version():
    """Parser must reject plan missing format_version."""
    parser = PlanParser()
    with pytest.raises(PlanValidationError, match="format_version"):
        parser.parse({"resource_changes": []})


def test_parser_rejects_missing_resource_changes():
    """Parser must reject plan missing resource_changes array."""
    plan = load_fixture("malformed_plan.json")
    parser = PlanParser()
    with pytest.raises(PlanValidationError, match="resource_changes"):
        parser.parse(plan)


def test_parser_rejects_malformed_resource_item():
    """Parser must reject resource items missing required fields."""
    parser = PlanParser()
    
    # Missing address
    with pytest.raises(PlanValidationError, match="address"):
        parser.parse({
            "format_version": "1.2",
            "resource_changes": [{"type": "aws_instance"}]
        })

    # Missing type
    with pytest.raises(PlanValidationError, match="type"):
        parser.parse({
            "format_version": "1.2",
            "resource_changes": [{"address": "aws_instance.web"}]
        })

    # Missing change object
    with pytest.raises(PlanValidationError, match="change"):
        parser.parse({
            "format_version": "1.2",
            "resource_changes": [{
                "address": "aws_instance.web",
                "type": "aws_instance"
            }]
        })

    # Missing change.actions
    with pytest.raises(PlanValidationError, match="actions"):
        parser.parse({
            "format_version": "1.2",
            "resource_changes": [{
                "address": "aws_instance.web",
                "type": "aws_instance",
                "change": {}
            }]
        })
