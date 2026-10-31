"""AWS Client Factory.

Provides lazily initialized boto3 client instances configured with appropriate
credentials and regions. Supports client caching and session injection for testing.
"""

from typing import Any, Optional
import boto3
from backend.app.config import settings


class AWSClientFactory:
    """Factory for creating and caching AWS service clients lazily."""

    def __init__(
        self,
        region_name: Optional[str] = None,
        session: Optional[boto3.Session] = None,
    ) -> None:
        self.region_name = region_name or settings.DEFAULT_AWS_REGION
        self.session = session
        self._clients: dict[tuple[str, str], Any] = {}

    def get_client(self, service_name: str, region_name: Optional[str] = None) -> Any:
        """Return a cached or newly instantiated boto3 client for the given service and region."""
        target_region = region_name or self.region_name
        cache_key = (service_name, target_region)
        if cache_key not in self._clients:
            if self.session is not None:
                self._clients[cache_key] = self.session.client(service_name, region_name=target_region)
            else:
                self._clients[cache_key] = boto3.client(service_name, region_name=target_region)
        return self._clients[cache_key]

    def get_ec2_client(self, region_name: Optional[str] = None) -> Any:
        """Return a boto3 EC2 client."""
        return self.get_client("ec2", region_name=region_name)

    def get_rds_client(self, region_name: Optional[str] = None) -> Any:
        """Return a boto3 RDS client."""
        return self.get_client("rds", region_name=region_name)
