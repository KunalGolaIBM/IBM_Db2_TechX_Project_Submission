"""Unit tests for Prediction.resource_address link and rule population."""

from backend.app.engine.rules.ec2_config import Ec2ConfigRule
from backend.app.engine.rules.ec2_cost import Ec2CostRule
from backend.app.engine.rules.ec2_replace import Ec2ReplaceRule
from backend.app.engine.rules.rds_data import RdsDataRule
from backend.app.engine.rules.rds_replace import RdsReplaceRule
from backend.app.engine.rules.sg_sensitive_port import SgSensitivePortRule
from backend.app.engine.rules.sg_widen import SgWidenRule
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.evidence import EvidenceRequirement
from backend.app.models.prediction import Prediction, VerificationApproach


def test_prediction_construction_without_resource_address_remains_valid():
    """Verify backwards compatibility: resource_address defaults to None."""
    pred = Prediction(
        prediction_id="pred-test-1",
        metric="instance_type",
        expected_value="t3.large",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="Test rationale",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="instance_type",
        ),
    )
    assert pred.resource_address is None
    assert pred.prediction_id == "pred-test-1"


def test_prediction_construction_with_explicit_resource_address():
    """Verify explicit resource_address assignment."""
    pred = Prediction(
        prediction_id="pred-test-2",
        resource_address="aws_instance.api",
        metric="instance_type",
        expected_value="t3.large",
        verification_approach=VerificationApproach.EXACT_MATCH,
        rationale="Test rationale",
        evidence_requirement=EvidenceRequirement(
            provider="aws",
            service="ec2",
            resource_type="instance",
            field="instance_type",
        ),
    )
    assert pred.resource_address == "aws_instance.api"


def test_all_seven_rules_populate_resource_address():
    """Verify that all 7 rules explicitly set resource_address on generated predictions."""
    # 1. CC-EC2-COST-001
    ec2_cost_change = CanonicalChange(
        resource_address="aws_instance.web",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"instance_type": "t3.small"},
        after={"instance_type": "t3.large"},
    )
    pred_cost = Ec2CostRule().generate_prediction(ec2_cost_change)
    assert pred_cost.resource_address == "aws_instance.web"

    # 2. CC-EC2-REPLACE-001
    ec2_replace_change = CanonicalChange(
        resource_address="aws_instance.web",
        resource_type="aws_instance",
        action=ActionType.REPLACE,
        requires_replacement=True,
        before={"id": "i-12345", "ami": "ami-111"},
        after={"ami": "ami-222"},
    )
    pred_replace = Ec2ReplaceRule().generate_prediction(ec2_replace_change)
    assert pred_replace.resource_address == "aws_instance.web"

    # 3. CC-EC2-CONFIG-001
    ec2_config_change = CanonicalChange(
        resource_address="aws_instance.worker",
        resource_type="aws_instance",
        action=ActionType.UPDATE,
        before={"ebs_optimized": False},
        after={"ebs_optimized": True},
    )
    pred_config = Ec2ConfigRule().generate_prediction(ec2_config_change)
    assert pred_config.resource_address == "aws_instance.worker"

    # 4. CC-SG-WIDEN-001
    sg_widen_change = CanonicalChange(
        resource_address="aws_security_group.app_sg",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr_blocks": ["0.0.0.0/0"]}
            ]
        },
    )
    pred_widen = SgWidenRule().generate_prediction(sg_widen_change)
    assert pred_widen.resource_address == "aws_security_group.app_sg"

    # 5. CC-SG-SENSITIVE-PORT-001
    sg_sens_change = CanonicalChange(
        resource_address="aws_security_group.bastion_sg",
        resource_type="aws_security_group",
        action=ActionType.UPDATE,
        before={"ingress": []},
        after={
            "ingress": [
                {"protocol": "tcp", "from_port": 22, "to_port": 22, "cidr_blocks": ["0.0.0.0/0"]}
            ]
        },
    )
    pred_sens = SgSensitivePortRule().generate_prediction(sg_sens_change)
    assert pred_sens.resource_address == "aws_security_group.bastion_sg"

    # 6. CC-RDS-REPLACE-001
    rds_replace_change = CanonicalChange(
        resource_address="aws_db_instance.db_master",
        resource_type="aws_db_instance",
        action=ActionType.REPLACE,
        requires_replacement=True,
        before={"id": "db-123", "dbi_resource_id": "db-ABCDEF"},
        after={"allocated_storage": 100},
    )
    pred_rds_rep = RdsReplaceRule().generate_prediction(rds_replace_change)
    assert pred_rds_rep.resource_address == "aws_db_instance.db_master"

    # 7. CC-RDS-DATA-001 (Modification & Deletion)
    rds_data_mod_change = CanonicalChange(
        resource_address="aws_db_instance.db_replica",
        resource_type="aws_db_instance",
        action=ActionType.UPDATE,
        requires_replacement=True,
        before={"allocated_storage": 20, "storage_encrypted": False},
        after={"allocated_storage": 50, "storage_encrypted": True},
    )
    pred_rds_mod = RdsDataRule().generate_prediction(rds_data_mod_change)
    assert pred_rds_mod.resource_address == "aws_db_instance.db_replica"

    rds_data_del_change = CanonicalChange(
        resource_address="aws_db_instance.db_temp",
        resource_type="aws_db_instance",
        action=ActionType.DELETE,
        before={"identifier": "db-temp"},
        after=None,
    )
    pred_rds_del = RdsDataRule().generate_prediction(rds_data_del_change)
    assert pred_rds_del.resource_address == "aws_db_instance.db_temp"
