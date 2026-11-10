"""Cache stores for the gateway.

InMemoryCache is for tests and short runs. Db2Cache
stores every call in the llm_cache table so recorded
runs can replay offline later.
"""

from __future__ import annotations

from typing import Protocol

from parity.gateway.types import GatewayResponse

LLM_CACHE_DDL = """CREATE TABLE llm_cache (
    cache_key VARCHAR(64) NOT NULL PRIMARY KEY,
    agent VARCHAR(100) NOT NULL,
    provider VARCHAR(100) NOT NULL,
    model VARCHAR(200) NOT NULL,
    response VARCHAR(4000) NOT NULL,
    tokens_in INTEGER NOT NULL DEFAULT 0,
    tokens_out INTEGER NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0
)"""


class CacheStore(Protocol):
    """Read and write cached responses."""

    def get(self, key: str) -> GatewayResponse | None:
        """Return the cached response or None."""
        ...

    def put(self, key: str, agent: str, response: GatewayResponse) -> None:
        """Store one response."""
        ...


class InMemoryCache:
    """Dict backed cache. For tests and local runs."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, GatewayResponse]] = {}

    def get(self, key: str) -> GatewayResponse | None:
        """Return the cached response or None."""
        entry = self._data.get(key)
        if entry is None:
            return None
        _, response = entry
        return GatewayResponse(
            text=response.text,
            provider=response.provider,
            model=response.model,
            tokens_in=response.tokens_in,
            tokens_out=response.tokens_out,
            from_cache=True,
        )

    def put(self, key: str, agent: str, response: GatewayResponse) -> None:
        """Store one response."""
        self._data[key] = (agent, response)


class Db2Cache:
    """Db2 backed cache using the admin client."""

    def __init__(self, admin) -> None:
        self._admin = admin

    def get(self, key: str) -> GatewayResponse | None:
        """Return the cached response or None."""
        import ibm_db

        conn = self._admin._connect()
        try:
            stmt = ibm_db.prepare(
                conn,
                "SELECT provider, model, response, tokens_in, tokens_out "
                "FROM llm_cache WHERE cache_key = ?",
            )
            ibm_db.bind_param(stmt, 1, key)
            ibm_db.execute(stmt)
            row = ibm_db.fetch_tuple(stmt)
            if row is False or row is None:
                return None
            return GatewayResponse(
                text=row[2],
                provider=row[0],
                model=row[1],
                tokens_in=int(row[3]),
                tokens_out=int(row[4]),
                from_cache=True,
            )
        finally:
            ibm_db.close(conn)

    def put(self, key: str, agent: str, response: GatewayResponse) -> None:
        """Store one response in llm_cache."""
        self._admin.insert_rows(
            "llm_cache",
            ("cache_key", "agent", "provider", "model", "response", "tokens_in", "tokens_out", "latency_ms"),
            [(key, agent, response.provider, response.model, response.text, response.tokens_in, response.tokens_out, 0)],
        )
