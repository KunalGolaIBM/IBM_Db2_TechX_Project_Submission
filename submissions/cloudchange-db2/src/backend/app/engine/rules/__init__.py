"""Deterministic Impact Rules Package for CloudChange."""

from backend.app.engine.rules.base import BaseRule
from backend.app.engine.rules.ec2_config import Ec2ConfigRule
from backend.app.engine.rules.ec2_cost import Ec2CostRule
from backend.app.engine.rules.ec2_replace import Ec2ReplaceRule
from backend.app.engine.rules.rds_data import RdsDataRule
from backend.app.engine.rules.rds_replace import RdsReplaceRule
from backend.app.engine.rules.sg_sensitive_port import SgSensitivePortRule
from backend.app.engine.rules.sg_widen import SgWidenRule

ALL_RULES: list[BaseRule] = [
    Ec2CostRule(),
    Ec2ReplaceRule(),
    Ec2ConfigRule(),
    SgWidenRule(),
    SgSensitivePortRule(),
    RdsReplaceRule(),
    RdsDataRule(),
]

RULE_REGISTRY: dict[str, BaseRule] = {rule.rule_id: rule for rule in ALL_RULES}

__all__ = [
    "BaseRule",
    "Ec2CostRule",
    "Ec2ReplaceRule",
    "Ec2ConfigRule",
    "SgWidenRule",
    "SgSensitivePortRule",
    "RdsReplaceRule",
    "RdsDataRule",
    "ALL_RULES",
    "RULE_REGISTRY",
]
