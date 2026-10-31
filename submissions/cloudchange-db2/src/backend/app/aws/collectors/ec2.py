"""EC2 Evidence Collector.

Fetches EC2 instance state via DescribeInstances and normalizes it into NormalizedEC2Instance.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from botocore.exceptions import BotoCoreError, ClientError

from backend.app.aws.collectors.base import BaseEvidenceCollector
from backend.app.aws.errors import (
    AWSAuthorizationError,
    AWSServiceError,
    ResourceNotFoundError,
    UnsupportedFieldError,
)
from backend.app.aws.schemas import NormalizedEC2Instance
from backend.app.models.evidence import Evidence


class EC2EvidenceCollector(BaseEvidenceCollector):
    """Collector for AWS EC2 instance empirical evidence."""

    def _handle_client_error(self, exc: ClientError, resource_id: str) -> None:
        """Translate botocore ClientError into domain-level AWS exceptions."""
        error_code = exc.response.get("Error", {}).get("Code", "")
        error_message = exc.response.get("Error", {}).get("Message", str(exc))

        if error_code in {"InvalidInstanceID.NotFound", "InvalidInstanceId", "InvalidInstanceID.Malformed"}:
            raise ResourceNotFoundError(
                resource_id=resource_id,
                resource_type="EC2 instance",
                message=f"EC2 instance '{resource_id}' not found: {error_message}",
                details={"error_code": error_code, "raw_message": error_message},
            ) from exc

        if error_code in {"UnauthorizedOperation", "AuthFailure", "AccessDenied"}:
            raise AWSAuthorizationError(
                f"Authorization failed querying EC2 instance '{resource_id}': {error_message}",
                details={"error_code": error_code, "raw_message": error_message},
            ) from exc

        raise AWSServiceError(
            f"AWS EC2 service error querying '{resource_id}': {error_message}",
            details={"error_code": error_code, "raw_message": error_message},
        ) from exc

    def get_normalized_instance(
        self,
        resource_id: str,
        region: Optional[str] = None,
    ) -> NormalizedEC2Instance:
        """Query AWS DescribeInstances and normalize the response into NormalizedEC2Instance."""
        client = self.client_factory.get_ec2_client(region_name=region)
        try:
            response = client.describe_instances(InstanceIds=[resource_id])
        except ClientError as e:
            self._handle_client_error(e, resource_id)
        except BotoCoreError as e:
            raise AWSServiceError(f"Botocore error querying EC2 instance '{resource_id}': {str(e)}") from e

        reservations = response.get("Reservations", [])
        if not reservations:
            raise ResourceNotFoundError(
                resource_id=resource_id,
                resource_type="EC2 instance",
                message=f"EC2 instance '{resource_id}' not found (no reservations returned).",
            )

        instances = reservations[0].get("Instances", [])
        if not instances:
            raise ResourceNotFoundError(
                resource_id=resource_id,
                resource_type="EC2 instance",
                message=f"EC2 instance '{resource_id}' not found (no instance in reservation).",
            )

        inst = instances[0]
        state = inst.get("State", {}).get("Name", "unknown")
        availability_zone = inst.get("Placement", {}).get("AvailabilityZone", "")
        monitoring = inst.get("Monitoring", {}).get("State", "disabled")
        ebs_optimized = inst.get("EbsOptimized", False)
        source_dest_check = inst.get("SourceDestCheck", True)
        disable_api_termination = inst.get("DisableApiTermination", False)

        return NormalizedEC2Instance(
            instance_id=inst.get("InstanceId", resource_id),
            instance_type=inst.get("InstanceType", "unknown"),
            state=state,
            availability_zone=availability_zone,
            ebs_optimized=ebs_optimized,
            monitoring=monitoring,
            source_dest_check=source_dest_check,
            disable_api_termination=disable_api_termination,
        )

    def collect(
        self,
        resource_id: str,
        field: str,
        region: Optional[str] = None,
    ) -> Evidence:
        """Collect and package normalized EC2 instance evidence."""
        norm = self.get_normalized_instance(resource_id=resource_id, region=region)

        normalized_field = field.strip().lower()
        observed_value: Any

        if normalized_field == "instance_type":
            observed_value = norm.instance_type
        elif normalized_field in {"instance_id", "id"}:
            observed_value = norm.instance_id
        elif normalized_field == "state":
            observed_value = norm.state
        elif normalized_field == "availability_zone":
            observed_value = norm.availability_zone
        elif normalized_field == "ebs_optimized":
            observed_value = norm.ebs_optimized
        elif normalized_field == "monitoring":
            observed_value = norm.monitoring
        elif normalized_field == "source_dest_check":
            observed_value = norm.source_dest_check
        elif normalized_field == "disable_api_termination":
            observed_value = norm.disable_api_termination
        elif normalized_field in {"operational_config", "config"}:
            observed_value = {
                "ebs_optimized": norm.ebs_optimized,
                "monitoring": norm.monitoring,
                "source_dest_check": norm.source_dest_check,
                "disable_api_termination": norm.disable_api_termination,
            }
        elif normalized_field in {"resource_identity", "identity"}:
            observed_value = {
                "instance_id": norm.instance_id,
                "state": norm.state,
            }
        elif normalized_field in {"*", "all", "instance", "ec2_instance", "normalizedec2instance"}:
            observed_value = norm.model_dump()
        else:
            raise UnsupportedFieldError(
                f"Field '{field}' is not supported for EC2 instance evidence collection."
            )

        target_region = region or self.client_factory.region_name
        return Evidence(
            source="aws.ec2",
            resource_id=norm.instance_id,
            field=field,
            observed_value=observed_value,
            observed_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "region": target_region,
                "availability_zone": norm.availability_zone,
                "state": norm.state,
            },
        )
