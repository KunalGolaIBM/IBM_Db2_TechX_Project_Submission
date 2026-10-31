"""AWS Evidence Collectors Package.

Provides concrete read-only evidence collectors for EC2, Security Groups, and RDS,
as well as a central EvidenceCollectorRegistry.
"""

from backend.app.aws.collectors.base import BaseEvidenceCollector
from backend.app.aws.collectors.ec2 import EC2EvidenceCollector
from backend.app.aws.collectors.rds import RDSEvidenceCollector
from backend.app.aws.collectors.registry import EvidenceCollectorRegistry
from backend.app.aws.collectors.security_group import SGEvidenceCollector

__all__ = [
    "BaseEvidenceCollector",
    "EC2EvidenceCollector",
    "SGEvidenceCollector",
    "RDSEvidenceCollector",
    "EvidenceCollectorRegistry",
]
