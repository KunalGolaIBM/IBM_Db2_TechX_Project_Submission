"""
Test Category 3: Patient Creation and Demo Data Test
Validates synthetic patient schemas, code uniqueness, and seed definitions.
"""

from db.seed_demo_data import SYNTHETIC_PATIENTS


def test_synthetic_patients_count():
    """Verify at least 3 synthetic demo patients are defined."""
    assert len(SYNTHETIC_PATIENTS) >= 3


def test_synthetic_patients_structure():
    """Verify each patient has demo_code, display_name, and birth_year."""
    codes = set()
    for p in SYNTHETIC_PATIENTS:
        assert "demo_code" in p
        assert p["demo_code"].startswith("DEMO-")
        assert "display_name" in p
        assert len(p["display_name"]) > 3
        assert "birth_year" in p
        assert 1900 < p["birth_year"] < 2026
        codes.add(p["demo_code"])

    # Code uniqueness
    assert len(codes) == len(SYNTHETIC_PATIENTS)

