from types import SimpleNamespace

import pytest
from haystack import Pipeline

from needle.haystack_component import NeedleTriageComponent


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_maps_triage_hits_to_documents(monkeypatch):
    connection = FakeConnection()
    captured = {}

    def fake_triage(query, *, k, mode, conn):
        captured.update(query=query, k=k, mode=mode, conn=conn)
        hit = SimpleNamespace(
            adv_id="GHSA-test",
            summary="Test advisory",
            details="Technical details",
            rrf=0.25,
            kw_rank=1,
            vec_rank=3,
            vec_dist=0.125,
        )
        return SimpleNamespace(hits=[hit])

    monkeypatch.setattr("needle.triage.triage", fake_triage)
    result = NeedleTriageComponent(lambda: connection, top_k=7, mode="kw").run("unsafe yaml")

    document = result["documents"][0]
    assert document.content == "Test advisory\n\nTechnical details"
    assert document.meta == {
        "adv_id": "GHSA-test",
        "rrf": 0.25,
        "kw_rank": 1,
        "vec_rank": 3,
        "vec_dist": 0.125,
    }
    assert captured == {"query": "unsafe yaml", "k": 7, "mode": "KW", "conn": connection}
    assert connection.closed


@pytest.mark.parametrize("mode", ["bad", "keyword", ""])
def test_rejects_invalid_mode(mode):
    with pytest.raises(ValueError, match="mode must be one of"):
        NeedleTriageComponent(FakeConnection, mode=mode)


@pytest.mark.parametrize("top_k", [0, 101, True, 1.5, "ten"])
def test_rejects_invalid_top_k(top_k):
    with pytest.raises(ValueError, match="top_k must be"):
        NeedleTriageComponent(FakeConnection, top_k=top_k)


def test_closes_connection_when_triage_raises(monkeypatch):
    connection = FakeConnection()

    def fail(*args, **kwargs):
        raise RuntimeError("database failure")

    monkeypatch.setattr("needle.triage.triage", fail)
    component = NeedleTriageComponent(lambda: connection)

    with pytest.raises(RuntimeError, match="database failure"):
        component.run("query")
    assert connection.closed


def test_runs_inside_haystack_pipeline(monkeypatch):
    connections = []

    def connection_factory():
        connection = FakeConnection()
        connections.append(connection)
        return connection

    def fake_triage(query, *, k, mode, conn):
        hit = SimpleNamespace(
            adv_id="PYSEC-1", rrf=0.1, kw_rank=2, vec_rank=None, vec_dist=None
        )
        return SimpleNamespace(hits=[hit])

    monkeypatch.setattr("needle.triage.triage", fake_triage)
    pipeline = Pipeline()
    pipeline.add_component("triage", NeedleTriageComponent(connection_factory))

    result = pipeline.run({"triage": {"query": "parser bug", "mode": "KW", "top_k": 1}})

    assert result["triage"]["documents"][0].content == "PYSEC-1"
    assert connections[0].closed
