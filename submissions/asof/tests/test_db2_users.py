"""Db2 integration: API users live in ASOF.API_USER as token hashes; only the owner can change them."""

from __future__ import annotations

import pytest

from asof import db, users
from asof.users import UserError

pytestmark = pytest.mark.db2


def test_a_token_authenticates_its_user_and_only_its_hash_is_stored(admin_conn, app_conn, test_schema):
    token = users.add(admin_conn, "maria", {"checker", "auditor"}, test_schema)
    assert users.TOKEN_RE.match(token)
    who = users.authenticate(app_conn, token, test_schema)
    assert who.name == "maria" and who.roles == {"checker", "auditor"} and not who.can("editor")
    db.use_schema(admin_conn, test_schema)
    rows = db.query(admin_conn, "SELECT TOKEN_SHA256 FROM API_USER WHERE USER_NAME = 'maria'")
    assert rows == [(users.token_hash(token),)] and token not in str(rows)
    assert users.authenticate(app_conn, users.new_token(), test_schema) is None
    assert users.authenticate(app_conn, "' OR 1=1 --", test_schema) is None  # never reaches Db2


def test_rotating_or_disabling_takes_effect_on_the_next_request(admin_conn, app_conn, test_schema):
    old = users.add(admin_conn, "omar", {"editor"}, test_schema)
    new = users.rotate(admin_conn, "omar", test_schema)
    assert users.authenticate(app_conn, old, test_schema) is None
    assert users.authenticate(app_conn, new, test_schema).name == "omar"
    assert users.disable(admin_conn, "omar", test_schema) and not users.disable(admin_conn, "omar", test_schema)
    assert users.authenticate(app_conn, new, test_schema) is None
    listed = {u["user"]: u for u in users.list_users(admin_conn, test_schema)}
    assert listed["omar"]["roles"] == ["editor"] and listed["omar"]["disabled_at"] is not None
    with pytest.raises(UserError):
        users.rotate(admin_conn, "omar", test_schema)


def test_names_roles_and_duplicates_are_refused(admin_conn, test_schema):
    users.add(admin_conn, "lee", {"auditor"}, test_schema)
    for name, roles in (("lee", {"auditor"}), ("Bad Name", {"auditor"}), ("ok.name", set()), ("ok.name", {"admin"})):
        with pytest.raises(UserError):
            users.add(admin_conn, name, roles, test_schema)


@pytest.mark.parametrize("sql", [
    "INSERT INTO API_USER (USER_NAME, TOKEN_SHA256, CAN_EDIT) VALUES ('mallory', "
    "'0000000000000000000000000000000000000000000000000000000000000000', 1)",
    "UPDATE API_USER SET CAN_EDIT = 1",
    "DELETE FROM API_USER",
])
def test_the_runtime_user_can_read_api_users_but_never_change_them(app_conn, test_schema, sql):
    db.use_schema(app_conn, test_schema)
    with pytest.raises(db.DatabaseError) as err:
        db.execute(app_conn, sql)
    app_conn.rollback()
    assert err.value.sqlstate == "42501"
