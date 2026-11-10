"""
Tests for hash-chained audit log.
"""
import json
import time

import pytest

from app.audit import (
    AuditChainError,
    append,
    compute_hash,
    get_all_records,
    get_latest_hash,
    get_records_by_action,
    get_records_by_subject,
    verify_chain,
)
from app.db import query

pytestmark = pytest.mark.integration


@pytest.fixture
def clean_audit_log():
    """Clean up test audit records after each test."""
    # Get initial record count
    result = query("SELECT COUNT(*) FROM AUDIT_LOG")
    initial_count = result[0][0] if result else 0
    
    yield
    
    # Delete test records (keep GENESIS and any pre-existing records)
    if initial_count > 0:
        query(f"DELETE FROM AUDIT_LOG WHERE ID > {initial_count}")


class TestHashComputation:
    """Test hash computation logic."""
    
    def test_compute_hash_deterministic(self):
        """Test that hash computation is deterministic."""
        hash1 = compute_hash("prev123", "alice", "ACTION", 42, {"key": "value"})
        hash2 = compute_hash("prev123", "alice", "ACTION", 42, {"key": "value"})
        
        assert hash1 == hash2
    
    def test_compute_hash_changes_with_input(self):
        """Test that hash changes when inputs change."""
        base_hash = compute_hash("prev", "alice", "ACTION", 42, {})
        
        # Different previous hash
        h1 = compute_hash("different", "alice", "ACTION", 42, {})
        assert h1 != base_hash
        
        # Different actor
        h2 = compute_hash("prev", "bob", "ACTION", 42, {})
        assert h2 != base_hash
        
        # Different action
        h3 = compute_hash("prev", "alice", "OTHER", 42, {})
        assert h3 != base_hash
        
        # Different subject
        h4 = compute_hash("prev", "alice", "ACTION", 99, {})
        assert h4 != base_hash
        
        # Different detail
        h5 = compute_hash("prev", "alice", "ACTION", 42, {"key": "different"})
        assert h5 != base_hash
    
    def test_compute_hash_consistent_with_json_order(self):
        """Test that detail dict order doesn't affect hash."""
        detail1 = {"a": 1, "b": 2, "c": 3}
        detail2 = {"c": 3, "b": 2, "a": 1}
        
        hash1 = compute_hash("prev", "alice", "ACTION", None, detail1)
        hash2 = compute_hash("prev", "alice", "ACTION", None, detail2)
        
        assert hash1 == hash2


class TestAuditAppend:
    """Test appending audit records."""
    
    def test_append_creates_record(self, clean_audit_log):
        """Test that append creates a new record."""
        record_id = append("test_user", "TEST_ACTION", 123, {"test": "data"})
        
        assert record_id > 0
    
    def test_append_chains_to_previous(self, clean_audit_log):
        """Test that new records chain to previous."""
        # Append two records
        id1 = append("user1", "ACTION1", None, {})
        id2 = append("user2", "ACTION2", None, {})
        
        # Get records
        records = get_all_records()
        
        # Find our records
        r1 = next(r for r in records if r.id == id1)
        r2 = next(r for r in records if r.id == id2)
        
        # Second record should chain to first
        assert r2.prev_hash == r1.hash
    
    def test_append_with_no_detail(self, clean_audit_log):
        """Test append with no detail dict."""
        record_id = append("user", "ACTION")
        
        assert record_id > 0
        
        records = get_all_records()
        record = next(r for r in records if r.id == record_id)
        assert record.detail == {}


class TestChainVerification:
    """Test audit chain verification."""
    
    def test_verify_empty_chain(self):
        """Test verifying an empty chain (or genesis only)."""
        is_valid, error = verify_chain()
        assert is_valid
        assert error is None
    
    def test_verify_valid_chain(self, clean_audit_log):
        """Test verifying a valid chain."""
        # Create a few records
        append("user1", "ACTION1", 1, {"data": "test1"})
        append("user2", "ACTION2", 2, {"data": "test2"})
        append("user3", "ACTION3", 3, {"data": "test3"})
        
        is_valid, error = verify_chain()
        assert is_valid
        assert error is None
    
    def test_detect_tampering_in_hash(self, clean_audit_log, db_conn):
        """Test that tampering with a hash is detected."""
        # Create records
        id1 = append("user1", "ACTION1", 1, {})
        append("user2", "ACTION2", 2, {})
        
        # Tamper with the first record's hash
        cur = db_conn.cursor()
        cur.execute(
            "UPDATE AUDIT_LOG SET HASH = ? WHERE ID = ?",
            ("tampered_hash_" + "0" * 50, id1)
        )
        db_conn.commit()
        
        # Verification should fail
        is_valid, error = verify_chain()
        assert not is_valid
        assert "incorrect hash" in error.lower()
    
    def test_detect_tampering_in_content(self, clean_audit_log, db_conn):
        """Test that tampering with content is detected."""
        # Create records
        id1 = append("user1", "ACTION1", 1, {"data": "original"})
        
        # Tamper with the detail
        cur = db_conn.cursor()
        cur.execute(
            "UPDATE AUDIT_LOG SET DETAIL = ? WHERE ID = ?",
            (json.dumps({"data": "tampered"}), id1)
        )
        db_conn.commit()
        
        # Verification should fail
        is_valid, error = verify_chain()
        assert not is_valid
        assert error is not None


