"""Unit tests for RDSEvidenceCollector."""

from unittest.mock import MagicMock
import pytest
from botocore.exceptions import ClientError

from backend.app.aws.clients import AWSClientFactory
from backend.app.aws.collectors.rds import RDSEvidenceCollector
from backend.app.aws.errors import (
    AWSAuthorizationError,
    AWSServiceError,
    ResourceNotFoundError,
    UnsupportedFieldError,
)
from backend.app.aws.schemas import NormalizedRDSInstance
from backend.app.models.evidence import Evidence


def _build_mock_client_error(code: str, message: str = "Test error") -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": message}},
        operation_name="DescribeDBInstances",
    )


def test_rds_collector_successful_normalization():
    """Verify DescribeDBInstances response normalizes into NormalizedRDSInstance."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client

    mock_client.describe_db_instances.return_value = {
        "DBInstances": [
            {
                "DBInstanceIdentifier": "postgres-prod",
                "DbiResourceId": "db-ABCDEF123456",
                "DBInstanceClass": "db.m5.large",
                "DBInstanceStatus": "available",
                "AllocatedStorage": 150,
                "StorageType": "gp3",
                "StorageEncrypted": True,
                "KmsKeyId": "arn:aws:kms:us-east-1:123456789012:key/test-key-id",
            }
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    collector = RDSEvidenceCollector(client_factory=factory)

    norm = collector.get_normalized_db_instance("postgres-prod", region="us-east-1")

    assert isinstance(norm, NormalizedRDSInstance)
    assert norm.db_instance_identifier == "postgres-prod"
    assert norm.dbi_resource_id == "db-ABCDEF123456"
    assert norm.instance_class == "db.m5.large"
    assert norm.status == "available"
    assert norm.allocated_storage == 150
    assert norm.storage_type == "gp3"
    assert norm.storage_encrypted is True
    assert norm.kms_key_id == "arn:aws:kms:us-east-1:123456789012:key/test-key-id"


def test_rds_collector_evidence_construction():
    """Verify collect() returns machine-readable Evidence for StorageConfig and dbi_resource_id."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client

    mock_client.describe_db_instances.return_value = {
        "DBInstances": [
            {
                "DBInstanceIdentifier": "mysql-dev",
                "DbiResourceId": "db-XYZ987654",
                "DBInstanceClass": "db.t3.micro",
                "DBInstanceStatus": "available",
                "AllocatedStorage": 20,
                "StorageType": "gp2",
                "StorageEncrypted": False,
            }
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    collector = RDSEvidenceCollector(client_factory=factory)

    # 1. StorageConfig field
    ev_storage = collector.collect(resource_id="mysql-dev", field="StorageConfig", region="us-east-1")
    assert isinstance(ev_storage, Evidence)
    assert ev_storage.source == "aws.rds"
    assert ev_storage.resource_id == "mysql-dev"
    assert ev_storage.field == "StorageConfig"
    assert ev_storage.observed_value == {
        "allocated_storage": 20,
        "storage_type": "gp2",
        "storage_encrypted": False,
        "kms_key_id": None,
    }
    # No raw DBInstances leaked
    assert "DBInstances" not in ev_storage.metadata

    # 2. dbi_resource_id field
    ev_dbi = collector.collect(resource_id="mysql-dev", field="dbi_resource_id", region="us-east-1")
    assert ev_dbi.observed_value == "db-XYZ987654"


def test_rds_collector_db_instance_not_found():
    """Verify DBInstanceNotFound raises ResourceNotFoundError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_db_instances.side_effect = _build_mock_client_error("DBInstanceNotFound")

    factory = AWSClientFactory(session=mock_session)
    collector = RDSEvidenceCollector(client_factory=factory)

    with pytest.raises(ResourceNotFoundError) as exc_info:
        collector.collect(resource_id="db-missing", field="StorageConfig")
    assert exc_info.value.resource_id == "db-missing"
    assert exc_info.value.resource_type == "RDS DB instance"


def test_rds_collector_authorization_error():
    """Verify AccessDenied raises AWSAuthorizationError distinguishable from not found."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_db_instances.side_effect = _build_mock_client_error("AccessDenied")

    factory = AWSClientFactory(session=mock_session)
    collector = RDSEvidenceCollector(client_factory=factory)

    with pytest.raises(AWSAuthorizationError):
        collector.collect(resource_id="db-forbidden", field="StorageConfig")


def test_rds_collector_unsupported_field():
    """Verify unsupported field raises UnsupportedFieldError."""
    mock_session = MagicMock()
    mock_client = MagicMock()
    mock_session.client.return_value = mock_client
    mock_client.describe_db_instances.return_value = {
        "DBInstances": [
            {
                "DBInstanceIdentifier": "test-db",
                "DbiResourceId": "db-123",
                "DBInstanceClass": "db.t3.micro",
                "DBInstanceStatus": "available",
            }
        ]
    }

    factory = AWSClientFactory(session=mock_session)
    collector = RDSEvidenceCollector(client_factory=factory)

    with pytest.raises(UnsupportedFieldError):
        collector.collect(resource_id="test-db", field="unsupported_quantum_field")
