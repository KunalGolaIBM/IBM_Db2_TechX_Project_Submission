"""Composition root: production adapters and injectable application services."""
from collections import OrderedDict
from functools import lru_cache
from threading import RLock

from config import settings
from cache import CachedEmbedder, CachedRepository
from domain.ports import Repository, Embedder, PaymentProvider
from domain.scoring import RiskEngine
from adapters.embeddings import get_embedder
from adapters.paypal import PayPalClient
from services.investigation import Investigator
from services.analyst import Analyst

class Services:
    def __init__(self, repo: Repository, embedder: Embedder, paypal: PaymentProvider):
        self.repo = CachedRepository(repo, settings.entity_cache_ttl, settings.cache_size)
        self.repo.patterns.ttl = settings.pattern_cache_ttl
        self.embedder = CachedEmbedder(embedder, settings.embedding_cache_ttl, settings.cache_size)
        self.paypal = paypal
        self._lock = RLock()
        repo, embedder = self.repo, self.embedder
        self.engine = RiskEngine(repo, embedder)
        self.investigator = Investigator(repo, embedder, self.engine)
        self.analyst = Analyst(repo)
        self.results: OrderedDict[int, dict] = OrderedDict()  # recent full results for share-target redirects

    def remember(self, result: dict) -> None:
        if result["screening_id"] is None:
            return
        with self._lock:
            self.results[result["screening_id"]] = result
            while len(self.results) > 300:
                self.results.popitem(last=False)

    def result(self, screening_id):
        with self._lock:
            return self.results.get(screening_id)


@lru_cache(maxsize=1)
def get_services() -> Services:
    from adapters.db2 import Db2Repository

    return Services(Db2Repository(), get_embedder(), PayPalClient())


