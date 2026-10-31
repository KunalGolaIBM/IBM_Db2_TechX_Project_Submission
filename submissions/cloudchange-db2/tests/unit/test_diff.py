"""Unit tests for Attribute Difference Engine."""

from backend.app.engine.diff import compute_attribute_diffs


def test_diff_creation():
    """Creation should generate diffs for all keys with before=None."""
    after = {"ami": "ami-12345", "instance_type": "t3.micro"}
    diffs = compute_attribute_diffs(None, after)
    assert len(diffs) == 2
    paths = {d.path: d for d in diffs}
    assert paths["ami"].before is None
    assert paths["ami"].after == "ami-12345"
    assert paths["instance_type"].before is None
    assert paths["instance_type"].after == "t3.micro"


def test_diff_deletion():
    """Deletion should generate diffs for all keys with after=None."""
    before = {"allocated_storage": 100, "identifier": "production-db"}
    diffs = compute_attribute_diffs(before, None)
    assert len(diffs) == 2
    paths = {d.path: d for d in diffs}
    assert paths["allocated_storage"].before == 100
    assert paths["allocated_storage"].after is None
    assert paths["identifier"].before == "production-db"
    assert paths["identifier"].after is None


def test_diff_no_changes():
    """Identical before and after should produce no diffs."""
    state = {"ami": "ami-123", "instance_type": "t3.medium"}
    diffs = compute_attribute_diffs(state, state.copy())
    assert diffs == []


def test_diff_simple_update():
    """Single attribute modification should produce a single diff."""
    before = {"ami": "ami-123", "instance_type": "t3.medium"}
    after = {"ami": "ami-123", "instance_type": "t3.large"}
    diffs = compute_attribute_diffs(before, after)
    assert len(diffs) == 1
    assert diffs[0].path == "instance_type"
    assert diffs[0].before == "t3.medium"
    assert diffs[0].after == "t3.large"


def test_diff_nested_dictionary():
    """Nested dictionary changes should use dot notation."""
    before = {"tags": {"Environment": "dev", "Owner": "team-a"}}
    after = {"tags": {"Environment": "prod", "Owner": "team-a"}}
    diffs = compute_attribute_diffs(before, after)
    assert len(diffs) == 1
    assert diffs[0].path == "tags.Environment"
    assert diffs[0].before == "dev"
    assert diffs[0].after == "prod"


def test_diff_nested_list_of_dicts():
    """List of dictionaries (like security group ingress) should produce bracket indexed paths."""
    before = {
        "ingress": [
            {
                "from_port": 22,
                "to_port": 22,
                "protocol": "tcp",
                "cidr_blocks": ["10.0.0.0/16"]
            }
        ]
    }
    after = {
        "ingress": [
            {
                "from_port": 22,
                "to_port": 22,
                "protocol": "tcp",
                "cidr_blocks": ["0.0.0.0/0"]
            }
        ]
    }
    diffs = compute_attribute_diffs(before, after)
    assert len(diffs) == 1
    assert diffs[0].path == "ingress[0].cidr_blocks"
    assert diffs[0].before == ["10.0.0.0/16"]
    assert diffs[0].after == ["0.0.0.0/0"]


def test_diff_added_and_removed_keys():
    """Attributes added or removed should be detected."""
    before = {"monitoring": False}
    after = {"monitoring": False, "ebs_optimized": True}
    diffs = compute_attribute_diffs(before, after)
    assert len(diffs) == 1
    assert diffs[0].path == "ebs_optimized"
    assert diffs[0].before is None
    assert diffs[0].after is True
