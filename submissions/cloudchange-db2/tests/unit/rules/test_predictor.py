"""Unit tests for ImpactPredictor orchestration and rule registry."""

from backend.app.engine.predictor import ImpactPredictor
from backend.app.engine.rules import ALL_RULES, RULE_REGISTRY
from backend.app.models.change import ActionType, CanonicalChange
from backend.app.models.impact import ImpactCategory, Severity


def test_rule_registry_contains_all_seven_phase_1_rules():
    assert len(ALL_RULES) == 7
    expected_ids = {
        "CC-EC2-COST-001",
        "CC-EC2-REPLACE-001",
        "CC-EC2-CONFIG-001",
        "CC-SG-WIDEN-001",
        "CC-SG-SENSITIVE-PORT-001",
        "CC-RDS-REPLACE-001",
        "CC-RDS-DATA-001",
    }
    assert set(RULE_REGISTRY.keys()) == expected_ids
    for rule_id, rule in RULE_REGISTRY.items():
        assert rule.rule_id == rule_id
        assert rule.rule_version == "1.0.0"


def test_predictor_evaluates_multiple_rules_across_resources():
    predictor = ImpactPredictor()

    changes = [
        # EC2 scaling up
        CanonicalChange(
            resource_address="aws_instance.web",
            resource_type="aws_instance",
            action=ActionType.UPDATE,
            before={"instance_type": "t3.small"},
            after={"instance_type": "t3.large"},
        ),
        # SG exposing port 22 and 80 to 0.0.0.0/0 (triggers both WIDEN and SENSITIVE_PORT)
        CanonicalChange(
            resource_address="aws_security_group.web_sg",
            resource_type="aws_security_group",
            action=ActionType.UPDATE,
            before={"ingress": []},
            after={
                "ingress": [
                    {"protocol": "tcp", "from_port": 80, "to_port": 80, "cidr_blocks": ["0.0.0.0/0"]},
                    {"protocol": "tcp", "from_port": 22, "to_port": 22, "cidr_blocks": ["0.0.0.0/0"]},
                ]
            },
        ),
        # RDS replacement with storage alterations (triggers both RDS_REPLACE and RDS_DATA)
        CanonicalChange(
            resource_address="aws_db_instance.db",
            resource_type="aws_db_instance",
            action=ActionType.UPDATE,
            requires_replacement=True,
            before={"identifier": "db-prod", "allocated_storage": 20},
            after={"identifier": "db-prod", "allocated_storage": 100},
        ),
    ]

    findings, predictions = predictor.evaluate(changes)

    # Web EC2: CC-EC2-COST-001
    # SG: CC-SG-WIDEN-001 and CC-SG-SENSITIVE-PORT-001
    # RDS: CC-RDS-REPLACE-001 and CC-RDS-DATA-001
    assert len(findings) == 5
    assert len(predictions) == 5

    found_rules = {f.rule_id for f in findings}
    assert found_rules == {
        "CC-EC2-COST-001",
        "CC-SG-WIDEN-001",
        "CC-SG-SENSITIVE-PORT-001",
        "CC-RDS-REPLACE-001",
        "CC-RDS-DATA-001",
    }

    # Verify Prediction Integrity across all generated predictions:
    for pred in predictions:
        assert pred.prediction_id is not None
        assert pred.metric is not None
        assert pred.expected_value is not None
        assert pred.verification_approach in {
            "EXACT_MATCH",
            "IDENTITY_REPLACED",
            "CONFIG_MATCH",
            "SET_CONTAINS",
            "RESOURCE_DELETED",
        }
        assert pred.evidence_requirement is not None
        assert pred.evidence_requirement.provider == "aws"
        assert pred.evidence_requirement.service in {"ec2", "rds"}
        assert pred.evidence_requirement.resource_type in {"instance", "security_group", "db_instance"}
        assert pred.evidence_requirement.field is not None


def test_predictor_with_no_actionable_changes():
    predictor = ImpactPredictor()
    findings, predictions = predictor.evaluate([])
    assert findings == []
    assert predictions == []
