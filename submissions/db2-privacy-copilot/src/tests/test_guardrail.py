"""
Tests for the SQL guardrail.

These are security tests - they verify that malicious/dangerous
SQL cannot bypass the guardrail.
"""
import pytest

from app.guardrail import (
    Blocked,
    check,
    check_plan_hash,
    check_retention_rule_exists,
    check_transaction_size,
    extract_table_name,
)


class TestValidStatements:
    """Test that valid statements are allowed."""
    
    def test_valid_delete(self):
        """Test that a valid DELETE statement passes."""
        sql = 'DELETE FROM "DB2INST1"."PATIENT" WHERE "ID" = ?'
        check(sql, {"PATIENT"}, approved=True)
        # Should not raise
    
    def test_valid_update(self):
        """Test that a valid UPDATE statement passes."""
        sql = 'UPDATE "DB2INST1"."PATIENT" SET "NAME" = NULL WHERE "ID" = ?'
        check(sql, {"PATIENT"}, approved=True)
        # Should not raise
    
    def test_multiple_set_clauses(self):
        """Test UPDATE with multiple SET clauses."""
        sql = '''UPDATE "DB2INST1"."PATIENT" 
                 SET "NAME" = NULL, "EMAIL" = NULL 
                 WHERE "ID" = ?'''
        check(sql, {"PATIENT"}, approved=True)
        # Should not raise


class TestApprovalRequired:
    """Test that approval is enforced."""
    
    def test_blocks_without_approval(self):
        """Test that statements without approval are blocked."""
        sql = 'DELETE FROM "DB2INST1"."PATIENT" WHERE "ID" = ?'
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=False)
        
        assert "approval required" in str(exc_info.value).lower()


class TestBannedTokens:
    """Test that banned SQL tokens are blocked."""
    
    @pytest.mark.parametrize("sql,token", [
        ('DROP TABLE "DB2INST1"."PATIENT"', "DROP"),
        ('TRUNCATE TABLE "DB2INST1"."PATIENT"', "TRUNCATE"),
        ('ALTER TABLE "DB2INST1"."PATIENT" DROP COLUMN "NAME"', "ALTER"),
        ('GRANT ALL ON "DB2INST1"."PATIENT" TO PUBLIC', "GRANT"),
        ('REVOKE SELECT ON "DB2INST1"."PATIENT" FROM PUBLIC', "REVOKE"),
        ('CREATE TABLE "DB2INST1"."EVIL" (X INT)', "CREATE"),
        ('CALL SYSPROC.ADMIN_CMD(?)', "CALL"),
        ('EXEC sp_executesql ?', "EXEC"),
        ('INSERT INTO "DB2INST1"."PATIENT" VALUES (?)', "INSERT"),
        ('MERGE INTO "DB2INST1"."PATIENT" AS T USING (VALUES(?)) AS S ON T.ID=S.C1', "MERGE"),
    ])
    def test_blocks_banned_token(self, sql, token):
        """Test that statements with banned tokens are blocked."""
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        assert "banned token" in str(exc_info.value).lower()


class TestSQLInjection:
    """Test that SQL injection attempts are blocked."""
    
    def test_blocks_stacked_statement(self):
        """Test that stacked statements are blocked."""
        sql = 'DELETE FROM "DB2INST1"."PATIENT" WHERE "ID" = ?; DROP TABLE X'
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        assert "banned token" in str(exc_info.value).lower()
    
    def test_blocks_sql_comment(self):
        """Test that SQL comments are blocked."""
        sql = 'DELETE FROM "DB2INST1"."PATIENT" WHERE "ID" = ? --comment'
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        # Should block either the comment or the missing WHERE with param
        assert "banned" in str(exc_info.value).lower() or "shape" in str(exc_info.value).lower()
    
    def test_blocks_block_comment(self):
        """Test that block comments are blocked."""
        sql = 'DELETE FROM "DB2INST1"."PATIENT" /* comment */ WHERE "ID" = ?'
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        assert "banned token" in str(exc_info.value).lower()
    
    def test_blocks_always_true_condition(self):
        """Test that always-true conditions are blocked."""
        sql = 'DELETE FROM "DB2INST1"."PATIENT" WHERE 1=1'
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        # Should block for missing parameter or suspicious pattern
        assert "suspicious" in str(exc_info.value).lower() or "parameter" in str(exc_info.value).lower()
    
    def test_blocks_string_injection(self):
        """Test that string-based injection is blocked."""
        sql = """DELETE FROM "DB2INST1"."PATIENT" WHERE "NAME" = 'x' OR '1'='1'"""
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        assert "suspicious" in str(exc_info.value).lower() or "parameter" in str(exc_info.value).lower()


class TestWhereClauseEnforcement:
    """Test that WHERE clause is mandatory."""
    
    def test_blocks_delete_without_where(self):
        """Test that DELETE without WHERE is blocked."""
        sql = 'DELETE FROM "DB2INST1"."PATIENT"'
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        assert "where" in str(exc_info.value).lower()
    
    def test_blocks_update_without_where(self):
        """Test that UPDATE without WHERE is blocked."""
        sql = 'UPDATE "DB2INST1"."PATIENT" SET "NAME" = NULL'
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        assert "where" in str(exc_info.value).lower() or "shape" in str(exc_info.value).lower()


