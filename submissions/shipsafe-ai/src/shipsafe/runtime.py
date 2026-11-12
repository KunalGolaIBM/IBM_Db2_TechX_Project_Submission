"""Shared construction of the Db2 repository, knowledge base and orchestrator."""

from dataclasses import dataclass
from typing import Optional

from .config import ShipSafeConfig
from .db2 import Db2Repository
from .orchestration import AssessmentOrchestrator


@dataclass
class Runtime:
    config: ShipSafeConfig
    repository: Db2Repository
    knowledge_base: Optional[object]
    orchestrator: AssessmentOrchestrator


def build_runtime(config: Optional[ShipSafeConfig] = None, with_knowledge: bool = True) -> Runtime:
    """Connect to IBM Db2, ensure the schema and policy vectors exist, and wire services."""
    config = config or ShipSafeConfig.load()
    repository = Db2Repository(config.db2)
    knowledge_base = None
    if with_knowledge:
        from .knowledge import PolicyKnowledgeBase

        knowledge_base = PolicyKnowledgeBase(repository, config.embedding_provider, config.embedding_dimension, config.llm)
        knowledge_base.ensure_ingested(config.policies_dir)
    orchestrator = AssessmentOrchestrator(config, repository, knowledge_base)
    return Runtime(config, repository, knowledge_base, orchestrator)
