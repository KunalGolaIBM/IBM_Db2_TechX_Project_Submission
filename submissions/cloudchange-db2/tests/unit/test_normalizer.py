"""Unit tests for Change Normalizer."""

import json
from pathlib import Path
import pytest

from backend.app.engine.exceptions import InvalidActionError, UnsupportedResourceError
from backend.app.engine.normalizer import ChangeNormalizer, parse_and_normalize
from backend.app.models.change import ActionType

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def load_fixture(filename: str) -> dict:
    """Helper to load a fixture JSON file."""
    path = FIXTURES_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_normalize_action_mappings():
    """Verify exact action array mappings."""
    norm = ChangeNormalizer()
    assert norm.normalize_action(["create"]) == ActionType.CREATE
    assert norm.normalize_action(["update"]) == ActionType.UPDATE
    assert norm.normalize_action(["delete"]) == ActionType.DELETE
    assert norm.normalize_action(["delete", "create"]) == ActionType.REPLACE
    assert norm.normalize_action(["create", "delete"]) == ActionType.REPLACE


def test_normalize_action_rejections():
    """Verify invalid or non-actionable action arrays are rejected by normalize_action."""
    norm = ChangeNormalizer()
    with pytest.raises(InvalidActionError):
        norm.normalize_action(["no-op"])
    with pytest.raises(InvalidActionError):
        norm.normalize_action(["read"])
    with pytest.raises(InvalidActionError):
        norm.normalize_action([])
    with pytest.raises(InvalidActionError):
        norm.normalize_action(["create", "update"])


def test_normalize_create_ec2():
    """Test normalization of create action fixture."""
    plan = load_fixture("create_ec2.json")
    result = parse_and_normalize(plan)
    assert len(result) == 1
    c = result[0]
    assert c.resource_address == "aws_instance.web"
    assert c.resource_type == "aws_instance"
    assert c.action == ActionType.CREATE
    assert c.before is None
    assert c.after is not None
    assert c.after["instance_type"] == "t3.micro"
    assert c.requires_replacement is False
    assert len(c.diffs) > 0


def test_normalize_update_ec2():
    """Test normalization of update action fixture and diff calculation."""
    plan = load_fixture("update_ec2_instance_type.json")
    result = parse_and_normalize(plan)
    assert len(result) == 1
    c = result[0]
    assert c.resource_address == "aws_instance.api"
    assert c.action == ActionType.UPDATE
    assert c.before["instance_type"] == "t3.medium"
    assert c.after["instance_type"] == "t3.large"
    assert c.requires_replacement is False

    # Check attribute diffs
    diff_map = {d.path: d for d in c.diffs}
    assert "instance_type" in diff_map
    assert diff_map["instance_type"].before == "t3.medium"
    assert diff_map["instance_type"].after == "t3.large"
    assert diff_map["monitoring"].before is False
    assert diff_map["monitoring"].after is True


def test_normalize_delete_rds():
    """Test normalization of delete action fixture."""
    plan = load_fixture("delete_rds.json")
    result = parse_and_normalize(plan)
    assert len(result) == 1
    c = result[0]
    assert c.resource_address == "aws_db_instance.database"
    assert c.action == ActionType.DELETE
    assert c.before is not None
    assert c.before["identifier"] == "production-db"
    assert c.after is None
    assert c.requires_replacement is False


def test_normalize_replace_rds():
    """Test normalization of replacement action fixture with replace_paths."""
    plan = load_fixture("replace_rds.json")
    result = parse_and_normalize(plan)
    assert len(result) == 1
    c = result[0]
    assert c.resource_address == "aws_db_instance.db"
    assert c.action == ActionType.REPLACE
    assert c.before["identifier"] == "old-db-name"
    assert c.after["identifier"] == "new-db-name"
    assert c.requires_replacement is True


def test_normalize_replace_create_delete_order():
    """Test replacement action where order is ['create', 'delete']."""
    plan = load_fixture("replace_create_delete.json")
    result = parse_and_normalize(plan)
    assert len(result) == 1
    c = result[0]
    assert c.resource_address == "aws_instance.worker"
    assert c.action == ActionType.REPLACE
    assert c.requires_replacement is True


