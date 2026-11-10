"""DB tests for the app layer (run: PYTHONPATH=src pytest -m db tests/test_app_db.py).

They need the fleet loaded (python -m needle.sbom --load) and the RCAC users from needle/.env.
"""
from datetime import date

import pytest

from needle import sbom

pytestmark = pytest.mark.db


def _connect(user=None):
    import ibm_db  # noqa: F401

    try:
        return sbom.connect_as(user, timeout_s=15)
    except Exception as e:  # unreachable DB or missing credentials -> skip, never a false pass
        pytest.skip(f"Db2 not reachable as {user or 'DB2_USER'}: {str(e)[:80]}")


def _rows(conn, sql, params=()):
    import ibm_db

    st = ibm_db.prepare(conn, sql)
    ibm_db.execute(st, tuple(params))
    out, r = [], ibm_db.fetch_assoc(st)
    while r:
        out.append({k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()})
        r = ibm_db.fetch_assoc(st)
    return out


def test_deployed_now_matches_generator():
    import ibm_db

    conn = _connect()
    try:
        rows = _rows(conn, "SELECT SERVICE_ID, PACKAGE, VERSION FROM NEEDLE.SBOM_COMPONENT "
                           "FOR BUSINESS_TIME AS OF CURRENT DATE")
    finally:
        ibm_db.close(conn)
    gen = {(c.service_id, c.package, c.version) for c in sbom.generate_fleet() if c.bus_end == sbom.OPEN_END}
    assert {(r["SERVICE_ID"], r["PACKAGE"], r["VERSION"]) for r in rows} == gen


