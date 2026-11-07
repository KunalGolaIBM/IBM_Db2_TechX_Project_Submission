"""Builds the real service objects (Db2, embeddings, LLM, KB, GitHub) from settings."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import partial

from .agents.graph import Services
from .config import Settings
from .db import Db2Repository, connect
from .embeddings import get_embeddings
from .github_client import search_issues
from .knowledge import KnowledgeBase
from .llm import BaseLLM, get_llm

log = logging.getLogger(__name__)


@dataclass
class App:
    settings: Settings
    conn: object
    repo: Db2Repository
    embeddings: object
    llm: BaseLLM
    kb: KnowledgeBase | None

    def services(self, use_github: bool = True) -> Services:
        gh = None
        if use_github and self.settings.github_search_repo:
            gh = partial(search_issues, self.settings.github_search_repo, token=self.settings.github_token)
        return Services(
            repo=self.repo, embeddings=self.embeddings, llm=self.llm, kb=self.kb, github_search=gh,
            max_rounds=self.settings.max_critic_rounds, duplicate_distance=self.settings.duplicate_distance,
            trace_sink=[],
        )


def build_app(settings: Settings, with_kb: bool = True) -> App:
    conn = connect(settings.db2_conn_str)
    repo = Db2Repository(conn, settings.db2_schema)
    embeddings = get_embeddings(settings.embedding_backend, settings.embedding_model)
    kb = None
    if with_kb:
        try:
            kb = KnowledgeBase(conn, embeddings, settings.db2_schema)
        except Exception as exc:
            log.warning("Knowledge base unavailable: %s", exc)
    return App(settings, conn, repo, embeddings, get_llm(settings), kb)
