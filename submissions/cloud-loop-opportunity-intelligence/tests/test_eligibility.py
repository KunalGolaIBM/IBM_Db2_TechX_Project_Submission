from backend.app.services.eligibility_service import eligibility_service

def test_eligibility_undergrad():
    opportunity = {
        "opportunity_type": "internship",
        "eligibility": "Currently enrolled students in 2026 or 2027 batch",
    }
    profile = {
        "degree": "B.Tech",
        "study_year": 3,
        "graduation_batch": "2026",
    }
    eligible, reason = eligibility_service.check_eligibility(opportunity, profile)
    assert eligible is True
    assert "eligible" in reason.lower()

def test_deadline_status():
    status = eligibility_service.check_deadline_status("Ongoing")
    assert status == "ongoing"

    status_past = eligibility_service.check_deadline_status("2020-01-01")
    assert status_past == "expired"

