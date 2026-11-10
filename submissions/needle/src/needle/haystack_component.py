"""Haystack component for permission-aware NEEDLE triage."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from haystack import Document, component

from needle import triage as triage_module

MODES = {"HYBRID", "KW", "VEC"}


def _validate_mode(mode: str) -> str:
    normalized = str(mode).upper()
    if normalized not in MODES:
        raise ValueError("mode must be one of HYBRID, KW, VEC")
    return normalized


def _validate_top_k(top_k: int) -> int:
    if isinstance(top_k, bool):
        raise ValueError("top_k must be an integer from 1 through 100")
    try:
        normalized = int(top_k)
    except (TypeError, ValueError) as exc:
        raise ValueError("top_k must be an integer from 1 through 100") from exc
    if normalized != top_k or not 1 <= normalized <= 100:
        raise ValueError("top_k must be an integer from 1 through 100")
    return normalized


def _hit_value(hit: Any, name: str) -> Any:
    if isinstance(hit, dict):
        return hit.get(name)
    return getattr(hit, name, None)


def _page_content(hit: Any) -> str:
    parts = [_hit_value(hit, "summary"), _hit_value(hit, "details")]
    content = "\n\n".join(str(part).strip() for part in parts if part)
    return content or str(_hit_value(hit, "adv_id"))


@component
class NeedleTriageComponent:
    """Run ``needle.triage`` with a new caller-owned Db2 connection per request.

    The connection factory must open the connection with the caller's Db2
    credentials. Db2 RCAC then applies to that caller. The factory is excluded
    from serialization because it can contain credentials or runtime state.
    """

    def __init__(
        self,
        connection_factory: Callable[[], Any],
        top_k: int = 10,
        mode: str = "HYBRID",
    ) -> None:
        self.connection_factory = connection_factory
        self.top_k = _validate_top_k(top_k)
        self.mode = _validate_mode(mode)

    @component.output_types(documents=list[Document])
    def run(
        self,
        query: str,
        top_k: int | None = None,
        mode: str | None = None,
    ) -> dict[str, list[Document]]:
        selected_top_k = self.top_k if top_k is None else _validate_top_k(top_k)
        selected_mode = self.mode if mode is None else _validate_mode(mode)

        connection = self.connection_factory()
        try:
            result = triage_module.triage(
                query,
                k=selected_top_k,
                mode=selected_mode,
                conn=connection,
            )
            documents = []
            for hit in result.hits:
                documents.append(
                    Document(
                        content=_page_content(hit),
                        meta={
                            "adv_id": _hit_value(hit, "adv_id"),
                            "rrf": _hit_value(hit, "rrf"),
                            "kw_rank": _hit_value(hit, "kw_rank"),
                            "vec_rank": _hit_value(hit, "vec_rank"),
                            "vec_dist": _hit_value(hit, "vec_dist"),
                        },
                    )
                )
            return {"documents": documents}
        finally:
            connection.close()
