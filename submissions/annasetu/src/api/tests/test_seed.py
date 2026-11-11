import pytest

from api.app import seed
from api.app.security import password_hash, password_matches


@pytest.mark.parametrize("invalid_password", ["", "short", "replace-with-example", "x" * 129])
def test_demo_seed_rejects_missing_placeholder_or_invalid_length(monkeypatch, invalid_password):
    monkeypatch.setattr(seed.settings, "demo_password", invalid_password)
    with pytest.raises(RuntimeError, match="private DEMO_PASSWORD"):
        seed._validate_demo_password()


def test_demo_account_seed_repairs_only_reserved_accounts_and_is_idempotent(monkeypatch):
    demo_password = "private-test-only-password"
    monkeypatch.setattr(seed.settings, "demo_password", demo_password)

    # Simulate one correctly seeded demo, one stale demo hash, and two missing demos.
    existing = {
        "admin@annasetu.local": {
            "user_id": "admin-id", "display_name": "AnnaSetu Admin", "role": "admin",
            "password_hash": password_hash(demo_password),
        },
        "donor@annasetu.local": {
            "user_id": "donor-id", "display_name": "Old demo name", "role": "donor",
            "password_hash": password_hash("stale-password-for-test"),
        },
        "tournamentgaming09@gmail.com": {
            "user_id": "unrelated-user-id", "display_name": "Unrelated QA user", "role": "donor",
            "password_hash": password_hash("unrelated-test-password"),
        },
    }
    unrelated_before = dict(existing["tournamentgaming09@gmail.com"])
    operations = []

    def fake_row(sql, params=(), conn=None):
        email = params[0].lower()
        return existing.get(email)

    def fake_execute(sql, params=(), conn=None):
        operations.append(sql.split()[0].upper())
        if sql.startswith("INSERT INTO USERS"):
            user_id, email, name, role, stored_hash = params
            existing[email.lower()] = {
                "user_id": user_id, "display_name": name, "role": role, "password_hash": stored_hash,
            }
        elif sql.startswith("UPDATE USERS"):
            name, role, stored_hash, user_id = params
            row = next(row for row in existing.values() if row["user_id"] == user_id)
            row.update(display_name=name, role=role, password_hash=stored_hash)
        return 1

    monkeypatch.setattr(seed.db, "row", fake_row)
    monkeypatch.setattr(seed.db, "execute", fake_execute)

    first_ids = seed._ensure_demo_accounts(object())
    assert set(first_ids) == set(seed.DEMO_USERS)
    assert operations.count("INSERT") == 2
    assert operations.count("UPDATE") == 1
    assert password_matches(demo_password, existing["donor@annasetu.local"]["password_hash"])
    assert existing["donor@annasetu.local"]["display_name"] == seed.DEMO_USERS["donor@annasetu.local"][0]

    operation_count = len(operations)
    second_ids = seed._ensure_demo_accounts(object())
    assert second_ids == first_ids
    assert len(operations) == operation_count
    assert existing["tournamentgaming09@gmail.com"] == unrelated_before
