"""RDS Evidence Collector.

Fetches RDS DB instance state via DescribeDBInstances and normalizes it into
NormalizedRDSInstance.
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
from backend.app.aws.schemas import NormalizedRDSInstance
from backend.app.models.evidence import Evidence


class RDSEvidenceCollector(BaseEvidenceCollector):
    """Collector for AWS RDS instance empirical evidence."""

    def _handle_client_error(self, exc: ClientError, resource_id: str) -> None:
        """Translate botocore ClientError into domain-level AWS exceptions."""
        error_code = exc.response.get("Error", {}).get("Code", "")
        error_message = exc.response.get("Error", {}).get("Message", str(exc))

        if error_code in {"DBInstanceNotFound", "DBInstanceNotFoundFault", "ResourceNotFoundFault"}:
            raise ResourceNotFoundError(
                resource_id=resource_id,
                resource_type="RDS DB instance",
                message=f"RDS DB instance '{resource_id}' not found: {error_message}",
                details={"error_code": error_code, "raw_message": error_message},
            ) from exc

        if error_code in {"AccessDenied", "AuthFailure", "NotAuthorized"}:
            raise AWSAuthorizationError(
                f"Authorization failed querying RDS DB instance '{resource_id}': {error_message}",
                details={"error_code": error_code, "raw_message": error_message},
            ) from exc

        raise AWSServiceError(
            f"AWS RDS service error querying '{resource_id}': {error_message}",
            details={"error_code": error_code, "raw_message": error_message},
        ) from exc

    def get_normalized_db_instance(
        self,
        resource_id: str,
        region: Optional[str] = None,
    ) -> NormalizedRDSInstance:
        """Query AWS DescribeDBInstances and normalize the response."""
        client = self.client_factory.get_rds_client(region_name=region)
        try:
            response = client.describe_db_instances(DBInstanceIdentifier=resource_id)
        except ClientError as e:
            self._handle_client_error(e, resource_id)
        except BotoCoreError as e:
            raise AWSServiceError(f"Botocore error querying RDS instance '{resource_id}': {str(e)}") from e

        db_instances = response.get("DBInstances", [])
        if not db_instances:
            raise ResourceNotFoundError(
                resource_id=resource_id,
                resource_type="RDS DB instance",
                message=f"RDS DB instance '{resource_id}' not found (no DBInstances returned).",
            )

        db = db_instances[0]
        return NormalizedRDSInstance(
            db_instance_identifier=db.get("DBInstanceIdentifier", resource_id),
            dbi_resource_id=db.get("DbiResourceId", ""),
            instance_class=db.get("DBInstanceClass", ""),
            status=db.get("DBInstanceStatus", "unknown"),
            allocated_storage=db.get("AllocatedStorage", 0),
            storage_type=db.get("StorageType", "standard"),
            storage_encrypted=db.get("StorageEncrypted", False),
            kms_key_id=db.get("KmsKeyId"),
        )

    def collect(
        self,
        resource_id: str,
        field: str,
        region: Optional[str] = None,
    ) -> Evidence:
        """Collect and package normalized RDS DB instance evidence."""
        norm = self.get_normalized_db_instance(resource_id=resource_id, region=region)

        normalized_field = field.strip().lower()
        observed_value: Any

        if normalized_field in {
            "storageconfig",
            "storage_config",
            "storage_and_encryption_config",
        }:
            observed_value = {
                "allocated_storage": norm.allocated_storage,
                "storage_type": norm.storage_type,
                "storage_encrypted": norm.storage_encrypted,
                "kms_key_id": norm.kms_key_id,
            }
        elif normalized_field in {"dbi_resource_id", "resource_identity"}:
            observed_value = norm.dbi_resource_id
        elif normalized_field in {"db_instance_identifier", "identifier"}:
            observed_value = norm.db_instance_identifier
        elif normalized_field in {"instance_class", "db_instance_class"}:
            observed_value = norm.instance_class
        elif normalized_field in {"status", "instance_deletion", "dbinstancenotfound"}:
            observed_value = norm.status
        elif normalized_field == "allocated_storage":
            observed_value = norm.allocated_storage
        elif normalized_field == "storage_type":
            observed_value = norm.storage_type
        elif normalized_field == "storage_encrypted":
            observed_value = norm.storage_encrypted
        elif normalized_field == "kms_key_id":
            observed_value = norm.kms_key_id
        elif normalized_field in {"*", "all", "db_instance", "rds_instance", "normalizedrdsinstance"}:
            observed_value = norm.model_dump()
        else:
            raise UnsupportedFieldError(
                f"Field '{field}' is not supported for RDS DB instance evidence collection."
            )

        target_region = region or self.client_factory.region_name
        return Evidence(
            source="aws.rds",
            resource_id=norm.db_instance_identifier,
            field=field,
            observed_value=observed_value,
            observed_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "region": target_region,
                "dbi_resource_id": norm.dbi_resource_id,
                "status": norm.status,
            },
        )
