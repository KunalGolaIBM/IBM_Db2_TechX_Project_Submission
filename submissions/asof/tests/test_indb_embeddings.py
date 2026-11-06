"""Db2 12.1.5 in-database embeddings: CREATE EXTERNAL MODEL, TO_EMBEDDING, and the safety checks."""

from __future__ import annotations

import json
import math
import uuid
from datetime import date

import pytest

from asof import db, indb, policy, schema, seed
from asof.config import Settings

# --- no database needed -------------------------------------------------------------------

@pytest.mark.parametrize("url, documented", [
    ("https://openrouter.ai/api/v1/embeddings", True),
    ("http://127.0.0.1:11434/v1/embeddings", False),
    ("http://host.docker.internal:11434/v1/embeddings", False),
])
def test_https_is_the_documented_path_and_local_http_is_tolerated(url, documented):
    assert indb.check_endpoint(url).documented is documented


@pytest.mark.parametrize("url", ["http://example.com/v1/embeddings", "ftp://x/y", "https://", "file:///etc/passwd"])
def test_remote_plain_http_and_other_schemes_are_refused(url):
    with pytest.raises(indb.InDbError):
        indb.check_endpoint(url)


@pytest.mark.parametrize("bad", ["sk-or-v1-abc'; DROP TABLE X; --", "a b", "x\\ny", "", "'", "a;b", 'a"b'])
def test_values_that_could_end_a_ddl_literal_are_refused(bad):
    with pytest.raises(ValueError):
        db.string_literal(bad)


def test_a_normal_key_url_and_model_id_pass_as_literals():
    assert db.string_literal("sk-or-v1-0123abcd") == "'sk-or-v1-0123abcd'"
    assert db.string_literal("https://openrouter.ai/api/v1/embeddings").startswith("'https://")
    assert db.string_literal("sentence-transformers/all-minilm-l6-v2")


def test_auto_mode_turns_on_only_with_a_key():
    assert Settings(_env_file=None, openrouter_api_key=None).indb_embeddings_wanted is False
    assert Settings(_env_file=None, openrouter_api_key="sk-or-v1-x").indb_embeddings_wanted is True
    assert Settings(_env_file=None, openrouter_api_key="sk-or-v1-x", asof_indb_embeddings="off").indb_embeddings_wanted is False


# --- real Db2 calling the real endpoint (opt in: ASOF_RUN_NETWORK_TESTS=1) ------------------

@pytest.fixture
def indb_world(admin_conn, embeddings, settings):
    if not settings.embedding_key:
        pytest.skip("no embedding API key in .env")
    name = f"ASOF_M{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_published_answers(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)  # the grants file covers the FAQ table too
        indb.register(admin_conn, settings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
    except Exception:
        schema.drop(admin_conn, name)  # a failed setup must not leave a schema behind
        raise
    yield name
    schema.drop(admin_conn, name)


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True)) / math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))


@pytest.mark.db2
@pytest.mark.network
def test_db2_embeds_with_the_same_model_as_the_app(admin_conn, embeddings, indb_world):
    result = indb.probe(admin_conn, embeddings, indb_world)
    assert result.agreement >= indb.MIN_AGREEMENT


@pytest.mark.db2
@pytest.mark.network
def test_apply_policy_change_embeds_the_new_version_inside_db2(settings, admin_conn, embeddings, indb_world):
    change = policy.PolicyChange(
        clause_id="PET-001", effective_from=date(2026, 12, 1), version_label="v2",
        clause_text="Small cats and dogs may travel in the cabin if the pet and its carrier together weigh no more "
                    "than 8 kg. The pet fee is $125 each way.",
        rule={"max_pet_weight_kg": 8, "pet_fee_usd": 125}, change_note="Pet fee rises to $125")
    editor = db.connect(settings, "editor")
    try:
        result = policy.apply_change(editor, change, None, indb_world)  # no local model: Db2 must embed
    finally:
        editor.close()
    assert result["embedded_in"] == "db2"
    db.use_schema(admin_conn, indb_world)
    title, text = db.query(admin_conn, "SELECT TITLE, VECTOR_SERIALIZE(EMBEDDING) FROM POLICY_CLAUSE "
                                       "WHERE CLAUSE_ID = 'PET-001' AND VERSION_LABEL = 'v2'")[0]
    local = embeddings.embed_query(f"{title}. {change.clause_text}")
    assert _cos(json.loads(text), local) >= indb.MIN_AGREEMENT


@pytest.mark.db2
@pytest.mark.network
def test_the_key_is_not_readable_from_the_catalog(admin_conn, settings, indb_world):
    key = settings.embedding_key.get_secret_value()
    rows = db.query(admin_conn, "SELECT MODELNAME, MODELID, URL FROM SYSCAT.EXTERNALMODELS WHERE MODELSCHEMA = ?",
                    (indb_world,))
    options = db.query(admin_conn, "SELECT OPTION, SETTING FROM SYSCAT.EXTERNALMODELOPTIONS WHERE MODELSCHEMA = ?",
                       (indb_world,))
    assert rows and key[-12:] not in repr(rows) + repr(options)
