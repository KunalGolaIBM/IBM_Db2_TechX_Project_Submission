"""Tests for safe Db2 SQL identifier composition."""

import pytest

from app.sql import quote_identifier


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [
        ("PATIENT", '"PATIENT"'),
        ("customer_email", '"CUSTOMER_EMAIL"'),
    ],
)
def test_quote_identifier(identifier, expected):
    assert quote_identifier(identifier) == expected


@pytest.mark.parametrize(
    "identifier",
    ["", "1TABLE", "TABLE.NAME", 'TABLE"NAME', "TABLE; DROP TABLE USERS", "TABLE NAME"],
)
def test_quote_identifier_rejects_unsafe_names(identifier):
    with pytest.raises(ValueError, match="Invalid Db2 identifier"):
        quote_identifier(identifier)
