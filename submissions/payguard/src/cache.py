"""Bounded LRU + TTL caching; never cache verdicts, velocity, or payments."""
from __future__ import annotations

import copy
import time
from collections import OrderedDict
from threading import RLock
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class TTLCache:
    def __init__(self, maxsize: int = 512, ttl: float = 10, clock: Callable[[], float] = time.monotonic):
        self.maxsize, self.ttl, self.clock = maxsize, ttl, clock
        self._items: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._lock = RLock()
        self._generation = self.hits = self.misses = 0

    def get_or_load(self, key: Any, load: Callable[[], T]) -> T:
        with self._lock:
            item = self._items.get(key)
            if item is not None and item[0] > self.clock():
                self.hits += 1
                self._items.move_to_end(key)
                return copy.deepcopy(item[1])
            self._items.pop(key, None)
            self.misses += 1
            generation = self._generation
        value = load()  # no cache mutex held during network calls; errors are never cached
        with self._lock:
            if generation == self._generation and self.maxsize > 0 and self.ttl > 0:
                self._items[key] = (self.clock() + self.ttl, copy.deepcopy(value))
                self._items.move_to_end(key)
                while len(self._items) > self.maxsize:
                    self._items.popitem(last=False)
        return value

    def invalidate(self) -> None:
        with self._lock:
            self._generation += 1  # also prevents in-flight stale reads repopulating the cache
            self._items.clear()

    def stats(self) -> dict:
        with self._lock:
            return {"hits": self.hits, "misses": self.misses, "size": len(self._items),
                    "hit_rate": self.hits / (self.hits + self.misses) if self.hits + self.misses else 0.0}


class CachedEmbedder:
    def __init__(self, embedder, ttl: float = 60, maxsize: int = 512):
        self.inner, self.name, self.dim = embedder, embedder.name, embedder.dim
        self.cache = TTLCache(maxsize, ttl)

    def embed(self, texts: list[str], task: str = "document") -> list[list[float]]:
        if task != "query":
            return self.inner.embed(texts, task=task)
        result = []
        for text in texts:
            def load() -> list[float]:
                return self.inner.embed([text], task="query")[0]
            result.append(self.cache.get_or_load((self.name, text), load))
        return result


class CachedRepository:
    def __init__(self, repo, ttl: float = 5, maxsize: int = 512):
        self.inner = repo
        self.entities = TTLCache(maxsize, ttl)
        self.patterns = TTLCache(maxsize, ttl)

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def lookup_entities(self, entities: list[tuple[str, str]]) -> list[dict]:
        key = tuple(sorted((t, v.lower()) for t, v in entities))
        return self.entities.get_or_load(key, lambda: self.inner.lookup_entities(list(key)))

    def search_patterns(self, vec: list[float], region: str = "GLOBAL", k: int = 5) -> list[dict]:
        return self.patterns.get_or_load(("patterns", tuple(vec), region, k),
                                        lambda: self.inner.search_patterns(vec, region=region, k=k))

    def search_examples(self, vec: list[float], k: int = 3) -> list[dict]:
        # Training examples are knowledge playbooks too; live community reports
        # deliberately remain uncached so newly filed evidence is read fresh.
        return self.patterns.get_or_load(("examples", tuple(vec), k),
                                        lambda: self.inner.search_examples(vec, k=k))

    def upsert_entity(self, *args, **kwargs) -> int:
        try:
            return self.inner.upsert_entity(*args, **kwargs)
        finally:
            self.entities.invalidate()

    def add_report(self, *args, **kwargs) -> int:
        try:
            return self.inner.add_report(*args, **kwargs)
        finally:
            self.entities.invalidate()

    def file_report(self, *args, **kwargs) -> dict:
        try:
            return self.inner.file_report(*args, **kwargs)
        finally:
            self.entities.invalidate()
