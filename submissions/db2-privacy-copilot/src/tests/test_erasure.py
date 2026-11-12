"""
Tests for erasure planning and execution.
"""
import pytest

from app.config import settings
from app.erasure import (
    ErasureError,
    PlanChanged,
    count_rows,
    execute,
    get_pii_columns,
    get_retention_rules,
    is_nullable,
    plan,
    plan_hash,
    rule_for,
    simulate,
)
from app.guardrail import Blocked

pytestmark = pytest.mark.integration


@pytest.fixture
def test_patient_with_data(db_conn, classified_erasure_columns):
    """Create a test patient with related data."""
    cur = db_conn.cursor()
    
    # Insert patient
    cur.execute("""
        INSERT INTO PATIENT (FULL_NM, CUST_MAIL_ID, PH_NO, DOB_DT, GOVT_ID, ADDR1, CITY_NM, PINCODE)
        VALUES ('Erasure Test', 'erasure@test.com', 8888888888, '1985-01-01', 'ERTST1234E', 
                'Test Address', 'Test City', '888888')
    """)
    db_conn.commit()
    
    cur.execute("SELECT ID FROM PATIENT WHERE CUST_MAIL_ID = 'erasure@test.com'")
    patient_id = int(cur.fetchone()[0])
    
    # Insert related appointment
    cur.execute("""
        INSERT INTO APPOINTMENT (PATIENT_ID, APPT_DT, APPT_TIME, DOCTOR_NM, REASON, STATUS)
        VALUES (?, '2026-06-15', '10:00:00', 'Dr. Test', 'Test appointment', 'SCHEDULED')
    """, (patient_id,))
    db_conn.commit()
    
    yield patient_id
    
    # Cleanup (cascading delete will handle related records)
    cur.execute("DELETE FROM APPOINTMENT WHERE PATIENT_ID = ?", (patient_id,))
    cur.execute("DELETE FROM PATIENT WHERE ID = ?", (patient_id,))
    db_conn.commit()


class TestRetentionRules:
    """Test retention rule retrieval."""
    
    def test_get_retention_rules(self):
        """Test retrieving all retention rules."""
        rules = get_retention_rules()
        
        assert isinstance(rules, dict)
        assert len(rules) > 0
        assert "PATIENT" in rules
    
    def test_rule_for_existing_table(self):
        """Test getting rule for existing table."""
        action, reason, verified = rule_for("PATIENT")
        
        assert action in ["ERASE", "ANONYMISE", "RETAIN"]
        assert isinstance(reason, str)
        assert len(reason) > 0
        assert isinstance(verified, bool)
    
    def test_rule_for_nonexistent_table(self):
        """Test that missing rule raises error."""
        with pytest.raises(ErasureError):
            rule_for("NONEXISTENT_TABLE")


class TestRowCounting:
    """Test row counting for planning."""
    
    def test_count_rows(self, test_patient_with_data):
        """Test counting rows for a subject."""
        count = count_rows(
            settings.db2_schema,
            "APPOINTMENT",
            "PATIENT_ID",
            test_patient_with_data
        )
        
        assert count >= 1  # We inserted at least one appointment
    
    def test_count_rows_nonexistent_patient(self):
        """Test counting for non-existent patient returns 0."""
        count = count_rows(
            settings.db2_schema,
            "APPOINTMENT",
            "PATIENT_ID",
            999999
        )
        
        assert count == 0


class TestPIIColumnDetection:
    """Test PII column detection."""
    
    def test_get_pii_columns(self):
        """Test getting PII columns for a table."""
        # Assuming classification has been run
        pii_cols = get_pii_columns("PATIENT")
        
        # Should have some PII columns (may be empty if classification not run)
        assert isinstance(pii_cols, list)
    
    def test_get_pii_columns_nonexistent_table(self):
        """Test getting PII columns for non-existent table."""
        pii_cols = get_pii_columns("NONEXISTENT")
        assert pii_cols == []


class TestNullableCheck:
    """Test nullable column checking."""
    
    def test_is_nullable(self):
        """Test checking if a column is nullable."""
        # PATIENT.NOTES is nullable (CLOB)
        nullable = is_nullable(settings.db2_schema, "PATIENT", "NOTES")
        assert isinstance(nullable, bool)
    
    def test_is_nullable_nonexistent_column(self):
        """Test nullable check on non-existent column."""
        nullable = is_nullable(settings.db2_schema, "PATIENT", "NONEXISTENT")
        assert nullable is False


class TestPlanGeneration:
    """Test erasure plan generation."""
    
    def test_plan_generates_steps(self, test_patient_with_data):
        """Test that plan generates steps."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        assert len(steps) > 0
        assert all(hasattr(s, "table") for s in steps)
        assert all(hasattr(s, "action") for s in steps)
        assert all(hasattr(s, "reason") for s in steps)
    
    def test_plan_includes_patient_table(self, test_patient_with_data):
        """Test that plan includes PATIENT table."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        table_names = [s.table for s in steps]
        assert "PATIENT" in table_names
    
    def test_plan_has_correct_actions(self, test_patient_with_data):
        """Test that plan actions match retention rules."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        for step in steps:
            assert step.action in ["ERASE", "ANONYMISE", "RETAIN"]
    
    def test_plan_generates_sql_for_erase(self, test_patient_with_data):
        """Test that ERASE steps have SQL."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        erase_steps = [s for s in steps if s.action == "ERASE"]
        
        for step in erase_steps:
            assert step.sql is not None
            assert "DELETE" in step.sql.upper()
            assert "?" in step.sql  # Parameterized
    
    def test_plan_no_sql_for_retain(self, test_patient_with_data):
        """Test that RETAIN steps have no SQL."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        retain_steps = [s for s in steps if s.action == "RETAIN"]
        
        for step in retain_steps:
            assert step.sql is None
    
    def test_plan_respects_retention_rules(self, test_patient_with_data):
        """Test that plan respects retention rules."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        # BILLING should be RETAIN (per retention rules)
        billing_steps = [s for s in steps if s.table == "BILLING"]
        if billing_steps:
            assert billing_steps[0].action == "RETAIN"


