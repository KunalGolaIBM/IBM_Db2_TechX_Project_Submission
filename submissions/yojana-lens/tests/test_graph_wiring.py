"""Wiring checks that do not need a database.

These catch the failures that would otherwise only appear at container
start-up: a graph that will not compile, a missing node, or a driver import
that explodes instead of explaining itself.
"""

from src.agent import graph as g
from src import db


def test_graph_compiles_when_langgraph_is_installed():
    app = g.build_graph()
    if not g.HAS_LANGGRAPH:
        assert app is None
        return
    assert app is not None
    nodes = set(app.get_graph().nodes)
    for expected in ["begin", "normalize", "retrieve", "record_trace", "explain", "finalize"]:
        assert expected in nodes


def test_conditional_route_asks_for_clarification_without_facts():
    assert g._route_after_normalize({"facts": {"age": 30}}) == "persist_facts"
    assert g._route_after_normalize({"facts": {}}) == "clarify"


def test_every_declared_node_exists():
    for name in g.NODES:
        assert callable(g.NODES[name])


def test_missing_driver_produces_an_actionable_error(monkeypatch):
    monkeypatch.setattr(db, "ibm_db", None)
    monkeypatch.setattr(db, "DRIVER_ERROR", "simulated missing client")
    try:
        with db.connect():
            pass
    except db.Db2Error as exc:
        message = str(exc)
        assert "docker compose up" in message
        assert "simulated missing client" in message
    else:  # pragma: no cover
        raise AssertionError("expected Db2Error")
