"""Unit tests (no DB): PEP 503 normalization, synthetic fleet invariants, exposure windows on fixtures."""
from datetime import date

import pytest

from needle import sbom
from needle.sbom import OPEN_END, compute_exposure, exposure_sql, generate_fleet, normalize_pkg

D = date.fromisoformat
TODAY = D("2026-11-09")


@pytest.mark.parametrize("raw,norm", [
    ("PyYAML", "pyyaml"),
    ("Jinja2", "jinja2"),
    ("zope.interface", "zope-interface"),
    ("Foo__Bar.baz-qux", "foo-bar-baz-qux"),
    ("python_multipart", "python-multipart"),
    ("scikit-learn", "scikit-learn"),
    ("  Django ", "django"),
    ("a-_.-b", "a-b"),
])
def test_normalize_pep503(raw, norm):
    assert normalize_pkg(raw) == norm


def test_fleet_is_deterministic_and_well_formed():
    a, b = generate_fleet(), generate_fleet()
    assert a == b
    assert len(sbom.SERVICES) == 20
    by_key = {}
    for c in a:
        by_key.setdefault((c.service_id, c.package), []).append(c)
        assert c.package == normalize_pkg(c.package)
        assert c.bus_start < c.bus_end
    for periods in by_key.values():
        periods.sort(key=lambda c: c.bus_start)
        for p, q in zip(periods, periods[1:]):
            assert p.bus_end == q.bus_start  # adjacent, no overlap (WITHOUT OVERLAPS holds)
        assert periods[-1].bus_end == OPEN_END  # exactly one version deployed now
        assert sum(p.bus_end == OPEN_END for p in periods) == 1


def test_fleet_never_deploys_before_release():
    pkg_by_norm = {normalize_pkg(p): p for p in sbom.UPGRADE_PATHS}
    for c in generate_fleet():
        assert c.bus_start >= sbom.released(pkg_by_norm[c.package], c.version)


def _h(svc, pkg, ver, start, end="9999-12-31"):
    return {"service_id": svc, "package": pkg, "version": ver, "bus_start": D(start), "bus_end": D(end)}


HISTORY = [
    # A: exposed 5.1 -> 5.3 (one contiguous run), fixed by 5.4.1
    _h("A", "PyYAML", "5.1", "2020-01-01", "2021-01-01"),
    _h("A", "PyYAML", "5.3", "2021-01-01", "2022-01-01"),
    _h("A", "PyYAML", "5.4.1", "2022-01-01"),
    # B: affected now since first deploy
    _h("B", "pyyaml", "5.3", "2021-06-01"),
    # C: uses the package, version not listed -> NOT_CONFIRMED (never "safe")
    _h("C", "pyyaml", "6.0.1", "2023-01-01"),
    # D: gap in deployment breaks the run: two windows, the later one current
    _h("D", "pyyaml", "5.3", "2020-01-01", "2021-01-01"),
    _h("D", "pyyaml", "5.3", "2022-01-01"),
    # E: unrelated package
    _h("E", "requests", "2.31.0", "2023-01-01"),
]
AFFECTED = [("ADV-1", "PyYAML", "5.1"), ("ADV-1", "PyYAML", "5.3")]


def _rows():
    return {(r["SERVICE_ID"], r["STATUS"], r["EXPOSED_SINCE"]): r for r in compute_exposure(HISTORY, AFFECTED, TODAY)}


def test_exposure_contiguous_run_then_fixed():
    r = _rows()[("A", "PREVIOUSLY_AFFECTED", D("2020-01-01"))]
    assert r["EXPOSED_UNTIL"] == D("2022-01-01")
    assert r["DAYS_EXPOSED"] == 731
    assert r["VERSIONS"] == "5.1 > 5.3"
    assert r["VERSION_NOW"] is None


def test_exposure_affected_now_days_exposed():
    r = _rows()[("B", "AFFECTED", D("2021-06-01"))]
    assert r["VERSION_NOW"] == "5.3"
    assert r["EXPOSED_UNTIL"] is None
    assert r["DAYS_EXPOSED"] == (TODAY - D("2021-06-01")).days


def test_exposure_not_confirmed_is_not_safe():
    rows = [r for r in compute_exposure(HISTORY, AFFECTED, TODAY) if r["SERVICE_ID"] == "C"]
    assert [r["STATUS"] for r in rows] == ["NOT_CONFIRMED"]
    assert rows[0]["VERSION_NOW"] == "6.0.1"
    assert all(r["SERVICE_ID"] != "E" for r in compute_exposure(HISTORY, AFFECTED, TODAY))


def test_exposure_gap_splits_windows():
    rows = sorted((r for r in compute_exposure(HISTORY, AFFECTED, TODAY) if r["SERVICE_ID"] == "D"),
                  key=lambda r: r["EXPOSED_SINCE"])
    assert [(r["STATUS"], r["EXPOSED_SINCE"]) for r in rows] == [
        ("PREVIOUSLY_AFFECTED", D("2020-01-01")), ("AFFECTED", D("2022-01-01"))]


def test_exposure_sql_is_parameterised():
    sql = exposure_sql(3)
    assert "A.ADV_ID IN (?, ?, ?)" in sql
    assert "FOR BUSINESS_TIME AS OF CURRENT DATE" in sql
    assert "REGEXP_REPLACE(A.PACKAGE, '[-_.]+', '-')" in sql
    with pytest.raises(ValueError):
        exposure_sql(0)


def test_ddl_declares_application_period():
    ddl = sbom.SQL_FILE.read_text(encoding="utf-8")
    assert "PERIOD BUSINESS_TIME (BUS_START, BUS_END)" in ddl
    assert "BUSINESS_TIME WITHOUT OVERLAPS" in ddl
    pre, post = sbom._split_sql(ddl)
    assert any(s.startswith("CREATE TABLE NEEDLE.SBOM_COMPONENT") for s in pre)
    assert all("RUNSTATS" in s for s in post)


def test_unknown_coverage_for_range_only_advisories():
    # ADV-2 mentions PyYAML but enumerates no versions (OSV ranges only) -> UNKNOWN_COVERAGE, never silence.
    # ADV-1 enumerates versions -> its usual statuses, and no UNKNOWN_COVERAGE row.
    rows = compute_exposure(HISTORY, AFFECTED, TODAY, adv_packages={"ADV-1": ["PyYAML"], "ADV-2": ["PyYAML", "nope"]})
    uc = sorted((r["SERVICE_ID"], r["VERSION_NOW"]) for r in rows if r["STATUS"] == "UNKNOWN_COVERAGE")
    assert uc == [("A", "5.4.1"), ("B", "5.3"), ("C", "6.0.1"), ("D", "5.3")]
    assert all(r["ADV_ID"] == "ADV-2" for r in rows if r["STATUS"] == "UNKNOWN_COVERAGE")
    assert not any(r["ADV_ID"] == "ADV-1" and r["STATUS"] == "UNKNOWN_COVERAGE" for r in rows)


def test_exposure_sql_binds_the_id_list_twice():
    sql = exposure_sql(3)
    assert sql.count("?") == 6 and "'UNKNOWN_COVERAGE'" in sql and "D.ADV_ID IN (?, ?, ?)" in sql
