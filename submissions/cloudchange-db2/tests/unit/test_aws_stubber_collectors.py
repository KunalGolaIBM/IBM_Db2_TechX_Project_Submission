"""Unit tests using botocore.stub.Stubber on real boto3 clients.

Validates parameter schemas, response parsing, and error simulation without network calls.
"""

import boto3
import pytest
from botocore.stub import Stubber

from backend.app.aws.clients import AWSClientFactory
from backend.app.aws.collectors.ec2 import EC2EvidenceCollector
from backend.app.aws.collectors.rds import RDSEvidenceCollector
from backend.app.aws.collectors.security_group import SGEvidenceCollector
from backend.app.aws.errors import (
    AWSAuthorizationError,
    AWSServiceError,
    ResourceNotFoundError,
)


def test_stubber_ec2_describe_instances_success():
    """Verify EC2 collector with Stubber on real boto3 EC2 client."""
    ec2_client = boto3.client("ec2", region_name="us-east-1", aws_access_key_id="fake", aws_secret_access_key="fake")
    stubber = Stubber(ec2_client)

    expected_params = {"InstanceIds": ["i-0123456789abcdef0"]}
    response = {
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
                    }
                ]
            }
        ]
    }

    stubber.add_response("describe_instances", response, expected_params)

    with stubber:
        factory = AWSClientFactory(region_name="us-east-1")
        factory._clients[("ec2", "us-east-1")] = ec2_client
        collector = EC2EvidenceCollector(client_factory=factory)

        ev = collector.collect(resource_id="i-0123456789abcdef0", field="instance_type", region="us-east-1")
        assert ev.observed_value == "t3.large"
        assert ev.resource_id == "i-0123456789abcdef0"


def test_stubber_ec2_describe_instances_not_found():
    """Verify EC2 collector handles InvalidInstanceID.NotFound via Stubber."""
    ec2_client = boto3.client("ec2", region_name="us-east-1", aws_access_key_id="fake", aws_secret_access_key="fake")
    stubber = Stubber(ec2_client)

    stubber.add_client_error(
        "describe_instances",
        service_error_code="InvalidInstanceID.NotFound",
        service_message="The instance ID 'i-missing' does not exist",
        expected_params={"InstanceIds": ["i-missing"]},
    )

    with stubber:
        factory = AWSClientFactory(region_name="us-east-1")
        factory._clients[("ec2", "us-east-1")] = ec2_client
        collector = EC2EvidenceCollector(client_factory=factory)

        with pytest.raises(ResourceNotFoundError) as exc_info:
            collector.collect(resource_id="i-missing", field="instance_type", region="us-east-1")
        assert exc_info.value.resource_id == "i-missing"


def test_stubber_sg_describe_security_groups_success():
    """Verify SG collector with Stubber on real boto3 EC2 client."""
    ec2_client = boto3.client("ec2", region_name="us-east-1", aws_access_key_id="fake", aws_secret_access_key="fake")
    stubber = Stubber(ec2_client)

    expected_params = {"GroupIds": ["sg-0123456789abcdef0"]}
    response = {
        "SecurityGroups": [
            {
                "GroupId": "sg-0123456789abcdef0",
                "GroupName": "app-sg",
                "VpcId": "vpc-01234567",
                "IpPermissions": [
                    {
                        "IpProtocol": "tcp",
                        "FromPort": 80,
                        "ToPort": 80,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    }
                ],
            }
        ]
    }

    stubber.add_response("describe_security_groups", response, expected_params)

    with stubber:
        factory = AWSClientFactory(region_name="us-east-1")
        factory._clients[("ec2", "us-east-1")] = ec2_client
        collector = SGEvidenceCollector(client_factory=factory)

        ev = collector.collect(resource_id="sg-0123456789abcdef0", field="IpPermissions", region="us-east-1")
        assert len(ev.observed_value) == 1
        assert ev.observed_value[0]["from_port"] == 80
        assert ev.observed_value[0]["cidr"] == "0.0.0.0/0"


def test_stubber_rds_describe_db_instances_success():
    """Verify RDS collector with Stubber on real boto3 RDS client."""
    rds_client = boto3.client("rds", region_name="us-east-1", aws_access_key_id="fake", aws_secret_access_key="fake")
    stubber = Stubber(rds_client)

    expected_params = {"DBInstanceIdentifier": "app-db-v2"}
    response = {
        "DBInstances": [
            {
                "DBInstanceIdentifier": "app-db-v2",
                "DbiResourceId": "db-RESOURCEID123",
                "DBInstanceClass": "db.t3.micro",
                "DBInstanceStatus": "available",
                "AllocatedStorage": 40,
                "StorageType": "gp3",
                "StorageEncrypted": True,
            }
        ]
    }

    stubber.add_response("describe_db_instances", response, expected_params)

    with stubber:
        factory = AWSClientFactory(region_name="us-east-1")
        factory._clients[("rds", "us-east-1")] = rds_client
        collector = RDSEvidenceCollector(client_factory=factory)

        ev = collector.collect(resource_id="app-db-v2", field="StorageConfig", region="us-east-1")
        assert ev.observed_value["allocated_storage"] == 40
        assert ev.observed_value["storage_type"] == "gp3"
        assert ev.observed_value["storage_encrypted"] is True


def test_stubber_rds_describe_db_instances_not_found():
    """Verify RDS collector handles DBInstanceNotFound via Stubber."""
    rds_client = boto3.client("rds", region_name="us-east-1", aws_access_key_id="fake", aws_secret_access_key="fake")
    stubber = Stubber(rds_client)

    stubber.add_client_error(
        "describe_db_instances",
        service_error_code="DBInstanceNotFound",
        service_message="DBInstance app-db-deleted not found.",
        expected_params={"DBInstanceIdentifier": "app-db-deleted"},
    )

    with stubber:
        factory = AWSClientFactory(region_name="us-east-1")
        factory._clients[("rds", "us-east-1")] = rds_client
        collector = RDSEvidenceCollector(client_factory=factory)

        with pytest.raises(ResourceNotFoundError) as exc_info:
            collector.collect(resource_id="app-db-deleted", field="StorageConfig", region="us-east-1")
        assert exc_info.value.resource_id == "app-db-deleted"
