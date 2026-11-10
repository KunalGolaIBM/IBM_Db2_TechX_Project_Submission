"""LangChain adapters for PayGuard's real Db2 repository and Gemini investigator."""
from __future__ import annotations

from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import StructuredTool
from langchain_db2 import DB2VS

import llm


class PayGuardEmbeddings(Embeddings):
    """Reuse exactly the embedder used for the existing Db2 playbooks."""

    def __init__(self, embedder):
        self.embedder = embedder

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embedder.embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embedder.embed([text], task="query")[0]


def example_vector_store(connection, embedder) -> DB2VS:
    return DB2VS(client=connection, table_name="SCAM_EXAMPLES",
                 embedding_function=PayGuardEmbeddings(embedder),
                 distance_strategy=DistanceStrategy.COSINE)


def run_investigation(prompt: str, system: str, declarations: list[dict], handlers: dict):
    """Validate and execute every Db2 tool through LangChain inside the agent chain.

    Keep the existing Gemini transport and function-response protocol. Tool invocations
    execute the supplied repository functions; production uses Db2Repository, not a mock.
    """
    tools = {spec["name"]: StructuredTool.from_function(
        handlers[spec["name"]], name=spec["name"], description=spec["description"])
        for spec in declarations}

    def tool_handler(tool):
        return lambda **arguments: tool.invoke(arguments)

    chain = RunnableLambda(lambda inputs: llm.run_tool_agent(
        inputs["prompt"], inputs["system"], declarations,
        {name: tool_handler(tool) for name, tool in tools.items()}))
    return chain.invoke({"prompt": prompt, "system": system})
