"""
IBM Db2 Vector Store Integration using official LlamaIndex package:
llama-index-vector-stores-db2 (DB2LlamaVS).
Demonstrates native VECTOR column handling (vector(dim, FLOAT32)) and in-engine distance search.
"""
import logging
from typing import Optional

from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import (
    VectorStoreQuery,
    VectorStoreQueryResult,
    MetadataFilters
)
from llama_index.vector_stores.db2 import DB2LlamaVS, DistanceStrategy

from src.db import get_dbi_connection

logger = logging.getLogger("bakebox.vector_store")

class BakeboxDb2VectorStore:
    """
    Wrapper around official DB2LlamaVS vector store.
    Utilizes Db2 v12.1.2+ native vector capabilities with COSINE distance strategy.
    """
    def __init__(
        self,
        table_name: str = "BB_CHUNKS_VECTOR",
        embed_dim: int = 384,
        distance_strategy: DistanceStrategy = DistanceStrategy.COSINE
    ):
        self.table_name = table_name
        self.embed_dim = embed_dim
        self.distance_strategy = distance_strategy
        self.connection = get_dbi_connection()

        logger.info(
            f"Initializing DB2LlamaVS on table '{table_name}' "
            f"with dimension {embed_dim} and strategy {distance_strategy.name}..."
        )
        self.vs = DB2LlamaVS(
            _client=self.connection,
            table_name=self.table_name,
            distance_strategy=self.distance_strategy,
            embed_dim=self.embed_dim
        )

    def add_nodes(self, nodes: list[TextNode]):
        """Ingest TextNode objects with pre-computed vector embeddings into Db2."""
        return self.vs.add(nodes)

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: Optional[MetadataFilters] = None
    ) -> VectorStoreQueryResult:
        """
        Execute native vector similarity search inside IBM Db2.
        Returns top_k matching nodes with similarity scores.
        """
        q = VectorStoreQuery(
            query_embedding=query_embedding,
            similarity_top_k=top_k,
            filters=filters
        )
        return self.vs.query(q)

    def delete_document(self, doc_id: str):
        """Remove a document and its vector embeddings from IBM Db2."""
        return self.vs.delete(doc_id)
