"""IBM watsonx.ai: as the language model (langchain-ibm, optional) and as the provider Db2 itself calls for
embeddings (CREATE EXTERNAL MODEL ... PROVIDER WATSONX). No test here needs an IBM Cloud account: the SDK is
replaced by a stand-in that records how AsOf builds it, and Db2 accepts a model without checking credentials."""

from __future__ import annotations

import sys
import types
import uuid

import pytest

from asof import db, indb, schema
from asof.config import ConfigError, Settings
from asof.llm import LLMClient, build_llm

PROJECT = "12345678-1234-1234-1234-123456789abc"
KEY = "test-watsonx-key-not-real-0001"


def wx(**kw) -> Settings:
    return Settings(_env_file=None, **({"llm_provider": "watsonx", "watsonx_api_key": KEY, "watsonx_project_id": PROJECT,
                                        "llm_fallback": "none"} | kw))


@pytest.fixture
def fake_sdk(monkeypatch):
    """Stand-ins for ibm_watsonx_ai and langchain_ibm that record their arguments."""
    seen: dict = {}

    class HttpClientConfig:
        def __init__(self, timeout):
            seen["timeout"] = timeout

    class Credentials:
        def __init__(self, url, api_key):
            seen["credentials"] = (url, api_key)

    class APIClient:
        def __init__(self, credentials, project_id, space_id, httpx_client, async_httpx_client):
            seen["client"] = {"project_id": project_id, "space_id": space_id}
            if seen.get("refuse"):
                raise RuntimeError(f"IAM said no to {credentials}")

    class ModelInference:
        def __init__(self, model_id, api_client, project_id, space_id, max_retries, params):
            seen["inference"] = {"model_id": model_id, "project_id": project_id, "max_retries": max_retries}
            seen["params"] = params

    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    class ChatWatsonx(FakeListChatModel):
        def __init__(self, watsonx_model, max_tokens, temperature):
            super().__init__(responses=["ok"])
            seen["chat"] = {"max_tokens": max_tokens, "temperature": temperature}

    ai = types.ModuleType("ibm_watsonx_ai")
    ai.APIClient, ai.Credentials = APIClient, Credentials
    fm = types.ModuleType("ibm_watsonx_ai.foundation_models")
    fm.ModelInference = ModelInference
    utils = types.ModuleType("ibm_watsonx_ai.utils")
    uu = types.ModuleType("ibm_watsonx_ai.utils.utils")
    uu.HttpClientConfig = HttpClientConfig
    lc = types.ModuleType("langchain_ibm")
    lc.ChatWatsonx = ChatWatsonx
    for name, mod in {"ibm_watsonx_ai": ai, "ibm_watsonx_ai.foundation_models": fm, "ibm_watsonx_ai.utils": utils,
                      "ibm_watsonx_ai.utils.utils": uu, "langchain_ibm": lc}.items():
        monkeypatch.setitem(sys.modules, name, mod)
    return seen


def test_watsonx_is_ready_only_with_a_key_and_a_project_or_space():
    assert not Settings(_env_file=None, llm_provider="watsonx").llm_ready
    assert not Settings(_env_file=None, llm_provider="watsonx", watsonx_api_key=KEY).llm_ready
    assert wx().llm_ready and wx(watsonx_project_id=None, watsonx_space_id=PROJECT).llm_ready
    assert wx().llm_model_name == "ibm/granite-4-h-small"


def test_empty_watsonx_values_copied_from_the_example_mean_unset():
    s = Settings(_env_file=None, llm_provider="watsonx", watsonx_api_key="", watsonx_project_id="", watsonx_space_id="")
    assert not s.llm_ready and not s.watsonx_ready


def test_the_legacy_env_name_for_the_key_is_accepted(monkeypatch):
    monkeypatch.setenv("WATSONX_APIKEY", KEY)
    assert Settings(_env_file=None).watsonx_api_key.get_secret_value() == KEY


@pytest.mark.parametrize("url", ["http://us-south.ml.cloud.ibm.com", "https://evil.example.com",
                                 "https://us-south.ml.cloud.ibm.com.evil.example"])
def test_only_https_watsonx_endpoints_are_accepted(url):
    with pytest.raises(ValueError):
        Settings(_env_file=None, watsonx_url=url)


