"""Security Group Evidence Collector.

Fetches Security Group state via DescribeSecurityGroups and normalizes it into
NormalizedSecurityGroup and NormalizedIngressRule.
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
from backend.app.aws.schemas import NormalizedIngressRule, NormalizedSecurityGroup
from backend.app.models.evidence import Evidence


class SGEvidenceCollector(BaseEvidenceCollector):
    """Collector for AWS Security Group empirical evidence."""

    def _handle_client_error(self, exc: ClientError, resource_id: str) -> None:
        """Translate botocore ClientError into domain-level AWS exceptions."""
        error_code = exc.response.get("Error", {}).get("Code", "")
        error_message = exc.response.get("Error", {}).get("Message", str(exc))

        if error_code in {"InvalidGroup.NotFound", "InvalidGroupId.Malformed", "InvalidPermission.NotFound"}:
            raise ResourceNotFoundError(
                resource_id=resource_id,
                resource_type="Security Group",
                message=f"Security Group '{resource_id}' not found: {error_message}",
                details={"error_code": error_code, "raw_message": error_message},
            ) from exc

        if error_code in {"UnauthorizedOperation", "AuthFailure", "AccessDenied"}:
            raise AWSAuthorizationError(
                f"Authorization failed querying Security Group '{resource_id}': {error_message}",
                details={"error_code": error_code, "raw_message": error_message},
            ) from exc

        raise AWSServiceError(
            f"AWS EC2 service error querying Security Group '{resource_id}': {error_message}",
            details={"error_code": error_code, "raw_message": error_message},
        ) from exc

    def get_normalized_security_group(
        self,
        resource_id: str,
        region: Optional[str] = None,
    ) -> NormalizedSecurityGroup:
        """Query AWS DescribeSecurityGroups and normalize the response."""
        client = self.client_factory.get_ec2_client(region_name=region)
        try:
            response = client.describe_security_groups(GroupIds=[resource_id])
        except ClientError as e:
            self._handle_client_error(e, resource_id)
        except BotoCoreError as e:
            raise AWSServiceError(f"Botocore error querying Security Group '{resource_id}': {str(e)}") from e

        groups = response.get("SecurityGroups", [])
        if not groups:
            raise ResourceNotFoundError(
                resource_id=resource_id,
                resource_type="Security Group",
                message=f"Security Group '{resource_id}' not found (no groups returned).",
            )

        sg = groups[0]
        rules: list[NormalizedIngressRule] = []

        for perm in sg.get("IpPermissions", []):
            protocol = perm.get("IpProtocol", "")
            from_port = perm.get("FromPort")
            to_port = perm.get("ToPort")

            for ip_range in perm.get("IpRanges", []):
                cidr = ip_range.get("CidrIp")
                if cidr:
                    rules.append(
                        NormalizedIngressRule(
                            protocol=protocol,
                            from_port=from_port,
                            to_port=to_port,
                            cidr=cidr,
                        )
                    )

            for ipv6_range in perm.get("Ipv6Ranges", []):
                cidr = ipv6_range.get("CidrIpv6")
                if cidr:
                    rules.append(
                        NormalizedIngressRule(
                            protocol=protocol,
                            from_port=from_port,
                            to_port=to_port,
                            cidr=cidr,
                        )
                    )

        return NormalizedSecurityGroup(
            group_id=sg.get("GroupId", resource_id),
            group_name=sg.get("GroupName", ""),
            vpc_id=sg.get("VpcId"),
            ip_permissions=rules,
        )

    def collect(
        self,
        resource_id: str,
        field: str,
        region: Optional[str] = None,
    ) -> Evidence:
        """Collect and package normalized Security Group evidence."""
        norm = self.get_normalized_security_group(resource_id=resource_id, region=region)

        normalized_field = field.strip().lower()
        observed_value: Any

        if normalized_field in {
            "ippermissions",
            "ip_permissions",
            "ingress",
            "ingress_cidr_blocks",
            "sensitive_port_exposure",
        }:
            observed_value = [r.model_dump() for r in norm.ip_permissions]
        elif normalized_field in {"group_id", "id"}:
            observed_value = norm.group_id
        elif normalized_field in {"group_name", "name"}:
            observed_value = norm.group_name
        elif normalized_field == "vpc_id":
            observed_value = norm.vpc_id
        elif normalized_field in {"*", "all", "security_group", "sg", "normalizedsecuritygroup"}:
            observed_value = norm.model_dump()
        else:
            raise UnsupportedFieldError(
                f"Field '{field}' is not supported for Security Group evidence collection."
            )

        target_region = region or self.client_factory.region_name
        return Evidence(
            source="aws.ec2.security_group",
            resource_id=norm.group_id,
            field=field,
            observed_value=observed_value,
            observed_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "region": target_region,
                "group_name": norm.group_name,
                "vpc_id": norm.vpc_id,
            },
        )
