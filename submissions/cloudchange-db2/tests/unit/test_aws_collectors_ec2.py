"""Unit tests for EC2EvidenceCollector."""

from unittest.mock import MagicMock
import pytest
from botocore.exceptions import ClientError

from backend.app.aws.clients import AWSClientFactory
from backend.app.aws.collectors.ec2 import EC2EvidenceCollector
from backend.app.aws.errors import (
    AWSAuthorizationError,
    AWSServiceError,
    ResourceNotFoundError,
    UnsupportedFieldError,
)
from backend.app.aws.schemas import NormalizedEC2Instance
from backend.app.models.evidence import Evidence


def _build_mock_client_error(code: str, message: str = "Test error") -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": message}},
        operation_name="DescribeInstances",
    )


def test_ec2_collector_successful_normalization():
    """Verify DescribeInstances response is correctly normalized into NormalizedEC2Instance."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client

    mock_client.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "InstanceType": "t3.large",
                        "State": {"Code": 16, "Name": "running"},
                        "Placement": {"AvailabilityZone": "us-east-1a"},
                        "EbsOptimized": True,
                        "Monitoring": {"State": "enabled"},
                        "SourceDestCheck": True,
                        "DisableApiTermination": True,
                    }
                ]
            }
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    collector = EC2EvidenceCollector(client_factory=factory)

    normalized = collector.get_normalized_instance("i-0123456789abcdef0", region="us-east-1")

    assert isinstance(normalized, NormalizedEC2Instance)
    assert normalized.instance_id == "i-0123456789abcdef0"
    assert normalized.instance_type == "t3.large"
    assert normalized.state == "running"
    assert normalized.availability_zone == "us-east-1a"
    assert normalized.ebs_optimized is True
    assert normalized.monitoring == "enabled"
    assert normalized.source_dest_check is True
    assert normalized.disable_api_termination is True


def test_ec2_collector_evidence_construction_and_field_extraction():
    """Verify collect() returns machine-readable Evidence without raw Boto3 structures."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client

    mock_client.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-0123456789abcdef0",
                        "InstanceType": "m5.xlarge",
                        "State": {"Code": 16, "Name": "running"},
                        "Placement": {"AvailabilityZone": "us-east-1b"},
                        "EbsOptimized": True,
                        "Monitoring": {"State": "disabled"},
                        "SourceDestCheck": False,
                        "DisableApiTermination": False,
                    }
                ]
            }
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    collector = EC2EvidenceCollector(client_factory=factory)

    # 1. instance_type field
    ev_type = collector.collect(resource_id="i-0123456789abcdef0", field="instance_type", region="us-east-1")
    assert isinstance(ev_type, Evidence)
    assert ev_type.source == "aws.ec2"
    assert ev_type.resource_id == "i-0123456789abcdef0"
    assert ev_type.field == "instance_type"
    assert ev_type.observed_value == "m5.xlarge"
    assert "Reservations" not in ev_type.metadata

    # 2. operational_config field
    ev_config = collector.collect(resource_id="i-0123456789abcdef0", field="operational_config", region="us-east-1")
    assert ev_config.observed_value == {
        "ebs_optimized": True,
        "monitoring": "disabled",
        "source_dest_check": False,
        "disable_api_termination": False,
    }

    # 3. resource_identity field
    ev_id = collector.collect(resource_id="i-0123456789abcdef0", field="resource_identity", region="us-east-1")
    assert ev_id.observed_value == {
        "instance_id": "i-0123456789abcdef0",
        "state": "running",
    }


def test_ec2_collector_resource_not_found():
    """Verify InvalidInstanceID.NotFound raises ResourceNotFoundError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_instances.side_effect = _build_mock_client_error("InvalidInstanceID.NotFound")

    factory = AWSClientFactory(session=mock_session)
    collector = EC2EvidenceCollector(client_factory=factory)

    with pytest.raises(ResourceNotFoundError) as exc_info:
        collector.collect(resource_id="i-missing123", field="instance_type")
    assert exc_info.value.resource_id == "i-missing123"
    assert exc_info.value.resource_type == "EC2 instance"


def test_ec2_collector_empty_reservations_raises_not_found():
    """Verify empty reservations list raises ResourceNotFoundError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_instances.return_value = {"Reservations": []}

    factory = AWSClientFactory(session=mock_session)
    collector = EC2EvidenceCollector(client_factory=factory)

    with pytest.raises(ResourceNotFoundError):
        collector.collect(resource_id="i-empty", field="instance_type")


def test_ec2_collector_authorization_error():
    """Verify UnauthorizedOperation / AccessDenied raises AWSAuthorizationError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_instances.side_effect = _build_mock_client_error("UnauthorizedOperation")

    factory = AWSClientFactory(session=mock_session)
    collector = EC2EvidenceCollector(client_factory=factory)

    with pytest.raises(AWSAuthorizationError):
        collector.collect(resource_id="i-12345", field="instance_type")


def test_ec2_collector_service_error():
    """Verify service/throttling error raises AWSServiceError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_instances.side_effect = _build_mock_client_error("RequestLimitExceeded")

    factory = AWSClientFactory(session=mock_session)
    collector = EC2EvidenceCollector(client_factory=factory)

    with pytest.raises(AWSServiceError):
        collector.collect(resource_id="i-12345", field="instance_type")


def test_ec2_collector_unsupported_field():
    """Verify unsupported field raises UnsupportedFieldError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"InstanceId": "i-123", "InstanceType": "t3.micro"}]}]
    }

    factory = AWSClientFactory(session=mock_session)
    collector = EC2EvidenceCollector(client_factory=factory)

    with pytest.raises(UnsupportedFieldError):
        collector.collect(resource_id="i-123", field="unsupported_quantum_property")
