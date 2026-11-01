"""
Unit and integration tests for IBM Db2 database operations and repository layer.
"""

import pytest
from internscrap.db.connection import SimulatedDb2Connection
from internscrap.db.repository import Db2Repository


@pytest.fixture
def test_repo():
    """Provides an isolated in-memory test database repository."""
    conn = SimulatedDb2Connection(":memory:")
    return Db2Repository(conn=conn)


def test_company_creation(test_repo):
    c_id = test_repo.get_or_create_company("IBM", "https://ibm.com", "Armonk, NY", "Enterprise AI", "Enterprise")
    assert c_id is not None
    # Deduplication test
    c_id_2 = test_repo.get_or_create_company("IBM")
    assert c_id == c_id_2


def test_skill_creation(test_repo):
    s_id = test_repo.get_or_create_skill("IBM Db2", "Database")
    assert s_id is not None
    s_id_2 = test_repo.get_or_create_skill("ibm db2")
    assert s_id == s_id_2


def test_internship_upsert_and_retrieval(test_repo):
    sample = {
        "title": "Software Engineering Intern - Db2",
        "company": "IBM",
        "location": "San Jose, CA",
        "is_remote": False,
        "stipend_min": 45.0,
        "stipend_max": 55.0,
        "currency": "USD",
        "apply_url": "https://ibm.com/careers/test",
        "source": "UnitTest",
        "external_id": "UNIT-001",
        "deadline": "2026-12-31",
        "skills": ["IBM Db2", "Python", "SQL"]
    }
    int_id = test_repo.upsert_internship(sample)
    assert int_id is not None

    item = test_repo.get_internship_by_id(int_id)
    assert item is not None
    assert item["TITLE"] == "Software Engineering Intern - Db2"
    assert item["COMPANY"] == "IBM"
    assert "IBM Db2" in item["SKILLS"]
    assert "Python" in item["SKILLS"]


def test_application_lifecycle_tracking(test_repo):
    sample = {
        "title": "Cloud Platform Intern",
        "company": "Red Hat",
        "apply_url": "https://redhat.com/apply",
        "source": "UnitTest",
        "external_id": "UNIT-002",
        "skills": ["Linux", "Kubernetes"]
    }
    int_id = test_repo.upsert_internship(sample)

    # 1. Track Wishlist
    test_repo.track_application(int_id, status="WISHLIST", notes="Preparing resume")
    apps = test_repo.list_applications()
    assert len(apps) == 1
    assert apps[0]["STATUS"] == "WISHLIST"

    # 2. Advance to APPLIED
    test_repo.track_application(int_id, status="APPLIED", notes="Submitted referral")
    apps = test_repo.list_applications()
    assert len(apps) == 1
    assert apps[0]["STATUS"] == "APPLIED"
    assert apps[0]["NOTES"] == "Submitted referral"


def test_analytics_and_views(test_repo):
    sample = {
        "title": "AI Intern",
        "company": "Scale AI",
        "apply_url": "https://scale.com/apply",
        "source": "UnitTest",
        "external_id": "UNIT-003",
        "skills": ["Python", "PyTorch"]
    }
    int_id = test_repo.upsert_internship(sample)
    test_repo.track_application(int_id, status="OFFER")

    analytics = test_repo.get_analytics()
    assert analytics["total_internships"] >= 1
    assert analytics["total_companies"] >= 1
    assert len(analytics["funnel"]) >= 1
    assert any(row["STAGE"] == "OFFER" for row in analytics["funnel"])
