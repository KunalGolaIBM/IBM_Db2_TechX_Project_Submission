from datetime import datetime

from fastapi.testclient import TestClient

from time_machine.api import create_app
from time_machine.config import Settings
from time_machine.llm import offline_llm
from time_machine.memory_repo import demo_scenario
from time_machine.scope import (default_hypotheses, detect_direction, find_product, heuristic_time_spec,
                                resolve_window)

PRODUCTS = [{"product_id": 1, "name": "Aurora Laptop"}, {"product_id": 2, "name": "Pulse Headphones"}]
NOW = datetime(2026, 11, 9, 11, 0)


def test_find_product_exact_and_fuzzy():
    assert find_product("why did the Aurora Laptop drop", PRODUCTS)["product_id"] == 1
    assert find_product("pulse headphone sales", PRODUCTS)["product_id"] == 2
    assert find_product("aurra revenue", PRODUCTS)["product_id"] == 1
    assert find_product("why did sales drop", PRODUCTS) is None


def test_direction_and_hypothesis_priors():
    assert detect_direction("revenue dropped") == "down"
    assert detect_direction("revenue spiked") == "up"
    assert detect_direction("why did revenue change") == "unknown"
    assert default_hypotheses("down")[0] == "rows_deleted" and default_hypotheses("up")[0] == "duplicate_load"


def test_time_windows():
    snap = datetime(2026, 11, 9, 8, 30)
    assert heuristic_time_spec("in the last 3 hours") == {"kind": "last_hours", "hours": 3.0}
    assert resolve_window({"kind": "since_snapshot"}, NOW, snap)[:2] == (snap, NOW)
    assert resolve_window({"kind": "yesterday"}, NOW, snap)[0] == datetime(2026, 11, 8)
    assert resolve_window({"kind": "today"}, NOW, snap)[0] == datetime(2026, 11, 9)
    start, end, _ = resolve_window({"kind": "since_snapshot"}, NOW, None)
    assert (end - start).total_seconds() == 24 * 3600
    assert resolve_window({}, NOW, snap, since=datetime(2026, 11, 9, 9))[0] == datetime(2026, 11, 9, 9)


def make_client():
    repo, _ = demo_scenario("price")
    return TestClient(create_app(repo=repo, llm=offline_llm(), settings=Settings())), repo


def test_health_and_products():
    client, _ = make_client()
    h = client.get("/api/health").json()
    assert h["db"]["ok"] and h["db"]["temporal_tables"] == ["ORDER_ITEMS"] and h["llm"]["enabled"] is False
    assert len(client.get("/api/products").json()) == 2
    assert client.get("/").status_code == 200


def test_investigate_endpoint_and_report_retrieval():
    client, repo = make_client()
    r = client.post("/api/investigate", json={"question": "Why did Aurora Laptop revenue drop?"})
    assert r.status_code == 200 and r.json()["verdict"]["pattern"] == "price_change"
    run_id = r.json()["run_id"]
    assert client.get(f"/api/reports/{run_id}").json()["run_id"] == run_id
    assert len(client.get(f"/api/audit/{run_id}").json()) > 5
    assert client.get("/api/reports/does-not-exist").status_code == 404
    assert client.get("/api/audit/bad id!").status_code == 400


def test_validation_errors():
    client, _ = make_client()
    assert client.post("/api/investigate", json={"question": "x"}).status_code == 422
    assert client.post("/api/investigate", json={"question": "valid question", "hours": -1}).status_code == 422


def test_sse_stream():
    client, _ = make_client()
    with client.stream("GET", "/api/investigate/stream", params={"question": "Why did Aurora Laptop revenue drop?"}) as r:
        body = "".join(r.iter_text())
    assert r.headers["content-type"].startswith("text/event-stream")
    assert '"type": "report"' in body and body.strip().endswith('{"type": "done"}')


def test_curve_shows_the_drop():
    client, _ = make_client()
    data = client.get("/api/curve", params={"product_id": 1, "points": 12}).json()
    values = [float(p["revenue"]) for p in data["points"]]
    assert len(values) == 12 and values[0] > values[-1]


def test_demo_controls_unavailable_for_test_backend():
    client, _ = make_client()
    assert client.post("/api/demo/reset").status_code == 404
