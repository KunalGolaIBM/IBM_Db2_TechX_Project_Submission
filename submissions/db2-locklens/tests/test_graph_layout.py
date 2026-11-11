from helpers import resource, session, snapshot, wait

from locklens.services.graph_layout import build_graph
from locklens.services.lock_monitor import analyze_snapshot


def graph(snap):
    return build_graph(analyze_snapshot(snap), snap)


def test_empty_when_no_waits():
    assert graph(snapshot()).nodes == []


def test_simple_holder_resource_waiter_graph():
    g = graph(snapshot(waits=[wait(9, 7, seconds=12)], sessions=[session(7), session(9)], resources=[resource()]))
    ids = {n.node_id for n in g.nodes}
    assert {"app:7", "app:9"} <= ids and len([n for n in g.nodes if n.kind == "resource"]) == 1
    assert [e.kind for e in g.edges] == ["holds", "waits"]
    x = {n.node_id: n.x for n in g.nodes}
    res = next(n for n in g.nodes if n.kind == "resource")
    assert x["app:7"] < res.x < x["app:9"]                 # reads left to right


def test_shared_holder_edge_is_drawn_once_for_many_waiters():
    g = graph(snapshot(waits=[wait(9, 7), wait(10, 7)]))
    assert len([e for e in g.edges if e.kind == "holds"]) == 1
    assert len([e for e in g.edges if e.kind == "waits"]) == 2


def test_unknown_holder_is_explicit_and_uncertain_not_invented():
    g = graph(snapshot(waits=[wait(9, None)]))
    assert any(n.kind == "unknown" and n.label == "Holder unknown" for n in g.nodes)
    assert not any(n.node_id.startswith("app:") and n.node_id != "app:9" for n in g.nodes)
    assert any(e.kind == "uncertain" for e in g.edges)


def test_chain_places_apps_in_increasing_columns():
    g = graph(snapshot(waits=[wait(2, 1, lock="L1"), wait(3, 2, lock="L2")]))
    x = {n.node_id: n.x for n in g.nodes if n.kind == "app"}
    assert x["app:1"] < x["app:2"] < x["app:3"]


def test_cycle_edges_are_emphasised():
    g = graph(snapshot(waits=[wait(1, 2, lock="L1"), wait(2, 1, lock="L2")]))
    assert any(e.emphasis == "cycle" for e in g.edges)


def test_long_waits_are_emphasised():
    g = graph(snapshot(waits=[wait(9, 7, seconds=50)]))
    assert next(e for e in g.edges if e.kind == "waits").emphasis == "long"
