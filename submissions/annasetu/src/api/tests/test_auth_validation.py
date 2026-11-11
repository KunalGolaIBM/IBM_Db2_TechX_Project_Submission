import pytest
from pydantic import ValidationError

from api.app.models import DemoLoginInput, LoginInput, PasswordResetConfirm, PasswordResetToken, SignupInput
from api.app.security import normalize_email, password_hash, password_matches, validate_password


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" user@gmail.com ", "user@gmail.com"),
        ("CONTACT@Example.ORG", "contact@example.org"),
        ("person+qa@sub.example.org", "person+qa@sub.example.org"),
    ],
)
def test_email_validation_and_normalization(raw, expected):
    assert normalize_email(raw) == expected


@pytest.mark.parametrize(
    "email",
    [
        "usergmail.com",
        "user@",
        "@gmail.com",
        "user..name@gmail.com",
        ".user@gmail.com",
        "user.@gmail.com",
        "user@example..org",
        "user@-example.org",
        "user@example-.org",
        "user@example.c",
        "user@exa_mple.org",
    ],
)
def test_malformed_emails_are_rejected(email):
    with pytest.raises(ValueError):
        normalize_email(email)
    with pytest.raises(ValidationError):
        LoginInput(email=email, password="Valid9!pass")


@pytest.mark.parametrize("password", ["Ab1!cd", "P@ssw0rd", "numb3r#", "A1!bcdef"])
def test_password_policy_accepts_minimum_complexity(password):
    assert validate_password(password) == password


@pytest.mark.parametrize("password", ["", "A1!b", "letter!", "123456!", "Letter123", "Ab1! " + "x" * 124])
def test_password_policy_rejects_short_weak_or_long_values(password):
    with pytest.raises(ValueError):
        validate_password(password)


def test_login_normalizes_email_and_applies_password_policy():
    payload = LoginInput(email="  USER@GMAIL.COM  ", password="Valid9!pass")
    assert payload.email == "user@gmail.com"
    with pytest.raises(ValidationError):
        LoginInput(email="user@example.org", password="weakpass")


def test_demo_login_accepts_only_generic_reserved_roles_and_valid_passwords():
    payload = DemoLoginInput(role="admin", password="Valid9!pass")
    assert payload.role == "admin"
    for role in ("other", "superuser", "ADMIN"):
        with pytest.raises(ValidationError):
            DemoLoginInput(role=role, password="Valid9!pass")
    with pytest.raises(ValidationError):
        DemoLoginInput(role="donor", password="weakpass")


def test_signup_requires_confirmed_password_and_restricted_role():
    base = {"email": "donor@example.org", "display_name": "Synthetic QA Donor",
            "password": "Valid9!pass", "confirm_password": "Valid9!pass", "role": "donor"}
    assert SignupInput(**base).email == "donor@example.org"
    with pytest.raises(ValidationError, match="confirmation"):
        SignupInput(**{**base, "confirm_password": "Other9!pass"})
    with pytest.raises(ValidationError):
        SignupInput(**{**base, "role": "admin"})
    with pytest.raises(ValidationError, match="Service area"):
        SignupInput(**{**base, "role": "volunteer"})
    with pytest.raises(ValidationError, match="NGO receiving details"):
        SignupInput(**{**base, "role": "ngo"})


def test_password_reset_confirmation_uses_same_policy_and_match_rule():
    good = {"token": "004281", "password": "Valid9!pass", "confirm_password": "Valid9!pass"}
    assert PasswordResetConfirm(**good).password == good["password"]
    with pytest.raises(ValidationError, match="confirmation"):
        PasswordResetConfirm(**{**good, "confirm_password": "Other9!pass"})
    with pytest.raises(ValidationError):
        PasswordResetConfirm(**{**good, "password": "NoNumber!", "confirm_password": "NoNumber!"})


def test_password_reset_accepts_only_six_digit_local_codes():
    assert PasswordResetToken(token="004281").token == "004281"
    for invalid in ("12345", "1234567", "abcdef", "short-token", "a" * 43):
        with pytest.raises(ValidationError):
            PasswordResetToken(token=invalid)


def test_password_hash_never_contains_plaintext_and_verifies():
    password = "Valid9!pass"
    stored = password_hash(password)
    assert password not in stored
    assert password_matches(password, stored)
    assert not password_matches("Wrong9!pass", stored)
