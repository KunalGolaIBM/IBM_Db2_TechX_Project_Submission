"""Base Evidence Collector Interface.

Defines the contract for AWS evidence collectors that fetch empirical data from AWS
and normalize it into domain schemas and Evidence models.
"""

from abc import ABC, abstractmethod
from typing import Optional
from backend.app.aws.clients import AWSClientFactory
from backend.app.models.evidence import Evidence


class BaseEvidenceCollector(ABC):
    """Abstract base class for AWS evidence collectors."""

    def __init__(self, client_factory: Optional[AWSClientFactory] = None) -> None:
        self.client_factory = client_factory or AWSClientFactory()

    @abstractmethod
    def collect(
        self,
        resource_id: str,
        field: str,
        region: Optional[str] = None,
    ) -> Evidence:
        """Collect normalized evidence for a given physical resource and field.

        Args:
            resource_id: Physical AWS resource identifier (e.g. i-12345, sg-12345, db-prod).
            field: The target attribute/metric to observe.
            region: Optional AWS region override (defaults to client factory region).

        Returns:
            Evidence domain model containing machine-readable observed value.

        Raises:
            ResourceNotFoundError: If the resource does not exist in AWS.
            AWSAuthorizationError: If credentials or permissions are insufficient.
            AWSServiceError: If AWS is unreachable or returns a server/throttling error.
            UnsupportedFieldError: If the requested field is not supported.
        """
        ...
