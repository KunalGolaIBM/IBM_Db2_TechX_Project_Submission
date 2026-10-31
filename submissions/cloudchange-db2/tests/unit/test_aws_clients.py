"""Unit tests for AWSClientFactory foundation."""

from unittest.mock import MagicMock, patch

from backend.app.aws.clients import AWSClientFactory


def test_aws_client_factory_lazy_initialization():
    """Verify no clients are created during construction."""
    with patch("boto3.client") as mock_boto_client:
        factory = AWSClientFactory(region_name="us-east-1")
        assert factory.region_name == "us-east-1"
        assert len(factory._clients) == 0
        mock_boto_client.assert_not_called()


def test_aws_client_factory_with_injected_session():
    """Verify that an injected boto3.Session is used to create clients."""
    mock_session = MagicMock()
    mock_ec2_client = MagicMock()
    mock_session.client.return_value = mock_ec2_client

    factory = AWSClientFactory(region_name="us-west-2", session=mock_session)
    assert len(factory._clients) == 0

    client = factory.get_ec2_client()
    assert client == mock_ec2_client
    mock_session.client.assert_called_once_with("ec2", region_name="us-west-2")


def test_aws_client_factory_client_caching():
    """Verify that subsequent requests for the same service + region reuse the cached client."""
    with patch("boto3.client") as mock_boto_client:
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2

        factory = AWSClientFactory(region_name="us-east-1")

        # First call creates client
        client1 = factory.get_ec2_client()
        assert client1 == mock_ec2
        assert mock_boto_client.call_count == 1
        mock_boto_client.assert_called_with("ec2", region_name="us-east-1")

        # Second call returns cached client
        client2 = factory.get_ec2_client()
        assert client2 is client1
        assert mock_boto_client.call_count == 1


def test_aws_client_factory_distinct_regions_not_shared():
    """Verify that different regions do not share the same client instance."""
    with patch("boto3.client") as mock_boto_client:
        mock_client_east = MagicMock()
        mock_client_west = MagicMock()
        mock_boto_client.side_effect = [mock_client_east, mock_client_west]

        factory = AWSClientFactory(region_name="us-east-1")

        client_east = factory.get_ec2_client("us-east-1")
        client_west = factory.get_ec2_client("us-west-2")

        assert client_east == mock_client_east
        assert client_west == mock_client_west
        assert client_east != client_west
        assert mock_boto_client.call_count == 2
        mock_boto_client.assert_any_call("ec2", region_name="us-east-1")
        mock_boto_client.assert_any_call("ec2", region_name="us-west-2")


def test_aws_client_factory_ec2_and_rds_creation():
    """Verify get_ec2_client and get_rds_client create respective service clients."""
    with patch("boto3.client") as mock_boto_client:
        mock_ec2 = MagicMock()
        mock_rds = MagicMock()
        mock_boto_client.side_effect = lambda service, region_name: mock_ec2 if service == "ec2" else mock_rds

        factory = AWSClientFactory(region_name="eu-central-1")

        ec2_client = factory.get_ec2_client()
        rds_client = factory.get_rds_client()

        assert ec2_client == mock_ec2
        assert rds_client == mock_rds
        assert mock_boto_client.call_count == 2
        mock_boto_client.assert_any_call("ec2", region_name="eu-central-1")
        mock_boto_client.assert_any_call("rds", region_name="eu-central-1")


def test_aws_client_factory_generic_get_client():
    """Verify generic get_client method creates and caches requested service."""
    with patch("boto3.client") as mock_boto_client:
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        factory = AWSClientFactory()
        client = factory.get_client("s3", region_name="us-west-1")

        assert client == mock_s3
        mock_boto_client.assert_called_once_with("s3", region_name="us-west-1")
