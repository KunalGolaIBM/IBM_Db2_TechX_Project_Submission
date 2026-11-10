"""
Tests for bitemporal consent ledger.
"""
from datetime import date, datetime, timedelta

import pytest

from app.consent import (
    ConsentError,
    ConsentInvalid,
    consent_gate,
    current_consents,
    grant,
    history,
    valid_on,
    withdraw,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def test_patient_id(db_conn):
    """Create a test patient and return the ID."""
    cur = db_conn.cursor()
    cur.execute("""
        INSERT INTO PATIENT (FULL_NM, CUST_MAIL_ID, PH_NO, DOB_DT, GOVT_ID, ADDR1, CITY_NM, PINCODE)
        VALUES ('Consent Test', 'consent@test.com', 9999999999, '1990-01-01', 'TESTX1234Y', 
                'Test Addr', 'Test City', '111111')
    """)
    db_conn.commit()
    
    cur.execute("SELECT ID FROM PATIENT WHERE CUST_MAIL_ID = 'consent@test.com'")
    patient_id = int(cur.fetchone()[0])
    
    yield patient_id
    
    # Cleanup
    cur.execute("DELETE FROM CONSENT WHERE PATIENT_ID = ?", (patient_id,))
    cur.execute("DELETE FROM CONSENT_HISTORY WHERE PATIENT_ID = ?", (patient_id,))
    cur.execute("DELETE FROM PATIENT WHERE ID = ?", (patient_id,))
    db_conn.commit()


class TestConsentGrant:
    """Tests for granting consent."""
    
    def test_grant_consent_success(self, test_patient_id):
        """Test successful consent grant."""
        grant(test_patient_id, "MARKETING", "2026-01-01", "2026-12-31")
        
        # Verify consent was recorded
        assert valid_on(test_patient_id, "MARKETING", "2026-06-01")
    
    def test_grant_consent_with_date_objects(self, test_patient_id):
        """Test granting consent with date objects."""
        start = date(2026, 1, 1)
        end = date(2026, 12, 31)
        
        grant(test_patient_id, "RESEARCH", start, end)
        assert valid_on(test_patient_id, "RESEARCH", "2026-06-01")
    
    def test_grant_consent_invalid_patient(self):
        """Test granting consent for non-existent patient."""
        with pytest.raises(ConsentError):
            grant(999999, "MARKETING", "2026-01-01")
    
    def test_grant_consent_far_future(self, test_patient_id):
        """Test granting consent with default far future end date."""
        grant(test_patient_id, "TREATMENT", "2026-01-01")
        
        # Should be valid far in the future
        assert valid_on(test_patient_id, "TREATMENT", "2050-01-01")


class TestConsentWithdraw:
    """Tests for withdrawing consent."""
    
    def test_withdraw_consent_success(self, test_patient_id):
        """Test successful consent withdrawal."""
        # Grant then withdraw
        grant(test_patient_id, "MARKETING", "2026-01-01", "2026-12-31")
        withdraw(test_patient_id, "MARKETING", "2026-07-01")
        
        # Should be valid before withdrawal
        assert valid_on(test_patient_id, "MARKETING", "2026-06-15")
        
        # Should be invalid after withdrawal
        assert not valid_on(test_patient_id, "MARKETING", "2026-07-15")
    
    def test_withdraw_nonexistent_consent(self, test_patient_id):
        """Test withdrawing consent that was never granted."""
        # Should not raise error, just record withdrawal
        withdraw(test_patient_id, "NEVER_GRANTED", "2026-01-01")
    
    def test_withdraw_with_date_object(self, test_patient_id):
        """Test withdrawal with date object."""
        grant(test_patient_id, "MARKETING", "2026-01-01")
        withdraw(test_patient_id, "MARKETING", date(2026, 7, 1))
        
        assert not valid_on(test_patient_id, "MARKETING", "2026-07-15")


class TestConsentValidation:
    """Tests for checking consent validity."""
    
    def test_valid_on_within_period(self, test_patient_id):
        """Test consent is valid within granted period."""
        grant(test_patient_id, "MARKETING", "2026-01-01", "2026-12-31")
        
        assert valid_on(test_patient_id, "MARKETING", "2026-01-01")
        assert valid_on(test_patient_id, "MARKETING", "2026-06-15")
        assert not valid_on(test_patient_id, "MARKETING", "2026-12-31")
    
    def test_valid_on_outside_period(self, test_patient_id):
        """Test consent is invalid outside granted period."""
        grant(test_patient_id, "MARKETING", "2026-01-01", "2026-12-31")
        
        assert not valid_on(test_patient_id, "MARKETING", "2025-12-31")
        assert not valid_on(test_patient_id, "MARKETING", "2027-01-01")
    
    def test_valid_on_never_granted(self, test_patient_id):
        """Test consent check when never granted."""
        assert not valid_on(test_patient_id, "NEVER_GRANTED", "2026-01-01")
    
    def test_valid_on_with_date_object(self, test_patient_id):
        """Test validation with date object."""
        grant(test_patient_id, "MARKETING", "2026-01-01", "2026-12-31")
        
        assert valid_on(test_patient_id, "MARKETING", date(2026, 6, 15))


class TestConsentGate:
    """Tests for consent gate (raises on invalid)."""
    
    def test_consent_gate_allows_valid(self, test_patient_id):
        """Test gate allows when consent is valid."""
        # Grant consent for today
        today = date.today()
        grant(test_patient_id, "PROCESSING", today.isoformat(), "2027-01-01")
        
        # Should not raise
        consent_gate(test_patient_id, "PROCESSING")
    
    def test_consent_gate_blocks_invalid(self, test_patient_id):
        """Test gate blocks when consent is invalid."""
        # Grant consent in the past
        grant(test_patient_id, "PROCESSING", "2020-01-01", "2020-12-31")
        
        # Should raise ConsentInvalid
        with pytest.raises(ConsentInvalid):
            consent_gate(test_patient_id, "PROCESSING")


class TestConsentHistory:
    """Tests for consent history tracking."""
    
    def test_history_tracks_changes(self, test_patient_id):
        """Test that history preserves all versions."""
        # Grant consent
        grant(test_patient_id, "MARKETING", "2026-01-01", "2026-12-31")
        
        # Withdraw it
        withdraw(test_patient_id, "MARKETING", "2026-07-01")
        
        # Check history
        hist = history(test_patient_id, "MARKETING")
        
        # Should have records (exact count depends on implementation)
        assert len(hist) >= 1
        
        # History should show the change
        assert any(r["granted"] for r in hist)
    
    def test_history_empty_for_new_patient(self, test_patient_id):
        """Test history is empty for patient with no consent records."""
        hist = history(test_patient_id)
        assert hist == []
    
    def test_history_filters_by_purpose(self, test_patient_id):
        """Test history filtering by purpose."""
        grant(test_patient_id, "MARKETING", "2026-01-01")
        grant(test_patient_id, "RESEARCH", "2026-01-01")
        
        marketing_hist = history(test_patient_id, "MARKETING")
        research_hist = history(test_patient_id, "RESEARCH")
        
        # Each should have records for only that purpose
        assert all(r["purpose"] == "MARKETING" for r in marketing_hist)
        assert all(r["purpose"] == "RESEARCH" for r in research_hist)


class TestCurrentConsents:
    """Tests for retrieving current consents."""
    
    def test_current_consents_shows_active(self, test_patient_id):
        """Test current consents shows active consents."""
        grant(test_patient_id, "MARKETING", "2026-01-01")
        grant(test_patient_id, "RESEARCH", "2026-01-01")
        
        current = current_consents(test_patient_id)
        
        assert len(current) >= 2
        purposes = [c["purpose"] for c in current]
        assert "MARKETING" in purposes
        assert "RESEARCH" in purposes
    
    def test_current_consents_empty(self, test_patient_id):
        """Test current consents when none granted."""
        current = current_consents(test_patient_id)
        assert current == []


class TestBitemporalQueries:
    """Tests for bitemporal querying (system time + business time)."""
    
    def test_system_time_as_of(self, test_patient_id):
        """Test querying system time 'as of' a past point."""
        # Grant consent
        grant(test_patient_id, "MARKETING", "2026-01-01", "2026-12-31")
        
        # Record the time
        granted_at = datetime.now()
        
        # Wait a moment (in real test, would be longer)
        import time
        time.sleep(0.1)
        
        # Withdraw consent
        withdraw(test_patient_id, "MARKETING", "2026-07-01")
        
        # Query as of before withdrawal
        # Note: This tests the system time dimension
        is_valid_then = valid_on(
            test_patient_id,
            "MARKETING",
            "2026-06-15",
            known_at=granted_at
        )
        
        # Should be valid in the past system state
        assert is_valid_then
    
    def test_business_time_as_of(self, test_patient_id):
        """Test business time dimension (valid when)."""
        grant(test_patient_id, "MARKETING", "2026-06-01", "2026-08-31")
        
        # Business time queries
        assert not valid_on(test_patient_id, "MARKETING", "2026-05-31")  # Before
        assert valid_on(test_patient_id, "MARKETING", "2026-06-01")      # Start
        assert valid_on(test_patient_id, "MARKETING", "2026-07-15")      # During
        assert not valid_on(test_patient_id, "MARKETING", "2026-08-31")  # End is exclusive
        assert not valid_on(test_patient_id, "MARKETING", "2026-09-01")  # After
