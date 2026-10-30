"""Offline and mocked integration coverage for the optional Db2 AI routes."""
import asyncio
import copy
import json
import sys
import types
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import httpx
import pytest

from backend import database, db2_ai
from backend.auth import hash_password
from backend.main import app


class MemoryStatement:
    def __init__(self, sql):
        self.sql = " ".join(sql.upper().split())
        self.rows = []
        self.offset = 0


class MemoryDb2:
    """Small parameter-aware Db2 fake; it persists JSON outside SQLite."""
    def __init__(self):
        self.records = {}
        self.table_exists = False
        self.committed = False
        self.commit_count = 0
        self.rolled_back = False
        self._transaction_snapshot = None

    SQL_AUTOCOMMIT_OFF = 0

    def connect(self, _dsn, _user, _password):
        return self

    def close(self, _conn):
        return True

    def exec_immediate(self, _conn, sql):
        normalized = " ".join(sql.upper().split())
        stmt = MemoryStatement(sql)
        if normalized.startswith("SELECT 1 FROM SYSCAT.TABLES"):
            stmt.rows = [{"1": 1}] if self.table_exists else []
        elif normalized.startswith("CREATE TABLE"):
            self.table_exists = True
        elif normalized == "VALUES 1":
            stmt.rows = [{"1": 1}]
        else:
            raise AssertionError(f"Unexpected Db2 statement: {normalized}")
        return stmt

    def prepare(self, _conn, sql):
        return MemoryStatement(sql)

    def execute(self, stmt, params=()):
        sql = stmt.sql
        if sql.startswith("DELETE FROM SURPLUSSYNC_AI_RECORDS WHERE RECORD_KEY LIKE"):
            prefix = params[0].removesuffix("%")
            for key in list(self.records):
                if key[1].startswith(prefix):
                    del self.records[key]
        elif sql.startswith("SELECT 1 FROM SURPLUSSYNC_AI_RECORDS WHERE RECORD_TYPE"):
            record_type, record_key = params
            stmt.rows = [{"1": 1}] if (record_type, record_key) in self.records else []
        elif sql.startswith("UPDATE SURPLUSSYNC_AI_RECORDS SET RECORD_JSON"):
            payload, record_type, record_key = params
            self.records[(record_type, record_key)] = payload
        elif sql.startswith("INSERT INTO SURPLUSSYNC_AI_RECORDS"):
            record_type, record_key, payload = params
            self.records[(record_type, record_key)] = payload
        elif sql.startswith("SELECT RECORD_TYPE, RECORD_KEY, RECORD_JSON FROM SURPLUSSYNC_AI_RECORDS"):
            prefix = params[0].removesuffix("%")
            stmt.rows = [
                {"RECORD_TYPE": record_type, "RECORD_KEY": key, "RECORD_JSON": value}
                for (record_type, key), value in sorted(self.records.items())
                if key.startswith(prefix)
            ]
        else:
            raise AssertionError(f"Unexpected prepared Db2 statement: {sql}")
        stmt.offset = 0
        return True

    @staticmethod
    def fetch_assoc(stmt):
        if stmt.offset >= len(stmt.rows):
            return None
        row = stmt.rows[stmt.offset]
        stmt.offset += 1
        return row

    def commit(self, _conn):
        self.committed = True
        self.commit_count += 1
        self._transaction_snapshot = None
        return True

    def autocommit(self, _conn, mode):
        if mode == self.SQL_AUTOCOMMIT_OFF:
            self._transaction_snapshot = copy.deepcopy(self.records)
        return True

    def rollback(self, _conn):
        self.rolled_back = True
        if self._transaction_snapshot is not None:
            self.records = self._transaction_snapshot
            self._transaction_snapshot = None
        return True


def run_api(coro):
    return asyncio.run(coro)


