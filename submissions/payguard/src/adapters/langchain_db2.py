"""LangChain adapters for PayGuard's real Db2 repository and Gemini investigator."""
from __future__ import annotations

from langchain_community.vectorstores.utils import DistanceStrategy
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import StructuredTool
from langchain_core.documents import Document
from langchain_db2 import DB2VS

from adapters import gemini as llm
from adapters.embeddings import to_db2_vector


class PayGuardEmbeddings(Embeddings):
    """Reuse exactly the embedder used for the existing Db2 playbooks."""

    def __init__(self, embedder):
        self.embedder = embedder

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embedder.embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embedder.embed([text], task="query")[0]


class ParameterizedDB2VS(DB2VS):
    """Keep IBM's DB2VS lifecycle, replacing its interpolated-vector query with markers."""

    def similarity_search_by_vector_with_relevance_scores(self, embedding, k=4, filter=None):
        cur = self.client.cursor()
        try:
            cur.execute(
                f"""SELECT TEXT, SYSTOOLS.BSON2JSON(METADATA),
                    VECTOR_DISTANCE(EMBEDDING, VECTOR(CAST(? AS CLOB(100000)), {len(embedding)}, FLOAT32), COSINE)
                    FROM SCAM_EXAMPLES WHERE EMBEDDING IS NOT NULL
                    ORDER BY 3 FETCH FIRST {max(1, int(k))} ROWS ONLY""",
                (to_db2_vector(embedding),),
            )
            import json

            pairs = []
            for text, metadata, distance in cur.fetchall():
                values = json.loads(metadata or "{}")
                if not filter or all(values.get(key) in allowed for key, allowed in filter.items()):
                    pairs.append((Document(page_content=text or "", metadata=values), float(distance)))
            return pairs
        finally:
            cur.close()


def example_vector_store(connection, embedder) -> DB2VS:
    return ParameterizedDB2VS(client=connection, table_name="SCAM_EXAMPLES",
                 embedding_function=PayGuardEmbeddings(embedder),
                 distance_strategy=DistanceStrategy.COSINE)


def run_investigation(prompt: str, system: str, declarations: list[dict], handlers: dict, provider=llm):
    """Validate and execute every Db2 tool through LangChain inside the agent chain.

    Keep the existing Gemini transport and function-response protocol. Tool invocations
    execute the supplied repository functions; production uses Db2Repository, not a mock.
    """
    tools = {spec["name"]: StructuredTool.from_function(
        handlers[spec["name"]], name=spec["name"], description=spec["description"])
        for spec in declarations}

    def tool_handler(tool):
        return lambda **arguments: tool.invoke(arguments)

    chain = RunnableLambda(lambda inputs: provider.run_tool_agent(
        inputs["prompt"], inputs["system"], declarations,
        {name: tool_handler(tool) for name, tool in tools.items()}))
    return chain.invoke({"prompt": prompt, "system": system})
    def get_embedding_dimension(self):
        return self.embedding_function.embedder.dim