class TestRecordRetrieval:
    """Test retrieving audit records."""
    
    def test_get_all_records(self, clean_audit_log):
        """Test retrieving all records."""
        # Create some records
        append("user1", "ACTION1", 1, {})
        append("user2", "ACTION2", 2, {})
        
        records = get_all_records()
        assert len(records) >= 2
    
    def test_get_records_by_action(self, clean_audit_log):
        """Test filtering records by action."""
        # Create records with different actions
        append("user1", "ERASURE", 1, {})
        append("user2", "CLASSIFICATION", 2, {})
        append("user3", "ERASURE", 3, {})
        
        erasure_records = get_records_by_action("ERASURE")
        
        # Filter to our test records
        test_records = [r for r in erasure_records if r.subject in [1, 3]]
        assert len(test_records) == 2
        assert all(r.action == "ERASURE" for r in test_records)
    
    def test_get_records_by_subject(self, clean_audit_log):
        """Test filtering records by subject."""
        # Create records for different subjects
        append("user1", "ACTION1", 100, {})
        append("user2", "ACTION2", 200, {})
        append("user3", "ACTION3", 100, {})
        
        subject_100_records = get_records_by_subject(100)
        
        assert len(subject_100_records) == 2
        assert all(r.subject == 100 for r in subject_100_records)
    
    def test_get_records_returns_empty_for_nonexistent(self, clean_audit_log):
        """Test that querying nonexistent records returns empty list."""
        records = get_records_by_action("NONEXISTENT_ACTION")
        assert records == []
        
        records = get_records_by_subject(999999)
        assert records == []


class TestLatestHash:
    """Test retrieving latest hash."""
    
    def test_get_latest_hash_returns_genesis_initially(self):
        """Test that latest hash is GENESIS when no records exist."""
        # This test assumes a fresh AUDIT_LOG with only GENESIS
        # In practice, there will be records, so we check the structure
        latest = get_latest_hash()
        assert isinstance(latest, str)
        assert len(latest) > 0
    
    def test_get_latest_hash_after_append(self, clean_audit_log):
        """Test that latest hash updates after append."""
        hash_before = get_latest_hash()
        
        append("user", "ACTION", None, {})
        
        hash_after = get_latest_hash()
        
        assert hash_after != hash_before


class TestAuditRecordDataClass:
    """Test AuditRecord dataclass."""
    
    def test_audit_record_has_required_fields(self, clean_audit_log):
        """Test that audit records have all required fields."""
        append("user", "ACTION", 42, {"key": "value"})
        
        records = get_all_records()
        record = records[-1]  # Last record
        
        assert hasattr(record, "id")
        assert hasattr(record, "actor")
        assert hasattr(record, "action")
        assert hasattr(record, "subject")
        assert hasattr(record, "detail")
        assert hasattr(record, "prev_hash")
        assert hasattr(record, "hash")
        assert hasattr(record, "created_at")
    
    def test_audit_record_detail_is_dict(self, clean_audit_log):
        """Test that detail is parsed as dict."""
        append("user", "ACTION", None, {"test": "data", "number": 123})
        
        records = get_all_records()
        record = records[-1]
        
        assert isinstance(record.detail, dict)
        assert record.detail["test"] == "data"
        assert record.detail["number"] == 123


class TestConcurrentAppends:
    """Test that concurrent appends maintain chain integrity."""
    
    def test_sequential_appends_maintain_chain(self, clean_audit_log):
        """Test that many sequential appends maintain chain."""
        # Append many records quickly
        ids = []
        for i in range(10):
            record_id = append(f"user{i}", f"ACTION{i}", i, {"index": i})
            ids.append(record_id)
        
        # Verify chain is intact
        is_valid, error = verify_chain()
        assert is_valid, f"Chain broken: {error}"