class TestParameterizedValues:
    """Test that parameterized values are enforced."""
    
    def test_blocks_literal_values(self):
        """Test that statements with literal values are blocked."""
        sql = 'DELETE FROM "DB2INST1"."PATIENT" WHERE "ID" = 123'
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        assert "parameter" in str(exc_info.value).lower() or "?" in str(exc_info.value)


class TestTableAllowlist:
    """Test that only approved tables can be modified."""
    
    def test_blocks_unapproved_table(self):
        """Test that statements on unapproved tables are blocked."""
        sql = 'DELETE FROM "DB2INST1"."EVIL_TABLE" WHERE "ID" = ?'
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        assert "not in approved plan" in str(exc_info.value).lower()
    
    def test_allows_approved_table(self):
        """Test that statements on approved tables are allowed."""
        sql = 'DELETE FROM "DB2INST1"."PATIENT" WHERE "ID" = ?'
        check(sql, {"PATIENT", "APPOINTMENT"}, approved=True)
        # Should not raise


class TestTableNameExtraction:
    """Test table name extraction."""
    
    def test_extract_from_delete(self):
        """Test extracting table name from DELETE."""
        sql = 'DELETE FROM "DB2INST1"."PATIENT" WHERE "ID" = ?'
        table = extract_table_name(sql)
        assert table == "PATIENT"
    
    def test_extract_from_update(self):
        """Test extracting table name from UPDATE."""
        sql = 'UPDATE "DB2INST1"."APPOINTMENT" SET "STATUS" = NULL WHERE "ID" = ?'
        table = extract_table_name(sql)
        assert table == "APPOINTMENT"
    
    def test_extract_returns_none_on_invalid(self):
        """Test that extraction returns None for invalid SQL."""
        sql = "SELECT * FROM PATIENT"
        table = extract_table_name(sql)
        assert table is None


class TestPlanHashValidation:
    """Test plan hash validation."""
    
    def test_matching_hashes_pass(self):
        """Test that matching hashes pass validation."""
        plan = '{"steps": [{"table": "PATIENT", "action": "ERASE"}]}'
        import hashlib
        hash_value = hashlib.sha256(plan.encode()).hexdigest()
        
        check_plan_hash(plan, hash_value)
        # Should not raise
    
    def test_mismatched_hashes_blocked(self):
        """Test that mismatched hashes are blocked."""
        plan = '{"steps": [{"table": "PATIENT", "action": "ERASE"}]}'
        wrong_hash = "0" * 64
        
        with pytest.raises(Blocked) as exc_info:
            check_plan_hash(plan, wrong_hash)
        
        assert "changed since approval" in str(exc_info.value).lower()


class TestRetentionRuleCheck:
    """Test retention rule checking."""
    
    def test_blocks_missing_rule(self):
        """Test that missing retention rules are blocked."""
        with pytest.raises(Blocked) as exc_info:
            check_retention_rule_exists("UNKNOWN_TABLE", {"PATIENT": "ERASE"})
        
        assert "no retention rule" in str(exc_info.value).lower()
    
    def test_allows_existing_rule(self):
        """Test that existing retention rules pass."""
        check_retention_rule_exists("PATIENT", {"PATIENT": "ERASE"})
        # Should not raise


class TestTransactionSize:
    """Test transaction size limits."""
    
    def test_blocks_large_transaction(self):
        """Test that oversized transactions are blocked."""
        with pytest.raises(Blocked) as exc_info:
            check_transaction_size(150000, max_rows=100000)
        
        assert "too large" in str(exc_info.value).lower()
    
    def test_allows_normal_transaction(self):
        """Test that normal-sized transactions pass."""
        check_transaction_size(5000, max_rows=100000)
        # Should not raise


class TestStatementShape:
    """Test statement shape validation."""
    
    def test_blocks_select(self):
        """Test that SELECT is blocked."""
        sql = 'SELECT * FROM "DB2INST1"."PATIENT" WHERE "ID" = ?'
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        assert "shape" in str(exc_info.value).lower()
    
    def test_blocks_malformed_delete(self):
        """Test that malformed DELETE is blocked."""
        sql = 'DELETE "DB2INST1"."PATIENT" WHERE "ID" = ?'  # Missing FROM
        
        with pytest.raises(Blocked) as exc_info:
            check(sql, {"PATIENT"}, approved=True)
        
        assert "shape" in str(exc_info.value).lower()


class TestEdgeCases:
    """Test edge cases."""
    
    def test_handles_whitespace(self):
        """Test that extra whitespace doesn't break validation."""
        sql = '''  DELETE   FROM   "DB2INST1"."PATIENT"   
                 WHERE   "ID"   =   ?  '''
        check(sql, {"PATIENT"}, approved=True)
        # Should not raise
    
    def test_case_insensitive_keywords(self):
        """Test that keyword case doesn't matter."""
        sql = 'delete from "DB2INST1"."PATIENT" where "ID" = ?'
        check(sql, {"PATIENT"}, approved=True)
        # Should not raise
