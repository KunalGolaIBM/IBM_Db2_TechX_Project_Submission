"""Unit tests for StateIdentityResolver hardening."""

from backend.app.aws.identity import StateIdentityResolver


def test_resolver_standard_managed_resources():
    """Verify parsing of standard managed resources across types."""
    resolver = StateIdentityResolver()
    state_json = {
        "version": 4,
        "terraform_version": "1.7.0",
        "resources": [
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "web",
                "provider": "provider[\"registry.terraform.io/hashicorp/aws\"]",
                "instances": [
                    {
                        "schema_version": 1,
                        "attributes": {
                            "id": "i-0123456789abcdef0",
                            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-0123456789abcdef0",
                        },
                    }
                ],
            },
            {
                "mode": "managed",
                "type": "aws_security_group",
                "name": "web_sg",
                "instances": [
                    {
                        "attributes": {
                            "id": "sg-999888777",
                        },
                    }
                ],
            },
            {
                "mode": "managed",
                "type": "aws_db_instance",
                "name": "postgres",
                "instances": [
                    {
                        "attributes": {
                            "identifier": "db-prod-master",
                        },
                    }
                ],
            },
        ],
    }

    identities = resolver.resolve_identities(state_json)

    assert len(identities) == 3
    assert "aws_instance.web" in identities
    assert identities["aws_instance.web"].resource_id == "i-0123456789abcdef0"
    assert identities["aws_instance.web"].resource_type == "aws_instance"

    assert "aws_security_group.web_sg" in identities
    assert identities["aws_security_group.web_sg"].resource_id == "sg-999888777"

    assert "aws_db_instance.postgres" in identities
    assert identities["aws_db_instance.postgres"].resource_id == "db-prod-master"


def test_resolver_ignores_data_sources():
    """Verify data sources (mode='data') are excluded from physical identity resolution."""
    resolver = StateIdentityResolver()
    state_json = {
        "resources": [
            {
                "mode": "data",
                "type": "aws_ami",
                "name": "ubuntu",
                "instances": [{"attributes": {"id": "ami-0123456"}}],
            },
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "worker",
                "instances": [{"attributes": {"id": "i-worker-1"}}],
            },
        ]
    }

    identities = resolver.resolve_identities(state_json)
    assert len(identities) == 1
    assert "aws_ami.ubuntu" not in identities
    assert "aws_instance.worker" in identities


def test_resolver_handles_empty_or_malformed_state():
    """Verify empty or missing fields do not cause exceptions."""
    resolver = StateIdentityResolver()

    # Empty dict
    assert resolver.resolve_identities({}) == {}

    # State with empty resources
    assert resolver.resolve_identities({"resources": []}) == {}

    # Resource with no instances
    state_no_inst = {
        "resources": [{"mode": "managed", "type": "aws_instance", "name": "web", "instances": []}]
    }
    assert resolver.resolve_identities(state_no_inst) == {}

    # Resource with instance lacking id or identifier
    state_no_id = {
        "resources": [
            {
                "mode": "managed",
                "type": "aws_instance",
                "name": "web",
                "instances": [{"attributes": {"tags": {"Name": "web"}}}],
            }
        ]
    }
    assert resolver.resolve_identities(state_no_id) == {}