def test_normalize_multiple_resources():
    """Test plan with multiple distinct resources."""
    plan = load_fixture("multiple_resources.json")
    result = parse_and_normalize(plan)
    assert len(result) == 3

    addr_map = {c.resource_address: c for c in result}
    assert addr_map["aws_instance.app"].action == ActionType.CREATE
    assert addr_map["aws_security_group.app_sg"].action == ActionType.UPDATE
    assert addr_map["aws_db_instance.app_db"].action == ActionType.REPLACE


def test_normalize_nested_attribute_sg():
    """Test nested attribute diffs for security group ingress rule."""
    plan = load_fixture("nested_attribute_sg.json")
    result = parse_and_normalize(plan)
    assert len(result) == 1
    c = result[0]
    assert c.action == ActionType.UPDATE

    diff_map = {d.path: d for d in c.diffs}
    assert "ingress[0].cidr_blocks" in diff_map
    assert diff_map["ingress[0].cidr_blocks"].before == ["10.0.0.0/16"]
    assert diff_map["ingress[0].cidr_blocks"].after == ["0.0.0.0/0"]


def test_normalize_null_and_missing_values():
    """Test handling of null/missing values in attributes."""
    plan = load_fixture("null_values_change.json")
    result = parse_and_normalize(plan)
    assert len(result) == 1
    c = result[0]
    assert c.action == ActionType.CREATE
    assert c.before is None
    assert c.after["user_data"] is None


def test_normalize_plan_with_noops():
    """Test plan containing both actionable changes and unchanged (no-op) resources."""
    plan = load_fixture("plan_with_noops.json")
    result = parse_and_normalize(plan)
    
    # Exactly 1 actionable change
    assert len(result.changes) == 1
    assert result.changes[0].resource_address == "aws_instance.api_server"
    assert result.changes[0].action == ActionType.UPDATE

    # Unchanged resource recorded in ignored_noops
    assert "aws_security_group.default_sg" in result.ignored_noops


def test_normalize_plan_with_data_sources():
    """Test plan containing actionable changes and read-only data sources."""
    plan = load_fixture("plan_with_data_sources.json")
    result = parse_and_normalize(plan)

    # Exactly 1 actionable change
    assert len(result.changes) == 1
    assert result.changes[0].resource_address == "aws_instance.bastion"
    assert result.changes[0].action == ActionType.CREATE

    # Data source recorded in ignored_reads
    assert "data.aws_ami.ubuntu" in result.ignored_reads


def test_normalize_mixed_supported_and_unsupported():
    """Test mixed plan with supported resources and unsupported resources."""
    plan = load_fixture("plan_mixed_supported_unsupported.json")
    result = parse_and_normalize(plan)

    # 2 supported actionable changes analyzed
    assert len(result.changes) == 2
    addresses = [c.resource_address for c in result.changes]
    assert "aws_instance.frontend" in addresses
    assert "aws_security_group.frontend_sg" in addresses

    # 2 unsupported resources captured with explicit warnings
    assert len(result.unsupported_resources) == 2
    warned = {w.resource_address: w.resource_type for w in result.unsupported_resources}
    assert warned["aws_s3_bucket.static_assets"] == "aws_s3_bucket"
    assert warned["aws_vpc.main_network"] == "aws_vpc"


def test_normalize_pure_noops_plan():
    """Test plan containing only unchanged resources."""
    plan = load_fixture("plan_pure_noops.json")
    result = parse_and_normalize(plan)
    assert len(result.changes) == 0
    assert len(result.ignored_noops) == 1
    assert result.ignored_noops[0] == "aws_instance.existing_server"


def test_normalize_pure_reads_plan():
    """Test plan containing only data source read entries."""
    plan = load_fixture("plan_pure_reads.json")
    result = parse_and_normalize(plan)
    assert len(result.changes) == 0
    assert len(result.ignored_reads) == 1
    assert result.ignored_reads[0] == "data.aws_vpc.selected"


def test_normalize_mixed_plan_strict_mode():
    """Test that strict mode still raises UnsupportedResourceError when requested."""
    plan = load_fixture("plan_mixed_supported_unsupported.json")
    with pytest.raises(UnsupportedResourceError, match="aws_s3_bucket"):
        parse_and_normalize(plan, strict_supported_only=True)
