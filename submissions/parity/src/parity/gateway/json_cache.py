"""File backed gateway cache.

The Db2 cache is the system of record in the bridge
environment. On a machine without a working ibm_db
driver, this file cache stores recorded model calls so
a run can replay offline later.
"""

from __future__ import annotations

import json
from pathlib import Path

from parity.gateway.types import GatewayResponse


class JsonGatewayCache:
    """One JSON file holds every recorded model call."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, tuple[str, GatewayResponse]] = {}
        if path.exists():
            self._load()

    def _load(self) -> None:
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        for key, entry in payload.items():
            response = GatewayResponse(
                text=entry["response"],
                provider=entry["provider"],
                model=entry["model"],
                tokens_in=entry["tokens_in"],
                tokens_out=entry["tokens_out"],
            )
            self._data[key] = (entry["agent"], response)

    def _flush(self) -> None:
        payload = {}
        for key, (agent, response) in self._data.items():
            payload[key] = {
                "agent": agent,
                "provider": response.provider,
                "model": response.model,
                "response": response.text,
                "tokens_in": response.tokens_in,
                "tokens_out": response.tokens_out,
            }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

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
        self._flush()