def test_without_overlaps_rejects_overlapping_period():
    import ibm_db

    conn = _connect()
    try:
        ibm_db.autocommit(conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        st = ibm_db.prepare(conn, "INSERT INTO NEEDLE.SBOM_COMPONENT (SERVICE_ID, PACKAGE, VERSION, BUS_START, BUS_END)"
                                  " VALUES ('SVC-16', 'pyyaml', '6.0.1', '2024-01-01', '2024-06-01')")
        with pytest.raises(Exception) as ei:
            ibm_db.execute(st)
        assert "SQL0803N" in str(ei.value) or "23505" in str(ei.value)
    finally:
        ibm_db.rollback(conn)
        ibm_db.close(conn)


def test_sql_exposure_equals_python_mirror():
    import ibm_db

    conn = _connect()  # SQL correctness, not RCAC: any user that can read the advisories
    try:
        ids = [r["ADV_ID"] for r in _rows(conn, "SELECT DISTINCT A.ADV_ID FROM NEEDLE.ADV_AFFECTED A "
                                                "WHERE A.PACKAGE = 'pyyaml' AND A.VERSION IN ('5.1', '5.3', '5.3.1') "
                                                "AND EXISTS (SELECT 1 FROM NEEDLE.ADV_DOC D WHERE D.ADV_ID = A.ADV_ID)")]
        assert ids, "no visible PyYAML advisories"
        sql_rows = sbom.fetch_exposure(conn, ids)
        today = _rows(conn, "SELECT CURRENT DATE AS D FROM SYSIBM.SYSDUMMY1")[0]["D"]
        marks = ", ".join("?" * len(ids))
        aff = [(r["ADV_ID"], r["PACKAGE"], r["VERSION"]) for r in _rows(
            conn, f"SELECT ADV_ID, PACKAGE, VERSION FROM NEEDLE.ADV_AFFECTED WHERE ECOSYSTEM = 'PyPI' "
                  f"AND ADV_ID IN ({marks})", ids)]
        adv_pk = {r["ADV_ID"]: [p for p in (r["PACKAGES"] or "").split(", ") if p] for r in _rows(
            conn, f"SELECT ADV_ID, PACKAGES FROM NEEDLE.ADV_DOC WHERE ADV_ID IN ({marks})", ids)}
    finally:
        ibm_db.close(conn)
    hist = [c.__dict__ for c in sbom.generate_fleet()]
    py_rows = sbom.compute_exposure(hist, aff, today if isinstance(today, date) else date.fromisoformat(str(today)),
                                    adv_packages=adv_pk)

    def key(r):
        return (r["SERVICE_ID"], r["PACKAGE"], r["ADV_ID"], r["STATUS"], str(r["EXPOSED_SINCE"] or ""),
                r["DAYS_EXPOSED"])

    assert sorted(map(key, sql_rows)) == sorted(map(key, py_rows))
    assert any(r["STATUS"] == "AFFECTED" for r in sql_rows)


def test_junior_never_sees_embargoed_advisories_in_exposure():
    import ibm_db

    senior = _connect("NDL_SENIOR")  # sees embargoed rows (SEES_EMBARGO = 1)
    try:
        emb = [r["ADV_ID"] for r in _rows(senior, "SELECT ADV_ID FROM NEEDLE.ADV_DOC "
                                                  "WHERE EMBARGO_UNTIL > CURRENT TIMESTAMP FETCH FIRST 20 ROWS ONLY")]
    except Exception as e:
        pytest.skip(f"NDL_SENIOR cannot read ADV_DOC yet (RCAC grants not applied?): {str(e)[:60]}")
    finally:
        ibm_db.close(senior)
    if not emb:
        pytest.skip("no embargoed advisories visible to NDL_SENIOR")
    junior = _connect("NDL_JUNIOR")
    try:
        from needle.retriever import fetch_docs

        assert fetch_docs(junior, emb) == {}
        assert sbom.fetch_exposure(junior, emb) == []
    finally:
        ibm_db.close(junior)


def test_range_only_advisory_gives_unknown_coverage():
    """GHSA-54qj-48vx-cr9f names django but enumerates no versions in OSV (checked 2026-11-09)."""
    import ibm_db

    conn = _connect("NDL_SENIOR")
    try:
        n_aff = _rows(conn, "SELECT COUNT(*) AS N FROM NEEDLE.ADV_AFFECTED WHERE ADV_ID = 'GHSA-54qj-48vx-cr9f'")
        if not _rows(conn, "SELECT 1 AS X FROM NEEDLE.ADV_DOC WHERE ADV_ID = 'GHSA-54qj-48vx-cr9f'"):
            pytest.skip("GHSA-54qj-48vx-cr9f not visible")
        rows = sbom.fetch_exposure(conn, ["GHSA-54qj-48vx-cr9f"])
    finally:
        ibm_db.close(conn)
    assert int(n_aff[0]["N"]) == 0
    django_now = {c.service_id for c in sbom.generate_fleet() if c.package == "django" and c.bus_end == sbom.OPEN_END}
    assert {r["SERVICE_ID"] for r in rows if r["STATUS"] == "UNKNOWN_COVERAGE"} == django_now
    assert all(r["STATUS"] == "UNKNOWN_COVERAGE" for r in rows)


def _login_page():
    import importlib
    import os

    from needle import app

    app = importlib.reload(app)  # undo module-level fakes that tests/test_app_ui.py installs (app.do_run)
    os.environ.pop("NEEDLE_DEMO_SWITCHER", None)
    app.main()


@pytest.mark.parametrize("user,pw_key,expect", [
    ("NDL_JUNIOR", "NDL_JUNIOR_PASSWORD", "ok"),
    ("NDL_JUNIOR", None, "Sign-in failed"),                     # wrong password
    ("NDL_JUNIOR;HOSTNAME=evil", None, "Sign-in failed"),       # connection-string injection attempt
])
def test_sign_in_binds_to_the_typed_identity(user, pw_key, expect):
    from streamlit.testing.v1 import AppTest

    pw = sbom._env().get(pw_key) if pw_key else "definitely-wrong-password"
    if pw_key and not pw:
        pytest.skip(f"{pw_key} not in needle/.env")
    import ibm_db

    if expect == "ok":  # a successful sign-in runs a real triage, which embeds the query with Ollama
        from conftest import skip_unless_ollama
        skip_unless_ollama()
    ibm_db.close(_connect("NDL_JUNIOR"))  # skip early when Db2 is unreachable
    at = AppTest.from_function(_login_page, default_timeout=120).run()
    at.sidebar.text_input[0].input(user)
    at.sidebar.text_input[1].input(pw)
    [b for b in at.sidebar.button if b.label == "Run triage"][0].click().run()
    assert not at.exception
    res = at.session_state["res"]
    assert all(pw not in str(v) for v in res.values())
    if expect == "ok":
        assert "fatal" not in res, res.get("fatal")
        assert res["user"] == "NDL_JUNIOR" and res["run"].authid == "NDL_JUNIOR"
        assert any("User <b>NDL_JUNIOR</b>" in m.value for m in at.markdown)
    else:
        assert any(expect in e.value for e in at.error), [e.value for e in at.error]
