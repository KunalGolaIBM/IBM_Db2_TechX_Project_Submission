"""Normalized AWS Evidence Schemas.

Domain-level schemas representing clean, normalized observations from AWS.
Raw Boto3 response dictionaries MUST NOT be used directly as domain contracts.
"""

from typing import Optional
from pydantic import BaseModel, Field


class NormalizedEC2Instance(BaseModel):
    """Normalized EC2 instance observation."""

    instance_id: str = Field(..., description="AWS EC2 instance ID (e.g., i-1234567890abcdef0)")
    instance_type: str = Field(..., description="EC2 instance type (e.g., t3.micro)")
    state: str = Field(..., description="Current instance state (e.g., running, stopped)")
    availability_zone: str = Field(..., description="Placement availability zone (e.g., us-east-1a)")
    ebs_optimized: bool = Field(..., description="Whether the instance is optimized for EBS I/O")
    monitoring: str = Field(..., description="State of CloudWatch detailed monitoring (e.g., enabled, disabled)")
    source_dest_check: bool = Field(..., description="Whether source/destination checking is enabled")
    disable_api_termination: bool = Field(..., description="Whether termination protection is enabled")


class NormalizedIngressRule(BaseModel):
    """Normalized security group ingress rule observation."""

    protocol: str = Field(..., description="IP protocol (e.g., tcp, udp, -1)")
    from_port: Optional[int] = Field(default=None, description="Start of port range (None for all ports)")
    to_port: Optional[int] = Field(default=None, description="End of port range (None for all ports)")
    cidr: str = Field(..., description="IPv4 or IPv6 CIDR block (e.g., 0.0.0.0/0)")


class NormalizedSecurityGroup(BaseModel):
    """Normalized security group observation."""

    group_id: str = Field(..., description="AWS Security Group ID (e.g., sg-12345678)")
    group_name: str = Field(..., description="Security group name")
    vpc_id: Optional[str] = Field(default=None, description="Associated VPC ID")
    ip_permissions: list[NormalizedIngressRule] = Field(
        ..., description="List of normalized ingress rules"
    )


class NormalizedRDSInstance(BaseModel):
    """Normalized RDS DB instance observation."""

    db_instance_identifier: str = Field(..., description="Logical DB instance identifier")
    dbi_resource_id: str = Field(..., description="Immutable physical AWS RDS resource ID (e.g., db-ABCDEF123456)")
    instance_class: str = Field(..., description="DB compute and memory capacity class (e.g., db.t3.micro)")
    status: str = Field(..., description="Current DB instance status (e.g., available, stopped)")
    allocated_storage: int = Field(..., description="Allocated storage size in gigabytes (GB)")
    storage_type: str = Field(..., description="Storage subsystem type (e.g., gp2, gp3, io1)")
    storage_encrypted: bool = Field(..., description="Whether storage encryption is enabled")
    kms_key_id: Optional[str] = Field(default=None, description="KMS key ARN/ID used for encryption if enabled")