def test_the_client_is_built_with_asofs_deadline_retries_and_output_cap(fake_sdk):
    client = build_llm(wx(llm_timeout_s=45, llm_max_retries=1, llm_max_output_tokens=900))
    assert isinstance(client, LLMClient) and client.info == "watsonx:ibm/granite-4-h-small"
    assert client.structured_method == "function_calling"
    timeout = fake_sdk["timeout"]
    assert timeout.read == 45 and timeout.connect == 10  # not the SDK's 1800 s
    assert fake_sdk["inference"] == {"model_id": "ibm/granite-4-h-small", "project_id": PROJECT, "max_retries": 1}
    assert fake_sdk["chat"]["max_tokens"] == 900 and fake_sdk["credentials"] == ("https://us-south.ml.cloud.ibm.com", KEY)
    assert fake_sdk["params"] == {"max_tokens": 900, "time_limit": 45000}  # in the model's parameters, or ignored


def test_intake_gets_its_own_output_cap_and_deadline_on_watsonx_too(fake_sdk):
    build_llm(wx(), max_output_tokens=4000, deadline_s=150)
    assert fake_sdk["chat"]["max_tokens"] == 4000 and fake_sdk["timeout"].read == 150
    assert fake_sdk["params"]["max_tokens"] == 4000


def test_a_hosted_watsonx_primary_falls_back_to_local_ollama(fake_sdk):
    client = build_llm(wx(llm_fallback="ollama"))
    assert client.primary.provider == "watsonx" and client.fallback.provider == "ollama"


def test_missing_ibm_packages_are_a_clear_setup_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "langchain_ibm", None)
    monkeypatch.setitem(sys.modules, "ibm_watsonx_ai", None)
    with pytest.raises(ConfigError, match="requirements-watsonx.txt"):
        build_llm(wx())


def test_a_refused_key_is_a_setup_error_that_does_not_repeat_the_key(fake_sdk):
    fake_sdk["refuse"] = True
    with pytest.raises(ConfigError) as err:
        build_llm(wx())
    assert "WATSONX_API_KEY" in str(err.value) and KEY not in str(err.value)


def test_a_project_or_space_is_required_before_anything_is_called(fake_sdk):
    with pytest.raises(ConfigError, match="WATSONX_PROJECT_ID"):
        build_llm(wx(watsonx_project_id=None))
    assert "client" not in fake_sdk


def test_db2s_watsonx_embedder_is_wanted_only_when_watsonx_is_configured():
    off = Settings(_env_file=None, asof_indb_provider="watsonx", openrouter_api_key="sk-or-x" * 3)
    assert not off.indb_embeddings_wanted  # an OpenRouter key alone does not configure watsonx
    assert wx(asof_indb_provider="watsonx").indb_embeddings_wanted
    assert indb.watsonx_embeddings_url(wx(watsonx_url="https://eu-de.ml.cloud.ibm.com/")) == (
        "https://eu-de.ml.cloud.ibm.com/ml/v1/text/embeddings?version=2023-10-25")


@pytest.mark.db2
def test_db2_registers_a_watsonx_embedder_and_never_stores_the_key_in_plain_text(admin_conn, settings):
    name = f"ASOF_W{uuid.uuid4().hex[:6].upper()}"
    schema.install(admin_conn, name)
    try:
        cfg = wx(asof_indb_provider="watsonx", asof_editor_user=settings.asof_editor_user)
        endpoint = indb.register(admin_conn, cfg, name)
        assert endpoint.documented and endpoint.url.endswith("?version=2023-10-25")
        rows = db.query(admin_conn, "SELECT PROVIDER, MODELID, MODELTYPE, RETURNTYPE FROM SYSCAT.EXTERNALMODELS "
                                    "WHERE MODELSCHEMA = ? AND MODELNAME = 'EMBEDDER'", (name,))
        assert [tuple(str(v).strip() for v in r) for r in rows] == [
            ("WATSONX", "sentence-transformers/all-minilm-l6-v2", "TEXT_EMBEDDING", "VECTOR(384,FLOAT32)")]
        assert db.query(admin_conn, "SELECT SETTING FROM SYSCAT.EXTERNALMODELOPTIONS WHERE MODELSCHEMA = ? "
                                    "AND OPTION = 'PROJECT_ID'", (name,))[0][0].strip() == PROJECT
        # The model's descriptor is readable by PUBLIC. The model ID is in it in plain text (the search works);
        # the key is not.
        found = "SELECT COUNT(*) FROM SYSIBM.SYSAIMODELS WHERE SCHEMA = ? AND LOCATE(CAST(? AS BLOB(1K)), MODEL) > 0"
        assert db.query(admin_conn, found, (name, b"all-minilm-l6-v2"))[0][0] == 1
        assert db.query(admin_conn, found, (name, KEY.encode()))[0][0] == 0
        meta = "SELECT COUNT(*) FROM SYSIBM.SYSAIMODELS WHERE SCHEMA = ? AND LOCATE(CAST(? AS BLOB(1K)), METADATA) > 0"
        assert db.query(admin_conn, meta, (name, KEY.encode()))[0][0] == 0
    finally:
        schema.drop(admin_conn, name)


