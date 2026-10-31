"""Unit tests for SGEvidenceCollector."""

from unittest.mock import MagicMock
import pytest
from botocore.exceptions import ClientError

from backend.app.aws.clients import AWSClientFactory
from backend.app.aws.collectors.security_group import SGEvidenceCollector
from backend.app.aws.errors import (
    AWSAuthorizationError,
    AWSServiceError,
    ResourceNotFoundError,
    UnsupportedFieldError,
)
from backend.app.aws.schemas import NormalizedSecurityGroup
from backend.app.models.evidence import Evidence


def _build_mock_client_error(code: str, message: str = "Test error") -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": message}},
        operation_name="DescribeSecurityGroups",
    )


def test_sg_collector_successful_normalization_multiple_rules():
    """Verify DescribeSecurityGroups response normalizes multiple permissions and CIDRs."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client

    mock_client.describe_security_groups.return_value = {
        "SecurityGroups": [
            {
                "GroupId": "sg-0123456789abcdef0",
                "GroupName": "web-tier-sg",
                "VpcId": "vpc-01234567",
                "IpPermissions": [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 80,
                        "ToPort": 80,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}, {"CidrIp": "10.0.0.0/8"}],
                        "Ipv6Ranges": [{"CidrIpv6": "::/0"}],
                    },
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 22,
                        "ToPort": 22,
                        "IpRanges": [{"CidrIp": "192.168.1.0/24"}],
                    },
                    {
                        "IpProtocol": "-1",
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    },
                ],
            }
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    collector = SGEvidenceCollector(client_factory=factory)

    norm = collector.get_normalized_security_group("sg-0123456789abcdef0", region="us-east-1")

    assert isinstance(norm, NormalizedSecurityGroup)
    assert norm.group_id == "sg-0123456789abcdef0"
    assert norm.group_name == "web-tier-sg"
    assert norm.vpc_id == "vpc-01234567"

    # Rules translation:
    # 1. tcp 80 (0.0.0.0/0, 10.0.0.0/8, ::/0) -> 3 rules
    # 2. tcp 22 (192.168.1.0/24) -> 1 rule
    # 3. -1 all (0.0.0.0/0) -> 1 rule
    # Total = 5 normalized ingress rules
    assert len(norm.ip_permissions) == 5

    # Check port 80 IPv4
    rule80 = next(r for r in norm.ip_permissions if r.from_port == 80 and r.cidr == "0.0.0.0/0")
    assert rule80.protocol == "tcp"
    assert rule80.to_port == 80

    # Check port 80 IPv6
    rule80_v6 = next(r for r in norm.ip_permissions if r.from_port == 80 and r.cidr == "::/0")
    assert rule80_v6.protocol == "tcp"

    # Check protocol -1
    rule_all = next(r for r in norm.ip_permissions if r.protocol == "-1")
    assert rule_all.from_port is None
    assert rule_all.to_port is None
    assert rule_all.cidr == "0.0.0.0/0"


def test_sg_collector_evidence_construction():
    """Verify collect() returns machine-readable Evidence for IpPermissions."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client

    mock_client.describe_security_groups.return_value = {
        "SecurityGroups": [
            {
                "GroupId": "sg-12345",
                "GroupName": "api-sg",
                "VpcId": "vpc-999",
                "IpPermissions": [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 443,
                        "ToPort": 443,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    }
                ],
            }
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    collector = SGEvidenceCollector(client_factory=factory)

    evidence = collector.collect(resource_id="sg-12345", field="IpPermissions", region="us-east-1")

    assert isinstance(evidence, Evidence)
    assert evidence.source == "aws.ec2.security_group"
    assert evidence.resource_id == "sg-12345"
    assert evidence.field == "IpPermissions"
    assert evidence.observed_value == [
        {"protocol": "tcp", "from_port": 443, "to_port": 443, "cidr": "0.0.0.0/0"}
    ]
    # No raw boto3 wrapper leaked
    assert "SecurityGroups" not in evidence.metadata


def test_sg_collector_resource_not_found():
    """Verify InvalidGroup.NotFound raises ResourceNotFoundError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_security_groups.side_effect = _build_mock_client_error("InvalidGroup.NotFound")

    factory = AWSClientFactory(session=mock_session)
    collector = SGEvidenceCollector(client_factory=factory)

    with pytest.raises(ResourceNotFoundError) as exc_info:
        collector.collect(resource_id="sg-nonexistent", field="IpPermissions")
    assert exc_info.value.resource_id == "sg-nonexistent"
    assert exc_info.value.resource_type == "Security Group"


def test_sg_collector_authorization_error():
    """Verify AccessDenied raises AWSAuthorizationError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_security_groups.side_effect = _build_mock_client_error("AccessDenied")

    factory = AWSClientFactory(session=mock_session)
    collector = SGEvidenceCollector(client_factory=factory)

    with pytest.raises(AWSAuthorizationError):
        collector.collect(resource_id="sg-12345", field="IpPermissions")


def test_sg_collector_unsupported_field():
    """Verify unsupported field raises UnsupportedFieldError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_security_groups.return_value = {
        "SecurityGroups": [{"GroupId": "sg-123", "GroupName": "test", "IpPermissions": []}]
    }

    factory = AWSClientFactory(session=mock_session)
    collector = SGEvidenceCollector(client_factory=factory)

    with pytest.raises(UnsupportedFieldError):
        collector.collect(resource_id="sg-123", field="unsupported_subfield")