def _create_account(email, role="DONOR"):
    now = datetime.now().isoformat(timespec="seconds")
    with database.connection(immediate=True) as db:
        cursor = db.execute(
            "INSERT INTO user_accounts(email,password_hash,role,created_at,updated_at) VALUES(?,?,?,?,?)",
            (email, hash_password("Db2-test-password-2026!"), role, now, now),
        )
        user_id = cursor.lastrowid
        profile = {"organization_name": "Authorized Test Organization"} if role == "DONOR" else {}
        db.execute(
            "INSERT INTO user_profiles(user_id,role,profile_json,status,created_at,updated_at) VALUES(?,?,?,'approved',?,?)",
            (user_id, role, json.dumps(profile), now, now),
        )
    return user_id


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "db2-ai-test.sqlite")
    for name in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "VERCEL"):
        monkeypatch.delenv(name, raising=False)
    for name in (
        "DB2_CONNECTION_STRING", "DB2_DATABASE", "DB2_HOSTNAME", "DB2_PORT", "DB2_UID", "DB2_PWD",
        "WATSONX_API_KEY", "WATSONX_APIKEY", "WATSONX_PROJECT_ID", "WATSONX_URL", "WATSONX_MODEL_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    database.init_db()
    owner_id = _create_account("db2-owner@example.test")
    outsider_id = _create_account("db2-outsider@example.test")
    _create_account("db2-recipient@example.test", "RECIPIENT")
    return {"owner_id": owner_id, "outsider_id": outsider_id}


@asynccontextmanager
async def authenticated_client(email="db2-owner@example.test"):
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    login = await client.post("/api/auth/login", json={"email": email, "password": "Db2-test-password-2026!"})
    assert login.status_code == 200, login.text
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    try:
        yield client
    finally:
        await client.aclose()


def _listing_payload():
    safety = {
        "handling_verified": True,
        "temperature_verified": True,
        "allergens_verified": True,
        "packaging_verified": True,
        "local_requirements_verified": True,
    }
    return {
        "donor_name": "Authorized Test Organization",
        "food_type": "Prepared meals",
        "portions": 8,
        "pickup_area": "Central test area",
        "deadline": (datetime.now() + timedelta(hours=2)).isoformat(timespec="minutes"),
        "prepared_at": (datetime.now() - timedelta(minutes=15)).isoformat(timespec="minutes"),
        "safety_verified_by": "Human test reviewer",
        "safety": safety,
    }


async def _create_listing_and_plan(client):
    created = await client.post("/api/listings", json=_listing_payload())
    assert created.status_code == 201, created.text
    plan = await client.post(f"/api/listings/{created.json()['id']}/plan")
    assert plan.status_code == 201, plan.text
    return created.json()


def _install_langchain_fakes(monkeypatch, response_text="Mocked IBM Granite response"):
    class FakeRunnableLambda:
        def __init__(self, function):
            self.function = function

        def invoke(self, values):
            return self.function(values)

    class FakeChain:
        def __init__(self, model):
            self.model = model
            self.transform = None

        def __or__(self, transform):
            self.transform = transform
            return self

        def invoke(self, values):
            message = types.SimpleNamespace(content=self.model.response_text)
            return self.transform.invoke(message) if self.transform else message

    class FakePrompt:
        @classmethod
        def from_messages(cls, messages):
            cls.messages = messages
            return cls()

        def __or__(self, model):
            return FakeChain(model)

    class FakeChatWatsonx:
        def __init__(self, **_kwargs):
            type(self).received_kwargs = _kwargs
            self.response_text = response_text

    core = types.ModuleType("langchain_core")
    prompts = types.ModuleType("langchain_core.prompts")
    prompts.ChatPromptTemplate = FakePrompt
    runnables = types.ModuleType("langchain_core.runnables")
    runnables.RunnableLambda = FakeRunnableLambda
    ibm = types.ModuleType("langchain_ibm")
    ibm.ChatWatsonx = FakeChatWatsonx
    monkeypatch.setitem(sys.modules, "langchain_core", core)
    monkeypatch.setitem(sys.modules, "langchain_core.prompts", prompts)
    monkeypatch.setitem(sys.modules, "langchain_core.runnables", runnables)
    monkeypatch.setitem(sys.modules, "langchain_ibm", ibm)


def test_db2_config_is_fail_closed_and_does_not_leak_credentials(monkeypatch):
    monkeypatch.delenv("DB2_CONNECTION_STRING", raising=False)
    for key in db2_ai.DB2_REQUIRED:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="DB2_CONNECTION_STRING"):
        db2_ai._connection_string()

    monkeypatch.setenv("DB2_CONNECTION_STRING", "DATABASE=hidden;PWD=never-return-this")
    assert db2_ai._connection_string().startswith("DATABASE=hidden;")
    assert "SECURITY=SSL" in db2_ai._connection_string()
    monkeypatch.setenv("DB2_CONNECTION_STRING", "DATABASE=sample;SECURITY=CLEAR;")
    with pytest.raises(RuntimeError, match="SECURITY=SSL"):
        db2_ai._connection_string()
    monkeypatch.setenv("DB2_CONNECTION_STRING", "DATABASE=sample;SECURITY=SSL;")
    monkeypatch.setenv("DB2_SECURITY", "CLEAR")
    with pytest.raises(RuntimeError, match="DB2_SECURITY must be SSL"):
        db2_ai._connection_string()


