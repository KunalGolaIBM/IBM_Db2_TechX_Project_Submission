import logging
from typing import List
from langchain_core.embeddings import Embeddings
from app.config import settings

logger = logging.getLogger("finsight.embeddings")

class FinSightEmbeddingProvider(Embeddings):
    """
    Genuine 384-dimensional pretrained embedding provider matching Db2 VECTOR(384, FLOAT32).
    Model: BAAI/bge-small-en-v1.5 (MTEB top-tier sentence transformer, 384 dimensions).
    No synthetic, hash-derived, or deterministic fallback vectors are permitted.
    """
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", dimension: int = 384):
        self.model_name = model_name
        self.dimension = dimension
        self._model = None
        self._init_model()

    def _init_model(self):
        try:
            from fastembed import TextEmbedding
            # Load genuine pretrained ONNX embedding model
            self._model = TextEmbedding(model_name=self.model_name)
            logger.info("Successfully loaded genuine pretrained embedding model: %s (dim=%d)", self.model_name, self.dimension)
        except Exception as e:
            logger.critical("FATAL: Failed to initialize real embedding model %s: %s", self.model_name, e)
            self._model = None
            raise RuntimeError(f"Real embedding model '{self.model_name}' could not be initialized: {e}. Fake fallback is prohibited.")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if self._model is None:
            raise RuntimeError("Real embedding model is not initialized. Cannot generate embeddings.")
        try:
            embeddings = list(self._model.embed(texts))
            # Round to 6 decimals to fit within IBM Db2 string parameter buffer limits
            return [[round(float(x), 6) for x in e] for e in embeddings]
        except Exception as e:
            logger.error("Error during real document embedding generation: %s", e)
            raise RuntimeError(f"Failed to generate genuine embeddings for documents: {e}")

    def embed_query(self, text: str) -> List[float]:
        if self._model is None:
            raise RuntimeError("Real embedding model is not initialized. Cannot generate query embedding.")
        try:
            embeddings = list(self._model.embed([text]))
            return [round(float(x), 6) for x in embeddings[0]]
        except Exception as e:
            logger.error("Error during real query embedding generation: %s", e)
            raise RuntimeError(f"Failed to generate genuine embedding for query '{text}': {e}")

    def get_model_info(self) -> dict:
        return {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "is_real_model": True,
            "framework": "FastEmbed (ONNX Runtime)",
            "fallback_active": False
        }

_model_name = getattr(settings, "embedding_model", "BAAI/bge-small-en-v1.5")
if not _model_name or "text-embedding" in _model_name:
    _model_name = "BAAI/bge-small-en-v1.5"

embedding_provider = FinSightEmbeddingProvider(
    model_name=_model_name,
    dimension=getattr(settings, "embedding_dimension", 384)
)