class TestPlanHashing:
    """Test plan hash computation."""
    
    def test_plan_hash_is_deterministic(self, test_patient_with_data):
        """Test that plan hash is deterministic."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        hash1 = plan_hash(steps)
        hash2 = plan_hash(steps)
        
        assert hash1 == hash2
    
    def test_plan_hash_changes_with_content(self, test_patient_with_data):
        """Test that plan hash changes when plan changes."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        hash1 = plan_hash(steps)
        
        # Modify a step
        steps[0].action = "DIFFERENT"
        
        hash2 = plan_hash(steps)
        
        assert hash1 != hash2


class TestSimulation:
    """Test plan simulation."""
    
    def test_simulate_returns_stats(self, test_patient_with_data):
        """Test that simulate returns statistics."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        sim = simulate(steps)
        
        assert "total_steps" in sim
        assert "total_rows" in sim
        assert "by_action" in sim
        assert "unverified_rules" in sim
        assert "has_unverified" in sim
    
    def test_simulate_counts_actions(self, test_patient_with_data):
        """Test that simulate counts by action."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        sim = simulate(steps)
        
        assert isinstance(sim["by_action"], dict)
        
        # Should have at least ERASE actions
        if "ERASE" in sim["by_action"]:
            assert sim["by_action"]["ERASE"]["tables"] > 0


class TestExecution:
    """Test erasure execution."""
    
    def test_execute_requires_matching_hash(self, test_patient_with_data):
        """Test that execution requires matching plan hash."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        correct_hash = plan_hash(steps)
        wrong_hash = "0" * 64
        
        with pytest.raises(PlanChanged):
            execute(
                steps,
                test_patient_with_data,
                "test@example.com",
                "approval_123",
                wrong_hash
            )
    
    def test_execute_validates_with_guardrail(self, test_patient_with_data):
        """Test that execution validates statements with guardrail."""
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        # Inject malicious SQL
        for step in steps:
            if step.sql:
                step.sql = 'DROP TABLE "DB2INST1"."PATIENT"'
                break
        
        correct_hash = plan_hash(steps)
        
        with pytest.raises(Blocked):
            execute(
                steps,
                test_patient_with_data,
                "test@example.com",
                "approval_123",
                correct_hash
            )
    
    @pytest.mark.integration
    def test_execute_anonymises_retained_patient(self, test_patient_with_data, db_conn):
        """Test that retained patient rows remain with identifying fields removed."""
        # This is a real execution test - be careful!
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        # Verify patient exists
        cur = db_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM PATIENT WHERE ID = ?", (test_patient_with_data,))
        count_before = cur.fetchone()[0]
        assert count_before == 1
        
        # Execute erasure
        correct_hash = plan_hash(steps)
        execute(
            steps,
            test_patient_with_data,
            "test_executor@example.com",
            "test_approval_001",
            correct_hash
        )
        
        cur.execute(
            "SELECT FULL_NM, CUST_MAIL_ID, PH_NO, GOVT_ID "
            "FROM PATIENT WHERE ID = ?",
            (test_patient_with_data,),
        )
        row_after = cur.fetchone()
        assert row_after is not None
        assert row_after == (None, None, None, None)
    
    @pytest.mark.integration
    def test_execute_creates_audit_record(self, test_patient_with_data):
        """Test that execution creates audit record."""
        from app.audit import get_records_by_subject
        
        steps = plan(test_patient_with_data, settings.db2_schema, "PATIENT")
        
        correct_hash = plan_hash(steps)
        execute(
            steps,
            test_patient_with_data,
            "auditor@example.com",
            "audit_approval_001",
            correct_hash
        )
        
        # Check audit log
        audit_records = get_records_by_subject(test_patient_with_data)
        erasure_records = [r for r in audit_records if r.action == "ERASURE"]
        
        assert len(erasure_records) >= 1
        
        # Check detail contains plan info
        latest = erasure_records[-1]
        assert "approval_id" in latest.detail
        assert "plan_hash" in latest.detail


class TestErrorHandling:
    """Test error handling in erasure."""
    
    def test_plan_handles_invalid_schema(self):
        """Test that planning with invalid schema fails gracefully."""
        with pytest.raises(ErasureError):
            plan(123, "INVALID_SCHEMA", "PATIENT")
    
    def test_plan_handles_invalid_root(self):
        """Test that planning with invalid root fails gracefully."""
        with pytest.raises(ErasureError):
            plan(123, settings.db2_schema, "NONEXISTENT_TABLE")
