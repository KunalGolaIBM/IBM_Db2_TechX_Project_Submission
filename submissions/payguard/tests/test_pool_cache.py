"""Pool contention, disconnect recovery, session cleanup, and stale-cache races."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock
import time

import pytest

from cache import CachedEmbedder, CachedRepository, TTLCache
from pool import ConnectionPool, PoolTimeout
from risk import RiskEngine, ScreenRequest


class Connection:
    def __init__(self):
        self.closed = False
        self.rollbacks = 0

    def rollback(self):
        if self.closed:
            raise RuntimeError("08003 connection closed")
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_fifty_parallel_screenings_exclusively_lease_connections(repo, embedder):
    active, lock, barrier = set(), Lock(), Barrier(50)
    # Instrumented Python hashing is slower under coverage; admission timeout
    # itself has a separate deterministic short-deadline test below.
    pool = ConnectionPool(Connection, min_size=2, max_size=5, timeout=20)
    pool.warm()

    def screen(_):
        barrier.wait(timeout=5)
        with pool.connection() as connection:
            with lock:
                assert id(connection) not in active
                active.add(id(connection))
            result = RiskEngine(repo, embedder).screen(ScreenRequest(message="Abeg send your OTP"))
            time.sleep(0.002)
            with lock:
                active.remove(id(connection))
            return result

    with ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(screen, range(50)))
    assert len({result.screening_id for result in results}) == 50
    assert all(result.verdict == "BLOCK" for result in results)
    assert pool.stats()["size"] <= 5 and pool.stats()["borrowed"] == 0
    pool.close()


def test_pool_deadline_and_closed_pool():
    pool = ConnectionPool(Connection, 0, 1, timeout=0.01)
    connection = pool.acquire()
    with pytest.raises(PoolTimeout):
        pool.acquire()
    pool.close()
    pool.release(connection)
    assert connection.closed and pool.stats()["size"] == 0
    with pytest.raises(RuntimeError, match="closed"):
        pool.acquire()


def test_dead_idle_connection_is_replaced_and_session_rolled_back():
    pool = ConnectionPool(Connection, 1, 2, healthcheck=lambda conn: conn.rollback())
    old = pool.acquire()
    pool.release(old)
    old.close()
    with pool.connection() as new:
        assert new is not old and not new.closed
    assert new.rollbacks >= 2 and pool.stats()["reconnects"] == 1
    pool.close()


def test_failure_does_not_leak_capacity_or_replay_a_write():
    calls = []

    def factory():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("connect failed")
        return Connection()

    pool = ConnectionPool(factory, 0, 1)
    with pytest.raises(RuntimeError):
        pool.acquire()
    assert pool.stats()["size"] == 0
    with pytest.raises(RuntimeError, match="08006"):
        with pool.connection():
            raise RuntimeError("SQLSTATE=08006 ambiguous write")
    assert len(calls) == 2 and pool.stats()["size"] == 0


@pytest.mark.parametrize("limits", [(3, 2), (-1, 2), (0, 0)])
def test_invalid_pool_settings(limits):
    with pytest.raises(ValueError):
        ConnectionPool(Connection, *limits)


def test_cache_ttl_lru_and_mutable_values():
    now = [0.0]
    cache = TTLCache(2, 5, lambda: now[0])
    assert cache.get_or_load("a", lambda: [1]) == [1]
    value = cache.get_or_load("a", lambda: [99])
    value.append(2)
    assert cache.get_or_load("a", lambda: [99]) == [1]
    cache.get_or_load("b", lambda: [2])
    cache.get_or_load("c", lambda: [3])
    assert cache.get_or_load("a", lambda: [4]) == [4]
    now[0] = 6
    assert cache.get_or_load("a", lambda: [5]) == [5]


def test_invalidation_during_inflight_lookup_cannot_restore_stale_data():
    entered, proceed = Event(), Event()
    cache = TTLCache()

    def load():
        entered.set()
        assert proceed.wait(3)
        return "stale"

    with ThreadPoolExecutor() as executor:
        pending = executor.submit(cache.get_or_load, "entity", load)
        assert entered.wait(3)
        cache.invalidate()
        proceed.set()
        assert pending.result() == "stale"
    assert cache.get_or_load("entity", lambda: "blocked") == "blocked"


def test_report_invalidates_entity_cache_and_embeddings_remain_immutable(repo, embedder):
    cached = CachedRepository(repo)
    key = [("account", "1234567890")]
    assert cached.lookup_entities(key) == []
    for _ in range(3):
        cached.upsert_entity(*key[0])
    assert cached.lookup_entities(key)[0]["status"] == "BLOCKED"
    wrapped = CachedEmbedder(embedder)
    v = wrapped.embed(["OTP"], task="query")
    v[0][0] = 999
    assert wrapped.embed(["OTP"], task="query")[0][0] != 999
    assert wrapped.cache.stats()["hits"] == 1


def test_static_example_retrieval_is_cached_but_live_reports_are_not(repo, embedder, monkeypatch):
    calls = []
    reports = []
    monkeypatch.setattr(repo, "search_examples", lambda vec, k=3: calls.append(1) or [])
    monkeypatch.setattr(repo, "search_reports", lambda vec, k=3: reports.append(1) or [])
    cached = CachedRepository(repo)
    vec = embedder.embed(["Hello"])[0]
    for _ in range(2):
        assert cached.search_examples(vec) == []
        assert cached.search_reports(vec) == []
    assert len(calls) == 1 and len(reports) == 2
