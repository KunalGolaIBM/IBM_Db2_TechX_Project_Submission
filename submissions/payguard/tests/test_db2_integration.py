"""Opt-in tests against a real Db2 instance; never substitute an in-memory database."""
import os

import pytest
from langchain_core.tools import StructuredTool

from agent import Investigator
from db import Db2Repository
from load_scam_examples import example_id, load_examples, read_examples
from risk import RiskEngine, ScreenRequest
from test_scam_examples import evaluate_heldout

pytestmark = pytest.mark.skipif(os.getenv("PAYGUARD_DB2_TEST") != "1",
                                reason="Set PAYGUARD_DB2_TEST=1 to test real Db2")


@pytest.fixture
def live_repo(embedder):
    repo = Db2Repository()
    assert repo.ping()
    load_examples(repo, embedder)
    try:
        yield repo
    finally:
        repo._conn.close()


def test_live_loader_and_langchain_db2vs(live_repo, embedder):
    rows = read_examples()
    assert {example_id(row) for row in rows} <= live_repo.example_ids()
    assert load_examples(live_repo, embedder)["inserted"] == 0
    matches = live_repo.search_examples(embedder.embed([rows[0]["text"]], task="query")[0])
    assert matches[0]["label"] == rows[0]["label"]
    assert matches[0]["similarity"] == pytest.approx(1, abs=0.001)
    assert live_repo._example_store.__class__.__module__.startswith("langchain_db2")
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
