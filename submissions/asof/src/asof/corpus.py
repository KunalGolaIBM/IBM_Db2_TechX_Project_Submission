"""The fictional Aurelia Air policy corpus, loaded and validated before it is seeded into Db2."""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schemas import Area

CORPUS_PATH = Path(__file__).with_name("data") / "policy_corpus.json"
OPEN_END = date(9999, 12, 31)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PolicyDocument(_Strict):
    doc_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,31}$")
    title: str = Field(min_length=1, max_length=200)
    owner_team: str = Field(max_length=100)
    source_note: str = Field(max_length=400)


class ClauseVersion(_Strict):
    version_label: str = Field(pattern=r"^v[0-9]{1,3}$")
    bus_start: date
    bus_end: date
    clause_text: str = Field(min_length=1, max_length=4000)
    rule: dict[str, Any]

    @model_validator(mode="after")
    def _period(self) -> ClauseVersion:
        if self.bus_end <= self.bus_start:
            raise ValueError(f"{self.version_label}: bus_end must be after bus_start")
        return self


class Clause(_Strict):
    clause_id: str = Field(pattern=r"^[A-Z]{3}-[0-9]{3}$")
    doc_id: str
    area: Area
    title: str = Field(min_length=1, max_length=200)
    versions: list[ClauseVersion] = Field(min_length=1)

    @model_validator(mode="after")
    def _no_overlap(self) -> Clause:
        ordered = sorted(self.versions, key=lambda v: v.bus_start)
        for prev, nxt in zip(ordered, ordered[1:], strict=False):
            if nxt.bus_start < prev.bus_end:
                raise ValueError(f"{self.clause_id}: versions {prev.version_label} and {nxt.version_label} overlap")
        if len({v.version_label for v in self.versions}) != len(self.versions):
            raise ValueError(f"{self.clause_id}: duplicate version labels")
        return self


class Corpus(_Strict):
    notice: str
    documents: list[PolicyDocument] = Field(min_length=1)
    clauses: list[Clause] = Field(min_length=1)

    @model_validator(mode="after")
    def _references(self) -> Corpus:
        doc_ids = {d.doc_id for d in self.documents}
        seen: set[str] = set()
        for c in self.clauses:
            if c.doc_id not in doc_ids:
                raise ValueError(f"{c.clause_id}: unknown doc_id {c.doc_id}")
            if c.clause_id in seen:
                raise ValueError(f"duplicate clause_id {c.clause_id}")
            seen.add(c.clause_id)
        return self

    def version_in_force(self, clause_id: str, on: date) -> ClauseVersion | None:
        """Pure-Python reference for the Db2 as-of query, used by tests and the eval set."""
        clause = next((c for c in self.clauses if c.clause_id == clause_id), None)
        if clause is None:
            return None
        return next((v for v in clause.versions if v.bus_start <= on < v.bus_end), None)


@lru_cache(maxsize=1)
def load_corpus(path: Path = CORPUS_PATH) -> Corpus:
    return Corpus.model_validate(json.loads(path.read_text(encoding="utf-8")))
