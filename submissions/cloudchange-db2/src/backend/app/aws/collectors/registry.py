"""Evidence Collector Registry.

Maps Terraform / AWS resource types to concrete evidence collectors.
"""

from typing import Optional
from backend.app.aws.clients import AWSClientFactory
from backend.app.aws.collectors.base import BaseEvidenceCollector
from backend.app.aws.collectors.ec2 import EC2EvidenceCollector
from backend.app.aws.collectors.rds import RDSEvidenceCollector
from backend.app.aws.collectors.security_group import SGEvidenceCollector
from backend.app.aws.errors import UnsupportedResourceTypeError
from backend.app.models.evidence import Evidence


class EvidenceCollectorRegistry:
    """Registry for looking up and invoking AWS evidence collectors."""

    def __init__(self, client_factory: Optional[AWSClientFactory] = None) -> None:
        self.client_factory = client_factory or AWSClientFactory()
        self._ec2_collector = EC2EvidenceCollector(client_factory=self.client_factory)
        self._sg_collector = SGEvidenceCollector(client_factory=self.client_factory)
        self._rds_collector = RDSEvidenceCollector(client_factory=self.client_factory)

        self._type_map: dict[str, BaseEvidenceCollector] = {
            "aws_instance": self._ec2_collector,
            "instance": self._ec2_collector,
            "ec2": self._ec2_collector,
            "aws_security_group": self._sg_collector,
            "security_group": self._sg_collector,
            "sg": self._sg_collector,
            "aws_db_instance": self._rds_collector,
            "db_instance": self._rds_collector,
            "rds": self._rds_collector,
        }

    def get_collector(self, resource_type: str) -> BaseEvidenceCollector:
        """Retrieve collector by Terraform resource type or AWS resource type name."""
        key = (resource_type or "").strip().lower()
        if key not in self._type_map:
            raise UnsupportedResourceTypeError(
                f"No evidence collector registered for resource type '{resource_type}'."
            )
        return self._type_map[key]

    def get_collector_for_service(self, service: str, resource_type: str) -> BaseEvidenceCollector:
        """Retrieve collector by EvidenceRequirement service and resource_type."""
        svc = (service or "").strip().lower()
        rtype = (resource_type or "").strip().lower()

        if svc == "ec2" and rtype in {"instance", "aws_instance"}:
            return self._ec2_collector
        if svc == "ec2" and rtype in {"security_group", "aws_security_group", "sg"}:
            return self._sg_collector
        if svc == "rds" and rtype in {"db_instance", "aws_db_instance", "instance"}:
            return self._rds_collector

        if rtype in self._type_map:
            return self._type_map[rtype]

        raise UnsupportedResourceTypeError(
            f"No evidence collector registered for service '{service}' and resource_type '{resource_type}'."
        )

    def collect(
        self,
        resource_type: str,
        resource_id: str,
        field: str,
        region: Optional[str] = None,
    ) -> Evidence:
        """Route collection to appropriate collector and return Evidence."""
        collector = self.get_collector(resource_type)
        return collector.collect(resource_id=resource_id, field=field, region=region)
