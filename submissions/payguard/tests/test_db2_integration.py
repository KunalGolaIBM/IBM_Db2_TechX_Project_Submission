"""Opt-in tests against a real Db2 instance; never substitute an in-memory database."""
import os

import pytest
from langchain_core.tools import StructuredTool

from agent import Investigator
from db import Db2Repository
from load_scam_examples import example_id, load_examples, read_examples
from risk import RiskEngine, ScreenRequest
from test_scam_examples import evaluate_heldout

pytestmark = [pytest.mark.db2, pytest.mark.skipif(os.getenv("PAYGUARD_DB2_TEST") != "1",
                                reason="Set PAYGUARD_DB2_TEST=1 to test real Db2")]


@pytest.fixture
def live_repo(embedder):
    repo = Db2Repository()
    assert repo.ping()
    repo.init_schema(embedder.dim)
    load_examples(repo, embedder)
    try:
        yield repo
    finally:
        repo.close()


def test_live_loader_and_langchain_db2vs(live_repo, embedder):
    rows = read_examples()
    assert {example_id(row) for row in rows} <= live_repo.example_ids()
    assert load_examples(live_repo, embedder)["inserted"] == 0
    matches = live_repo.search_examples(embedder.embed([rows[0]["text"]], task="query")[0])
    assert matches[0]["label"] == rows[0]["label"]
    assert matches[0]["similarity"] == pytest.approx(1, abs=0.001)
    from adapters.langchain_db2 import ParameterizedDB2VS
    from langchain_db2 import DB2VS
    assert issubclass(ParameterizedDB2VS, DB2VS)
    assert live_repo.count_patterns() == 25


def test_live_langchain_tools(live_repo, embedder):
    engine = RiskEngine(live_repo, embedder)
    handlers = Investigator(live_repo, embedder, engine)._handlers()
    arguments = {
        "lookup_entity": {"entity_type": "email", "value": "fastdeals.ng@mail.example"},
        "search_scam_examples": {"query": read_examples()[0]["text"]},
        "search_community_reports": {"query": "friends and family payment scam"},
    }
    for name, args in arguments.items():
        tool = StructuredTool.from_function(handlers[name], name=name, description="Query live Db2")
        assert tool.invoke(args)


def test_live_heldout_pipeline(live_repo, embedder):
    evaluate_heldout(live_repo, embedder)


def test_live_example_evidence(live_repo, embedder):
    result = RiskEngine(live_repo, embedder).screen(ScreenRequest(message=read_examples()[0]["text"]), persist=False)
    assert result.verdict == "BLOCK"
    assert any(r["code"] == "EXAMPLE_MATCH" and "bank_phishing" in r["evidence"] for r in result.reasons)


def test_live_fifty_parallel_screenings(live_repo, embedder):
    from concurrent.futures import ThreadPoolExecutor
    from services.container import Services
    from test_api import FakePayPal

    services = Services(live_repo, embedder, FakePayPal())
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(lambda _: services.engine.screen(
            ScreenRequest(message="Abeg send your OTP to collect the prize")), range(50)))
    try:
        assert len({r.screening_id for r in results}) == 50
        assert all(r.verdict == "BLOCK" and not r.degraded for r in results)
        assert 1 < live_repo.pool.stats()["size"] <= live_repo.pool.max_size
        assert live_repo.pool.stats()["borrowed"] == 0
    finally:
        for result in results:
            if result.screening_id:
                live_repo.execute("DELETE FROM PG_SCREENINGS WHERE ID = ?", (result.screening_id,))