def test_db2_connection_fields_require_ssl_and_a_valid_port(monkeypatch):
    monkeypatch.delenv("DB2_CONNECTION_STRING", raising=False)
    for key, value in {
        "DB2_DATABASE": "sample", "DB2_HOSTNAME": "db2.example.test", "DB2_PORT": "50000",
        "DB2_UID": "surplus", "DB2_PWD": "private-test-value",
    }.items():
        monkeypatch.setenv(key, value)
    assert "SECURITY=SSL" in db2_ai._connection_string()
    monkeypatch.setenv("DB2_PORT", "invalid")
    with pytest.raises(RuntimeError, match="DB2_PORT"):
        db2_ai._connection_string()
    monkeypatch.setenv("DB2_PORT", "50000")
    monkeypatch.setenv("DB2_SECURITY", "CLEAR")
    with pytest.raises(RuntimeError, match="SSL"):
        db2_ai._connection_string()


def test_status_and_analyze_report_missing_db2_config_without_fallback(isolated_database):
    async def exercise():
        async with authenticated_client() as donor:
            status = await donor.get("/api/ai/db2/status")
            assert status.status_code == 200
            assert status.json()["configured"] is False
            assert status.json()["connected"] is False
            assert status.json()["fallback"] == "none for this workflow"
            listing = await _create_listing_and_plan(donor)
            response = await donor.post("/api/ai/db2/analyze", json={"listing_id": listing["id"]})
            assert response.status_code == 503
            assert response.json()["detail"]["code"] == "db2_not_configured"
            assert response.json()["detail"]["fallback"].startswith("none;")
            no_csrf = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
            login = await no_csrf.post("/api/auth/login", json={"email": "db2-owner@example.test", "password": "Db2-test-password-2026!"})
            assert login.status_code == 200
            blocked = await no_csrf.post("/api/ai/db2/analyze", json={"listing_id": listing["id"]})
            assert blocked.status_code == 403
            await no_csrf.aclose()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as public:
            assert (await public.get("/api/ai/db2/status")).status_code == 401
            denied = await public.post("/api/ai/db2/analyze", json={"listing_id": 1})
            assert denied.status_code == 401
    run_api(exercise())


def test_analysis_requires_listing_ownership_even_when_db2_is_unavailable(isolated_database):
    async def exercise():
        async with authenticated_client() as owner:
            listing = await _create_listing_and_plan(owner)
        async with authenticated_client("db2-outsider@example.test") as outsider:
            response = await outsider.post("/api/ai/db2/analyze", json={"listing_id": listing["id"]})
            assert response.status_code == 403
            assert response.json()["detail"]["code"] == "listing_forbidden"
        async with authenticated_client("db2-recipient@example.test") as recipient:
            status = await recipient.get("/api/ai/db2/status")
            assert status.status_code == 403
    run_api(exercise())


def test_analysis_writes_reads_and_uses_db2_evidence_with_rules_only(isolated_database, monkeypatch):
    fake_db2 = MemoryDb2()
    monkeypatch.setenv("DB2_CONNECTION_STRING", "DATABASE=test;PWD=private-value;")
    monkeypatch.setattr(db2_ai, "_connect", lambda: (fake_db2, fake_db2))
    _install_langchain_fakes(monkeypatch)

    async def exercise():
        async with authenticated_client() as donor:
            listing = await _create_listing_and_plan(donor)
            response = await donor.post(
                "/api/ai/db2/analyze",
                json={"listing_id": listing["id"], "question": "Explain the ranked recipient and deadline evidence."},
            )
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["database"] == "IBM Db2"
            assert result["db2_write_read_verified"] is True
            assert result["records_retrieved"] == result["candidates_considered"] + 1
            assert result["recommendation"]["generation_mode"] == "rules_only"
            assert result["recommendation"]["framework"] == "LangChain RunnableLambda"
            assert "simulated travel estimate" in result["recommendation"]["answer"]
            assert "recipient" in result["recommendation"]["answer"]
            assert fake_db2.committed is True
            records = list(fake_db2.records.values())
            serialized = " ".join(records)
            assert "Human test reviewer" not in serialized
            assert "donor_user_id" not in serialized
            assert "db2-owner@example.test" not in serialized
        async with authenticated_client() as donor:
            # Db2 status checks the actual mocked driver and does not require table creation.
            status = await donor.get("/api/ai/db2/status")
            assert status.status_code == 200
            assert status.json()["connected"] is True
    run_api(exercise())


