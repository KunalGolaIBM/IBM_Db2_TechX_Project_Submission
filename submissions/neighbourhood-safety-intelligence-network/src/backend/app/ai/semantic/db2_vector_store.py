"""Semantic search inside IBM Db2 using native VECTOR columns and VECTOR_DISTANCE.

Two Db2 tables (created with raw DDL, because VECTOR is a Db2-specific type):

* ``safety_protocols``   - approved safety SOPs with a VECTOR(384, FLOAT32) embedding,
                           upserted with MERGE on every start.
* ``incident_embeddings`` - one embedding per incident, used to find related reports
                           (for example several residents reporting the same broken streetlight).

Embeddings come from a small local ONNX model (fastembed, BAAI/bge-small-en-v1.5), so no
resident text ever leaves the deployment. The store is active only in DATABASE_MODE=db2;
everywhere else the app falls back to Haystack BM25 retrieval.
"""
import logging
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.app.ai.haystack.documents import APPROVED_CIVIC_SAFETY_DOCUMENTS
from backend.app.core.config import settings

logger = logging.getLogger("neighbourhood_safety.db2_vectors")

DDL = {
    "SAFETY_PROTOCOLS": """
        CREATE TABLE safety_protocols (
            doc_id          VARCHAR(40)  NOT NULL PRIMARY KEY,
            title           VARCHAR(255) NOT NULL,
            category        VARCHAR(50)  NOT NULL,
            source          VARCHAR(255),
            body            CLOB(64K)    NOT NULL,
            embedding       VECTOR({dim}, FLOAT32) NOT NULL,
            embedding_model VARCHAR(100) NOT NULL,
            updated_at      TIMESTAMP    NOT NULL DEFAULT CURRENT TIMESTAMP
        )""",
    "INCIDENT_EMBEDDINGS": """
        CREATE TABLE incident_embeddings (
            incident_id     INTEGER      NOT NULL PRIMARY KEY,
            embedding       VECTOR({dim}, FLOAT32) NOT NULL,
            embedding_model VARCHAR(100) NOT NULL,
            created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT TIMESTAMP,
            CONSTRAINT fk_incident_embeddings_incident
                FOREIGN KEY (incident_id) REFERENCES incidents (id) ON DELETE CASCADE
        )""",
}

UPSERT_PROTOCOL = """
    MERGE INTO safety_protocols t
    USING (VALUES (CAST(:doc_id AS VARCHAR(40)), CAST(:title AS VARCHAR(255)), CAST(:category AS VARCHAR(50)),
                   CAST(:source AS VARCHAR(255)), CAST(:body AS CLOB(64K)), VECTOR(:embedding, {dim}, FLOAT32),
                   CAST(:model AS VARCHAR(100))))
          AS s (doc_id, title, category, source, body, embedding, embedding_model)
    ON t.doc_id = s.doc_id
    WHEN MATCHED THEN UPDATE SET title = s.title, category = s.category, source = s.source, body = s.body,
                                 embedding = s.embedding, embedding_model = s.embedding_model,
                                 updated_at = CURRENT TIMESTAMP
    WHEN NOT MATCHED THEN INSERT (doc_id, title, category, source, body, embedding, embedding_model)
                          VALUES (s.doc_id, s.title, s.category, s.source, s.body, s.embedding, s.embedding_model)
"""

UPSERT_INCIDENT = """
    MERGE INTO incident_embeddings t
    USING (VALUES (CAST(:incident_id AS INTEGER), VECTOR(:embedding, {dim}, FLOAT32), CAST(:model AS VARCHAR(100))))
          AS s (incident_id, embedding, embedding_model)
    ON t.incident_id = s.incident_id
    WHEN MATCHED THEN UPDATE SET embedding = s.embedding, embedding_model = s.embedding_model
    WHEN NOT MATCHED THEN INSERT (incident_id, embedding, embedding_model)
                          VALUES (s.incident_id, s.embedding, s.embedding_model)
"""

SEARCH_PROTOCOLS = """
    SELECT doc_id, VECTOR_DISTANCE(embedding, VECTOR(:query, {dim}, FLOAT32), COSINE) AS distance
    FROM safety_protocols
    ORDER BY distance
    FETCH FIRST {k} ROWS ONLY
"""

SIMILAR_INCIDENTS = """
    SELECT other.incident_id, VECTOR_DISTANCE(other.embedding, target.embedding, COSINE) AS distance
    FROM incident_embeddings target
    JOIN incident_embeddings other ON other.incident_id <> target.incident_id
    WHERE target.incident_id = :incident_id
    ORDER BY distance
    FETCH FIRST {k} ROWS ONLY
"""

# Calibrated on the protocol corpus with bge-small: relevant queries rank the right protocol first
# with a clear margin over the runner-up, while off-topic queries produce near-ties.
PROTOCOL_STRONG_MATCH = 0.42
PROTOCOL_MAX_DISTANCE = 0.50
PROTOCOL_MIN_MARGIN = 0.03
# Incidents closer than this are treated as reports of the same or a closely related event.
SIMILAR_INCIDENT_MAX_DISTANCE = 0.20


@dataclass
class VectorHit:
    key: str
    distance: float


def to_vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(f"{float(v):.6f}" for v in values) + "]"


