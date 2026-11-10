"""The UI, executed headlessly through Streamlit's own test harness.

``AppTest`` runs ``src/app.py`` the same way the server does -- same script,
same widget state, same reruns -- and surfaces any exception the script raised.
That makes "the UI works" an assertion instead of a screenshot.

Marked ``db2`` because the page opens real connections on load.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "src" / "app.py")

pytestmark = pytest.mark.db2

# Loading an embedding model and proving six datasets is slower than the
# default 3s budget.
TIMEOUT = 300


def _run() -> AppTest:
    app = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    assert not app.exception, [str(e.value) for e in app.exception]
    return app


def test_the_page_loads_without_raising():
    app = _run()
    assert any("PortProof" in t.value for t in app.title)
    # The header metrics prove the page really talked to Db2 on load.
    labels = {m.label for m in app.metric}
    assert {"Db2", "runtime identity", "owner identity", "repair model"} <= labels


def test_header_shows_the_least_privilege_identity_not_the_owner():
    app = _run()
    runtime = next(m for m in app.metric if m.label == "runtime identity")
    owner = next(m for m in app.metric if m.label == "owner identity")
    assert runtime.value.strip() == "PPAPP"
    assert owner.value.strip() == "PPOWN"


def test_all_three_tabs_are_present():
    app = _run()
    headings = " ".join(h.value for h in app.subheader)
    assert "Db2 is not" in headings  # tab 1
    assert "Compiling proves nothing" in headings  # tab 2
    assert "an app layer could not" in headings  # tab 3


def test_the_ledger_tab_renders_rows_db2_returned():
    app = _run()
    frames = [df.value for df in app.dataframe]
    assert frames, "no dataframe rendered"
    ledger = frames[0]
    assert len(ledger) > 0
    # Certificates are computed by the engine, so the column must be populated.
    certs = [r for r in ledger["certificate (truncated)"] if str(r).strip()]
    assert certs, "no engine-computed certificates in the ledger"


def test_pasted_sql_that_is_not_read_only_is_refused_before_db2():
    """The guard must fire in the real widget flow, not just in a unit test."""
    app = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    assert not app.exception

    app.radio(key="prove_mode").set_value("paste my own").run()
    app.text_area(key="prove_sql").set_value("SELECT 1; DROP TABLE customers").run()

    errors = " ".join(e.value for e in app.error)
    assert "rejected before it reached Db2" in errors
    assert "more than one statement" in errors


def test_pasted_read_only_sql_is_accepted_and_proved_by_db2():
    app = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    app.radio(key="prove_mode").set_value("paste my own").run()
    app.text_area(key="prove_sql").set_value(
        "SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id"
    ).run()
    assert not app.error, [e.value for e in app.error]

    app.button(key="go_prove").click().run()
    assert not app.exception, [str(e.value) for e in app.exception]
    assert any("Db2 accepted it" in s.value for s in app.success), [
        s.value for s in app.success
    ]


def test_a_silent_failure_is_shown_as_one_and_then_repaired():
    """End to end through the UI: clean translation, Db2 rejection, repair."""
    app = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    app.selectbox(key="prove_case").set_value("mysql/group_concat").run()
    app.button(key="go_prove").click().run()
    assert not app.exception, [str(e.value) for e in app.exception]

    errors = " ".join(e.value for e in app.error)
    assert "SILENT FAILURE" in errors, errors

    successes = " ".join(s.value for s in app.success)
    assert "translator reported no problem" in successes
    assert "Repaired in" in successes and "Db2 re-verified it" in successes
