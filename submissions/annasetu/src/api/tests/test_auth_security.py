import json
import hashlib
from types import SimpleNamespace

import pytest
from fastapi.exceptions import RequestValidationError

from api.app import main
from api.app.config import settings


def test_reset_rate_limiter_caps_repeated_email_requests(monkeypatch):
    monkeypatch.setattr(main, "_reset_attempts", {})
    monkeypatch.setattr(settings, "jwt_secret", "test-key-that-is-long-enough-for-reset-hashing")
    for _ in range(5):
        assert main._reset_request_allowed("127.0.0.1", "qa@example.org")
    assert not main._reset_request_allowed("127.0.0.1", "qa@example.org")


def test_local_recovery_code_digest_is_keyed(monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "qa-only-jwt-secret-with-enough-length")
    code = "004281"
    digest = main._hash_reset_token(code)
    assert len(digest) == 64
    assert digest != hashlib.sha256(code.encode("ascii")).hexdigest()
    assert digest == main._hash_reset_token(code)


def test_recovery_code_attempts_are_rate_limited_per_ip(monkeypatch):
    monkeypatch.setattr(main, "_reset_verify_attempts", {})
    for _ in range(10):
        assert main._reset_token_attempt_allowed("127.0.0.9")
    assert not main._reset_token_attempt_allowed("127.0.0.9")


def test_production_never_exposes_a_local_code(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(main, "_reset_request_allowed", lambda *_: True)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={})
    result = main.request_password_reset(
        main.PasswordResetRequest(email="synthetic-qa@example.org"), request,
    )
    assert result["recovery_mode"] == "unavailable"
    assert "no email, sms, or code was generated" in result["message"].lower()
    assert "recovery_code" not in result


def test_public_development_recovery_requires_local_admin_approval(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(main, "_reset_request_allowed", lambda *_: True)
    monkeypatch.setattr(main, "_dict", lambda *_: pytest.fail("public recovery must not query accounts"))
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={})
    result = main.request_password_reset(
        main.PasswordResetRequest(email="missing@example.org"), request,
    )
    assert result["recovery_mode"] == "local_admin_approval"
    assert "administrator to verify your identity" in result["message"].lower()
    assert "no email, sms, or external service" in result["message"].lower()
    assert "recovery_code" not in result


def test_development_recovery_rejects_unconfigured_browser_origin(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(main, "_reset_request_allowed", lambda *_: True)
    monkeypatch.setattr(main, "_dict", lambda *_: pytest.fail("database must not be queried"))
    request = SimpleNamespace(
        client=SimpleNamespace(host="127.0.0.1"),
        headers={"origin": "https://unexpected.example"},
    )
    result = main.request_password_reset(
        main.PasswordResetRequest(email="synthetic-qa@example.org"), request,
    )
    assert result["recovery_mode"] == "unavailable"
    assert "recovery_code" not in result


def test_auth_validation_responses_do_not_echo_passwords():
    secret_input = "NeverEchoThis9!"
    validation_error = RequestValidationError([{
        "loc": ("body", "password"), "msg": "Value error: invalid password.",
        "type": "value_error", "input": secret_input,
    }])
    response = main.request_validation_error_handler(None, validation_error)
    body = response.body.decode("utf-8")
    assert secret_input not in body
    assert "input" not in json.loads(body)["detail"][0]