class Db2VectorStore:
    def __init__(self) -> None:
        self.engine: Optional[Engine] = None
        self._model = None
        self._lock = threading.Lock()
        self.enabled = False
        self.error: Optional[str] = None

    # ---- lifecycle -----------------------------------------------------------------------
    def initialise(self, engine: Engine) -> None:
        """Create the vector tables if needed and (re)index the protocol corpus. Never raises:
        if embeddings are unavailable the app keeps working with BM25 retrieval."""
        if not settings.ENABLE_VECTOR_SEARCH:
            self.error = "disabled by ENABLE_VECTOR_SEARCH"
            return
        try:
            self.engine = engine
            self._load_model()
            self._ensure_tables()
            self._index_protocols()
            backfilled = self._backfill_incidents()
            self.enabled = True
            self.error = None
            logger.info("Db2 vector search enabled (%s, %d dims); embedded %d existing incident(s).",
                        settings.EMBEDDING_MODEL, settings.EMBEDDING_DIM, backfilled)
        except Exception as exc:  # pragma: no cover - depends on environment
            self.enabled = False
            self.error = str(exc)[:300]
            logger.warning("Db2 vector search unavailable, falling back to BM25 only: %s", exc)

    def _load_model(self):
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding
                kwargs = {"cache_dir": settings.EMBEDDING_CACHE_DIR} if settings.EMBEDDING_CACHE_DIR else {}
                self._model = TextEmbedding(settings.EMBEDDING_MODEL, **kwargs)
        return self._model

    def _ensure_tables(self) -> None:
        with self.engine.begin() as conn:
            existing = {
                row[0] for row in conn.execute(text(
                    "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA "
                    "AND TABNAME IN ('SAFETY_PROTOCOLS', 'INCIDENT_EMBEDDINGS')"
                ))
            }
            for name, ddl in DDL.items():
                if name not in existing:
                    conn.execute(text(ddl.format(dim=settings.EMBEDDING_DIM)))
                    logger.info("Created Db2 table %s", name)

    def _index_protocols(self) -> None:
        docs = APPROVED_CIVIC_SAFETY_DOCUMENTS
        vectors = list(self._model.embed([f"{d['title']}. {d['content']}" for d in docs]))
        sql = text(UPSERT_PROTOCOL.format(dim=settings.EMBEDDING_DIM))
        with self.engine.begin() as conn:
            for d, v in zip(docs, vectors, strict=True):
                conn.execute(sql, {
                    "doc_id": d["id"], "title": d["title"], "category": d["category"], "source": d["source"],
                    "body": d["content"], "embedding": to_vector_literal(v), "model": settings.EMBEDDING_MODEL,
                })

    def _backfill_incidents(self, batch: int = 500) -> int:
        """Embed incidents that have no vector yet (seed data, or rows created before vectors were enabled)."""
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT i.id, i.title, i.description FROM incidents i "
                "WHERE NOT EXISTS (SELECT 1 FROM incident_embeddings e WHERE e.incident_id = i.id) "
                f"ORDER BY i.id FETCH FIRST {int(batch)} ROWS ONLY"
            )).fetchall()
        if not rows:
            return 0
        vectors = list(self._model.embed([f"{r[1]}. {r[2]}" for r in rows]))
        sql = text(UPSERT_INCIDENT.format(dim=settings.EMBEDDING_DIM))
        with self.engine.begin() as conn:
            for r, v in zip(rows, vectors, strict=True):
                conn.execute(sql, {"incident_id": int(r[0]), "embedding": to_vector_literal(v),
                                   "model": settings.EMBEDDING_MODEL})
        return len(rows)

    # ---- protocols -----------------------------------------------------------------------
    def search_protocols(self, query: str, k: int = 3) -> List[VectorHit]:
        """Nearest protocols by cosine distance, gated so that off-topic queries return nothing."""
        if not self.enabled or not query.strip():
            return []
        qv = next(iter(self._model.query_embed([query])))
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(SEARCH_PROTOCOLS.format(dim=settings.EMBEDDING_DIM, k=max(2, int(k)))),
                {"query": to_vector_literal(qv)},
            ).fetchall()
        hits = [VectorHit(r[0], float(r[1])) for r in rows]
        if not hits:
            return []
        best = hits[0].distance
        margin = (hits[1].distance - best) if len(hits) > 1 else 1.0
        confident = best <= PROTOCOL_STRONG_MATCH or (best <= PROTOCOL_MAX_DISTANCE and margin >= PROTOCOL_MIN_MARGIN)
        if not confident:
            return []
        return [h for h in hits if h.distance <= best + PROTOCOL_MIN_MARGIN][:k]

    # ---- incidents -----------------------------------------------------------------------
    def index_incident(self, incident_id: int, title: str, description: str) -> bool:
        if not self.enabled:
            return False
        try:
            vector = next(iter(self._model.embed([f"{title}. {description}"])))
            with self.engine.begin() as conn:
                conn.execute(text(UPSERT_INCIDENT.format(dim=settings.EMBEDDING_DIM)), {
                    "incident_id": int(incident_id), "embedding": to_vector_literal(vector),
                    "model": settings.EMBEDDING_MODEL,
                })
            return True
        except Exception as exc:  # embedding must never block an emergency report
            logger.warning("Could not index incident %s for similarity search: %s", incident_id, exc)
            return False

    def similar_incidents(self, incident_id: int, k: int = 5) -> List[VectorHit]:
        if not self.enabled:
            return []
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(SIMILAR_INCIDENTS.format(k=max(1, min(int(k), 20)))), {"incident_id": int(incident_id)}
            ).fetchall()
        return [VectorHit(str(r[0]), float(r[1])) for r in rows if float(r[1]) <= SIMILAR_INCIDENT_MAX_DISTANCE]

    def status(self) -> Dict[str, object]:
        return {
            "enabled": self.enabled,
            "model": settings.EMBEDDING_MODEL if self.enabled else None,
            "dimensions": settings.EMBEDDING_DIM if self.enabled else None,
            "reason": None if self.enabled else (self.error or "requires DATABASE_MODE=db2"),
        }


vector_store = Db2VectorStore()
