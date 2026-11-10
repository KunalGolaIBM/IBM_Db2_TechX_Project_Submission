"""Embeddings: local sentence-transformers if available, else a deterministic hashing embedder
(zero downloads -> reproducible for judges)."""
import hashlib
import math
import os
import re
from langchain_core.embeddings import Embeddings
from config import EMBED_DIM


class HashEmbeddings(Embeddings):
    def _one(self, text):
        v = [0.0] * EMBED_DIM
        toks = re.findall(r"[a-z0-9]+", text.lower())
        feats = toks + [t[i:i + 3] for t in toks for i in range(max(1, len(t) - 2))]
        for f in feats:
            h = int(hashlib.md5(f.encode()).hexdigest(), 16)
            v[h % EMBED_DIM] += 1.0 if (h >> 100) & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def embed_documents(self, texts):
        return [self._one(t) for t in texts]

    def embed_query(self, text):
        return self._one(text)


class FastEmbedEmbeddings(Embeddings):
    """all-MiniLM-L6-v2 (384-d) via ONNX: small install, no torch."""
    def __init__(self):
        from fastembed import TextEmbedding
        self.m = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")

    def embed_documents(self, texts):
        return [list(map(float, v)) for v in self.m.embed(list(texts))]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def get_embeddings():
    mode = os.getenv("EMBEDDINGS", "auto")
    if mode in ("auto", "fastembed"):
        try:
            return FastEmbedEmbeddings(), "MiniLM-L6-v2 (fastembed)"
        except Exception as e:
            if mode == "fastembed":
                raise
            print(f"[embeddings] fastembed unavailable ({str(e)[:80]}); using hashing fallback")
    if mode == "hf":
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2"), "MiniLM-L6-v2 (sentence-transformers)"
    return HashEmbeddings(), "hashing fallback"


EMB, EMB_NAME = get_embeddings()


def embed(text):
    return EMB.embed_query(text)
