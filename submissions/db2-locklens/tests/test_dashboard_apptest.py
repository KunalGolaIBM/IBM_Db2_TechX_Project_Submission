"""Headless dashboard tests using Streamlit's own AppTest harness (needs `streamlit` installed).

No Db2 is required: one test uses an invalid port to force the configuration screen, the other
points at a closed local port to force the "cannot reach Db2" screen. Both must render without
raising an exception.
"""

import os

import pytest

pytest.importorskip("streamlit")
try:
    from streamlit.testing.v1 import AppTest
except ImportError:                                           # very old Streamlit
    pytest.skip("streamlit.testing.v1 is not available", allow_module_level=True)

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "app.py")


def _run_app(env):
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        at = AppTest.from_file(APP, default_timeout=90)
        at.run()
        return at
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _texts(elements):
    return [str(getattr(e, "value", e)) for e in elements]


def test_invalid_configuration_shows_setup_guidance_without_crashing():
    at = _run_app({"DB2_PASSWORD": "x", "DB2_PORT": "not-a-number"})
    assert not at.exception
    assert any("not configured" in t for t in _texts(at.error))


def test_unreachable_db2_shows_a_clear_error_and_hint_without_crashing():
    at = _run_app({"DB2_PASSWORD": "x", "DB2_HOST": "127.0.0.1", "DB2_PORT": "1",
                   "LOCKLENS_CONNECT_TIMEOUT": "2", "LOCKLENS_AUTO_REFRESH": "false",
                   "LOCKLENS_AUTO_RECORD": "false"})
    assert not at.exception
    assert any("Cannot read from Db2" in t for t in _texts(at.error))
