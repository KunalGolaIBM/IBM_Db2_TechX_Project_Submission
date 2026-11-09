from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from civiclens.domain import geo, text
from civiclens.domain.models import ComplaintCreate


def test_geo_cell_is_deterministic_and_local():
    assert geo.geo_cell(27.4964, 77.6767) == geo.geo_cell(27.4965, 77.6768)
    assert geo.geo_cell(27.4964, 77.6767) != geo.geo_cell(27.5100, 77.6767)
    lat, lon = geo.cell_center(geo.geo_cell(27.4964, 77.6767))
    assert abs(lat - 27.4964) < geo.CELL_SIZE_DEG and abs(lon - 77.6767) < geo.CELL_SIZE_DEG


def test_haversine_known_distance():
    # 0.001 deg latitude ~= 111 m
    assert 105 < geo.haversine_m(27.0, 77.0, 27.001, 77.0) < 117
    assert geo.haversine_m(10, 10, 10, 10) == 0


def test_bounding_box_contains_radius():
    min_lat, max_lat, min_lon, max_lon = geo.bounding_box(27.5, 77.6, 250)
    assert geo.haversine_m(27.5, 77.6, max_lat, 77.6) == pytest.approx(250, rel=1e-3)
    assert min_lon < 77.6 < max_lon and min_lat < 27.5


def test_fingerprint_ignores_case_order_and_stopwords():
    a = text.fingerprint("POTHOLE", "Big pothole", "on the main road")
    b = text.fingerprint("pothole", "MAIN road", "big pothole")
    assert a == b and len(a) == 64
    assert a != text.fingerprint("STREETLIGHT", "Big pothole", "on the main road")


def test_jaccard_and_score_bounds():
    assert text.jaccard("water leak pipe", "pipe water leak") == 1.0
    assert text.jaccard("", "x") == 0.0
    assert text.duplicate_score(0, 250, 1.0) == 1.0
    assert text.duplicate_score(500, 250, 0.0) == 0.0


def test_complaint_validation_rejects_bad_input():
    base = dict(category="POTHOLE", title="Hole", description="Deep", latitude=1, longitude=1)
    ComplaintCreate(**base)
    for override in (
        {"latitude": 91},
        {"severity": 9},
        {"category": "DROP TABLE"},
        {"source": "x;--"},
        {"title": ""},
    ):
        with pytest.raises(ValidationError):
            ComplaintCreate(**{**base, **override})


def test_reported_at_normalised_to_naive_utc():
    aware = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
    c = ComplaintCreate(
        category="OTHER", title="abc", description="abc", latitude=0, longitude=0, reported_at=aware
    )
    assert c.reported_at.tzinfo is None and c.reported_at.hour == 12
