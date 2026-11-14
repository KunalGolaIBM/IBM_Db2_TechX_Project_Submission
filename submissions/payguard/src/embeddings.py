"""Compatibility import; implementation lives in adapters.embeddings."""
import sys
from adapters.embeddings import LocalHashEmbedder as LocalHashEmbedder, GeminiEmbedder as GeminiEmbedder, get_embedder as get_embedder, to_db2_vector as to_db2_vector
from adapters import embeddings as _implementation
sys.modules[__name__] = _implementation
