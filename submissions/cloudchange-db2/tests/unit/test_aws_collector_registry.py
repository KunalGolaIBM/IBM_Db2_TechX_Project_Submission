"""Unit tests for EvidenceCollectorRegistry."""

from unittest.mock import MagicMock
import pytest

from backend.app.aws.clients import AWSClientFactory
from backend.app.aws.collectors.ec2 import EC2EvidenceCollector
from backend.app.aws.collectors.rds import RDSEvidenceCollector
from backend.app.aws.collectors.registry import EvidenceCollectorRegistry
from backend.app.aws.collectors.security_group import SGEvidenceCollector
from backend.app.aws.errors import UnsupportedResourceTypeError
from backend.app.models.evidence import Evidence


def test_registry_resolves_all_three_resource_types():
    """Verify registry maps standard Terraform resource types to correct collectors."""
    registry = EvidenceCollectorRegistry()

    ec2_col = registry.get_collector("aws_instance")
    assert isinstance(ec2_col, EC2EvidenceCollector)

    sg_col = registry.get_collector("aws_security_group")
    assert isinstance(sg_col, SGEvidenceCollector)

    rds_col = registry.get_collector("aws_db_instance")
    assert isinstance(rds_col, RDSEvidenceCollector)


def test_registry_resolves_common_aliases():
    """Verify registry maps shorthand / service aliases appropriately."""
    registry = EvidenceCollectorRegistry()

    assert isinstance(registry.get_collector("instance"), EC2EvidenceCollector)
    assert isinstance(registry.get_collector("ec2"), EC2EvidenceCollector)
    assert isinstance(registry.get_collector("security_group"), SGEvidenceCollector)
    assert isinstance(registry.get_collector("sg"), SGEvidenceCollector)
    assert isinstance(registry.get_collector("db_instance"), RDSEvidenceCollector)
    assert isinstance(registry.get_collector("rds"), RDSEvidenceCollector)


def test_registry_resolves_service_and_resource_type_pairs():
    """Verify get_collector_for_service matching EvidenceRequirement properties."""
    registry = EvidenceCollectorRegistry()

    assert isinstance(registry.get_collector_for_service("ec2", "instance"), EC2EvidenceCollector)
    assert isinstance(registry.get_collector_for_service("ec2", "security_group"), SGEvidenceCollector)
    assert isinstance(registry.get_collector_for_service("rds", "db_instance"), RDSEvidenceCollector)


def test_registry_unsupported_resource_type_raises():
    """Verify unsupported resource type raises UnsupportedResourceTypeError."""
    registry = EvidenceCollectorRegistry()

    with pytest.raises(UnsupportedResourceTypeError):
        registry.get_collector("aws_lambda_function")

    with pytest.raises(UnsupportedResourceTypeError):
        registry.get_collector_for_service("lambda", "function")


def test_registry_collect_delegation():
    """Verify registry.collect delegates to the underlying collector."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_instances.return_value = {
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-999",
                        "InstanceType": "c5.large",
                        "State": {"Name": "running"},
                    }
                ]
            }
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    registry = EvidenceCollectorRegistry(client_factory=factory)

    evidence = registry.collect(
        resource_type="aws_instance",
        resource_id="i-999",
        field="instance_type",
        region="us-west-2",
    )

    assert isinstance(evidence, Evidence)
    assert evidence.resource_id == "i-999"
    assert evidence.observed_value == "c5.large"
    mock_session.client.assert_called_with("ec2", region_name="us-west-2")