def test_live_concurrent_report_merge_is_atomic(live_repo, embedder):
    from concurrent.futures import ThreadPoolExecutor
    import uuid

    value = "test-" + uuid.uuid4().hex
    vec = embedder.embed(["Test report, collected payment without delivery"])[0]
    try:
        with ThreadPoolExecutor(max_workers=50) as executor:
            results = list(executor.map(lambda _: live_repo.file_report(
                "account", value, "integration", "other", 1, "NGN", "Test report narrative", vec), range(50)))
        rows = live_repo.lookup_entities([("account", value)])
        assert len(rows) == 1 and rows[0]["report_count"] == 50 and rows[0]["status"] == "BLOCKED"
        assert len({r["report_id"] for r in results}) == 50
        eid = results[0]["entity"]["id"] if "id" in results[0]["entity"] else live_repo.query(
            "SELECT ID FROM PG_ENTITIES WHERE ENTITY_VALUE = ?", (value,))[0]["id"]
        assert live_repo.query("SELECT COUNT(*) AS N FROM PG_REPORTS WHERE ENTITY_ID = ?", (eid,))[0]["n"] == 50
    finally:
        live_repo.execute("DELETE FROM PG_ENTITIES WHERE ENTITY_VALUE = ?", (value,))


def test_live_failed_report_rolls_back_merge(live_repo, embedder):
    import uuid
    value = "test-" + uuid.uuid4().hex
    try:
        with pytest.raises(Exception):
            live_repo.file_report("account", value, "test", "other", 0, "TOO-LONG",
                                  "Test narrative", embedder.embed(["test"])[0])
        assert live_repo.lookup_entities([("account", value)]) == []
    finally:
        live_repo.execute("DELETE FROM PG_ENTITIES WHERE ENTITY_VALUE = ?", (value,))


def test_live_platform_checkout_end_to_end(live_repo, embedder, monkeypatch):
    from fastapi.testclient import TestClient
    import api.security
    import main
    from test_api import FakePayPal

    services = main.Services(live_repo, embedder, FakePayPal())
    main.app.dependency_overrides[main.get_services] = lambda: services
    monkeypatch.setattr(api.security, "settings", api.security.settings.model_copy(update={"platform_api_key": "live-test-key"}))
    ids = []
    try:
        with TestClient(main.app, headers={"X-API-Key": "live-test-key"}) as client:
            for email, expected in [("orders@akwa-books.example", "ALLOW"), ("fastdeals.ng@mail.example", "BLOCK")]:
                response = client.post("/api/v1/checkout/verify", json={"platform": "integration", "amount": 45,
                    "seller_email": email, "chat": [{"sender": "seller", "text": "Invoice attached, pickup Saturday"}]})
                assert response.status_code == 200, response.text
                verdict = response.json()
                ids.append(verdict["screening_id"])
                assert verdict["verdict"] == expected and not verdict["degraded"]
                paid = client.post("/api/v1/paypal/orders", json={"screening_id": verdict["screening_id"], "amount": 0.01})
                assert paid.status_code == (200 if expected == "ALLOW" else 403)
            assert services.paypal.created[0]["amount"] == 45
    finally:
        main.app.dependency_overrides.clear()
        for sid in ids:
            live_repo.execute("DELETE FROM PG_SCREENINGS WHERE ID = ?", (sid,))


def test_live_migrations_seeding_and_hot_query_contracts(live_repo, embedder):
    from analyst import Analyst, QUICK_QUESTIONS
    from load_scam_examples import DATA_DIR
    from migrations import migrate

    assert migrate(live_repo, embedder.dim) == []
    assert load_examples(live_repo, embedder)["inserted"] == 0
    heldout = {r["text"].casefold() for r in read_examples(DATA_DIR / "heldout_v1.csv")}
    stored = live_repo.query("SELECT TEXT FROM SCAM_EXAMPLES")
    assert len(stored) == 90 and not heldout.intersection(r["text"].casefold() for r in stored)
    assert live_repo.stats()["knowledge_base"]["patterns"] == 25
    assert live_repo.recent_screenings(2)
    assert live_repo.get_screening(-1) is None
    for title in QUICK_QUESTIONS:
        assert "rows" in Analyst(live_repo).answer(title)