def test_the_real_ibm_packages_take_the_arguments_asof_passes():
    """Runs where requirements-watsonx.txt is installed (CI does): catches an SDK change before a user does."""
    import inspect

    lc = pytest.importorskip("langchain_ibm")
    from ibm_watsonx_ai import APIClient, Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai.utils.utils import HttpClientConfig

    assert {"watsonx_model", "max_tokens", "temperature"} <= set(lc.ChatWatsonx.model_fields)
    assert {"credentials", "project_id", "space_id", "httpx_client", "async_httpx_client"} <= set(
        inspect.signature(APIClient.__init__).parameters)
    assert {"url", "api_key"} <= set(inspect.signature(Credentials.__init__).parameters)
    assert {"model_id", "api_client", "project_id", "space_id", "max_retries", "params"} <= set(
        inspect.signature(ModelInference.__init__).parameters)
    assert "timeout" in inspect.signature(HttpClientConfig.__init__).parameters
    assert "function_calling" in str(inspect.signature(lc.ChatWatsonx.with_structured_output))


@pytest.mark.db2
@pytest.mark.network
def test_db2_embeds_policy_text_on_watsonx_and_matches_the_local_model(admin_conn, embeddings, settings):
    """Live: Db2 itself calls watsonx.ai (PROVIDER WATSONX). Needs WATSONX_* in .env and ASOF_RUN_NETWORK_TESTS=1."""
    from datetime import date

    from asof import db as asof_db
    from asof import policy, seed
    from asof.retriever import clauses_as_of

    if not settings.watsonx_ready:
        pytest.skip("WATSONX_API_KEY and WATSONX_PROJECT_ID are not set")
    name = f"ASOF_X{uuid.uuid4().hex[:6].upper()}"
    cfg = settings.model_copy(update={"asof_indb_provider": "watsonx"})
    schema.install(admin_conn, name)
    try:
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
        indb.register(admin_conn, cfg, name)
        probe = indb.probe(admin_conn, embeddings, name)  # Db2's vector against the local one, same sentence
        assert probe.agreement >= indb.MIN_AGREEMENT
        change = policy.PolicyChange(
            clause_id="PET-001", effective_from=date(2026, 12, 1), version_label="v2",
            clause_text="Small cats and dogs may travel in the cabin if the pet and its carrier together weigh no more "
                        "than 8 kg. The pet fee is $125 each way.",
            rule={"max_pet_weight_kg": 8, "pet_fee_usd": 125}, change_note="Pet fee rises to $125 (watsonx test)")
        with asof_db.connection(settings, "editor") as editor:
            out = policy.apply_change(editor, change, None, name)  # no local model: Db2 must embed it on watsonx.ai
        assert out["embedded_in"] == "db2"
        with asof_db.connection(settings, "app") as reader:
            found = clauses_as_of(reader, embeddings.embed_query("How much is the pet fee in the cabin?"),
                                  date(2026, 12, 15), "AURELIA-CSP", 3, None, name)
        assert found[0].clause_id == "PET-001" and found[0].version_label == "v2"
    finally:
        schema.drop(admin_conn, name)
