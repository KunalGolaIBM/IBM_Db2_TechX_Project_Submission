"""Unit tests for Normalized AWS Evidence Schemas."""

import pytest
from pydantic import ValidationError

from backend.app.aws.schemas import (
    NormalizedEC2Instance,
    NormalizedIngressRule,
    NormalizedRDSInstance,
    NormalizedSecurityGroup,
)


def test_valid_ec2_instance_schema():
    """Verify valid NormalizedEC2Instance construction."""
    instance = NormalizedEC2Instance(
        instance_id="i-0123456789abcdef0",
        instance_type="t3.large",
        state="running",
        availability_zone="us-east-1a",
        ebs_optimized=True,
        monitoring="enabled",
        source_dest_check=True,
        disable_api_termination=False,
    )
    assert instance.instance_id == "i-0123456789abcdef0"
    assert instance.instance_type == "t3.large"
    assert instance.state == "running"
    assert instance.availability_zone == "us-east-1a"
    assert instance.ebs_optimized is True
    assert instance.monitoring == "enabled"
    assert instance.source_dest_check is True
    assert instance.disable_api_termination is False


def test_ec2_instance_schema_required_fields():
    """Verify NormalizedEC2Instance rejects missing required fields."""
    with pytest.raises(ValidationError):
        NormalizedEC2Instance(
            instance_id="i-0123456789abcdef0",
            # missing instance_type, state, availability_zone, etc.
        )


def test_valid_ingress_rule_schema():
    """Verify NormalizedIngressRule with both explicit and default optional fields."""
    # Explicit ports
    rule_explicit = NormalizedIngressRule(
        protocol="tcp",
        from_port=80,
        to_port=80,
        cidr="0.0.0.0/0",
    )
    assert rule_explicit.protocol == "tcp"
    assert rule_explicit.from_port == 80
    assert rule_explicit.to_port == 80
    assert rule_explicit.cidr == "0.0.0.0/0"

    # Optional ports defaulting to None (e.g. all traffic)
    rule_defaults = NormalizedIngressRule(
        protocol="-1",
        cidr="10.0.0.0/16",
    )
    assert rule_defaults.protocol == "-1"
    assert rule_defaults.from_port is None
    assert rule_defaults.to_port is None
    assert rule_defaults.cidr == "10.0.0.0/16"


def test_ingress_rule_schema_required_fields():
    """Verify NormalizedIngressRule rejects missing required fields."""
    with pytest.raises(ValidationError):
        NormalizedIngressRule(
            protocol="tcp",
            # missing cidr
        )


def test_valid_security_group_schema():
    """Verify NormalizedSecurityGroup with nested rules and optional vpc_id."""
    rule = NormalizedIngressRule(
        protocol="tcp",
        from_port=443,
        to_port=443,
        cidr="0.0.0.0/0",
    )
    sg_with_vpc = NormalizedSecurityGroup(
        group_id="sg-0123456789abcdef0",
        group_name="web-sg",
        vpc_id="vpc-12345678",
        ip_permissions=[rule],
    )
    assert sg_with_vpc.group_id == "sg-0123456789abcdef0"
    assert sg_with_vpc.group_name == "web-sg"
    assert sg_with_vpc.vpc_id == "vpc-12345678"
    assert len(sg_with_vpc.ip_permissions) == 1
    assert sg_with_vpc.ip_permissions[0].from_port == 443

    # Default vpc_id is None
    sg_no_vpc = NormalizedSecurityGroup(
        group_id="sg-9876543210abcdef0",
        group_name="default-sg",
        ip_permissions=[],
    )
    assert sg_no_vpc.vpc_id is None
    assert sg_no_vpc.ip_permissions == []


def test_security_group_schema_required_fields():
    """Verify NormalizedSecurityGroup rejects missing required fields."""
    with pytest.raises(ValidationError):
        NormalizedSecurityGroup(
            group_id="sg-0123456789abcdef0",
            # missing group_name and ip_permissions
        )


def test_valid_rds_instance_schema():
    """Verify NormalizedRDSInstance with both explicit and default optional fields."""
    # With KMS key
    rds_encrypted = NormalizedRDSInstance(
        db_instance_identifier="prod-db",
        dbi_resource_id="db-ABCDEF123456",
        instance_class="db.r5.xlarge",
        status="available",
        allocated_storage=200,
        storage_type="gp3",
        storage_encrypted=True,
        kms_key_id="arn:aws:kms:us-east-1:123456789012:key/abc-123",
    )
    assert rds_encrypted.db_instance_identifier == "prod-db"
    assert rds_encrypted.dbi_resource_id == "db-ABCDEF123456"
    assert rds_encrypted.instance_class == "db.r5.xlarge"
    assert rds_encrypted.status == "available"
    assert rds_encrypted.allocated_storage == 200
    assert rds_encrypted.storage_type == "gp3"
    assert rds_encrypted.storage_encrypted is True
    assert rds_encrypted.kms_key_id == "arn:aws:kms:us-east-1:123456789012:key/abc-123"

    # Without KMS key (optional default None)
    rds_unencrypted = NormalizedRDSInstance(
        db_instance_identifier="dev-db",
        dbi_resource_id="db-XYZ987654321",
        instance_class="db.t3.micro",
        status="available",
        allocated_storage=20,
        storage_type="gp2",
        storage_encrypted=False,
    )
    assert rds_unencrypted.kms_key_id is None
    assert rds_unencrypted.storage_encrypted is False


def test_rds_instance_schema_required_fields():
    """Verify NormalizedRDSInstance rejects missing required fields."""
    with pytest.raises(ValidationError):
        NormalizedRDSInstance(
            db_instance_identifier="prod-db",
            # missing dbi_resource_id, instance_class, status, allocated_storage, storage_type, storage_encrypted
        )