def test_failed_snapshot_replacement_rolls_back_existing_db2_records(isolated_database, monkeypatch):
    fake_db2 = MemoryDb2()
    monkeypatch.setenv("DB2_CONNECTION_STRING", "DATABASE=test;SECURITY=SSL;")
    monkeypatch.setattr(db2_ai, "_connect", lambda: (fake_db2, fake_db2))
    _install_langchain_fakes(monkeypatch)
    original_upsert = db2_ai._upsert

    async def exercise():
        async with authenticated_client() as donor:
            listing = await _create_listing_and_plan(donor)
            first = await donor.post("/api/ai/db2/analyze", json={"listing_id": listing["id"]})
            assert first.status_code == 200
            saved_records = copy.deepcopy(fake_db2.records)
            saved_commit_count = fake_db2.commit_count

            calls = 0

            def fail_after_a_partial_write(ibm_db, conn, record_type, record_key, payload):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("simulated write failure")
                original_upsert(ibm_db, conn, record_type, record_key, payload)

            monkeypatch.setattr(db2_ai, "_upsert", fail_after_a_partial_write)
            failed = await donor.post("/api/ai/db2/analyze", json={"listing_id": listing["id"]})
            assert failed.status_code == 503
            assert failed.json()["detail"]["code"] == "db2_unavailable"
            assert fake_db2.records == saved_records
            assert fake_db2.commit_count == saved_commit_count
            assert fake_db2.rolled_back is True

    run_api(exercise())


def test_status_and_analyze_never_return_or_log_raw_db2_errors(isolated_database, monkeypatch, caplog):
    secret = "PWD=do-not-leak-this-value"
    monkeypatch.setenv("DB2_CONNECTION_STRING", f"DATABASE=test;{secret};")
    monkeypatch.setattr(db2_ai, "_connect", lambda: (_ for _ in ()).throw(RuntimeError(secret)))

    async def exercise():
        async with authenticated_client() as donor:
            status = await donor.get("/api/ai/db2/status")
            assert status.status_code == 200 and not status.json()["connected"]
            assert secret not in status.text
            listing = await _create_listing_and_plan(donor)
            response = await donor.post("/api/ai/db2/analyze", json={"listing_id": listing["id"]})
            assert response.status_code == 503
            assert secret not in response.text
            assert response.json()["detail"]["error_code"] == "RuntimeError"
    run_api(exercise())
    assert secret not in caplog.text


def test_mocked_watsonx_generation_and_failure_are_labelled_honestly(monkeypatch, caplog):
    records = [{"record_type": "LISTING", "record_key": "listing:1:listing", "data": {"id": 1}}]
    monkeypatch.setenv("WATSONX_APIKEY", "mock-api-key")
    monkeypatch.setenv("WATSONX_PROJECT_ID", "mock-project-id")
    _install_langchain_fakes(monkeypatch)
    generated = db2_ai._langchain_explanation("Explain listing 1.", records)
    assert generated["generation_mode"] == "langchain_watsonx"
    assert generated["framework"] == "LangChain"
    assert "not food-safety certification" in generated["answer"]
    params = sys.modules["langchain_ibm"].ChatWatsonx.received_kwargs["params"]
    assert params["max_completion_tokens"] == 500
    assert "max_new_tokens" not in params

    class FailingChatWatsonx:
        def __init__(self, **_kwargs):
            raise RuntimeError("mock secret detail must not appear in logs")

    monkeypatch.setattr(sys.modules["langchain_ibm"], "ChatWatsonx", FailingChatWatsonx)
    caplog.clear()
    fallback = db2_ai._langchain_explanation("Explain listing 1.", records)
    assert fallback["generation_mode"] == "rules_only"
    assert fallback["llm_status"] == "generation_failed:RuntimeError"
    assert "mock secret detail" not in caplog.text


def test_current_watsonx_api_key_name_is_supported(monkeypatch):
    records = [{"record_type": "LISTING", "record_key": "listing:1:listing", "data": {"id": 1}}]
    monkeypatch.delenv("WATSONX_APIKEY", raising=False)
    monkeypatch.setenv("WATSONX_API_KEY", "mock-api-key")
    monkeypatch.setenv("WATSONX_PROJECT_ID", "mock-project-id")
    _install_langchain_fakes(monkeypatch)
    generated = db2_ai._langchain_explanation("Explain listing 1.", records)
    assert generated["generation_mode"] == "langchain_watsonx"
    assert sys.modules["langchain_ibm"].ChatWatsonx.received_kwargs["apikey"] == "mock-api-key"
