"""Related-incident search inside IBM Db2 using a native VECTOR column and VECTOR_DISTANCE.

(Safety-protocol retrieval uses IBM's Haystack integration instead: see ai/haystack/rag_pipeline.py.)

Table ``incident_embeddings`` (raw DDL, because VECTOR is a Db2-specific type) holds one embedding
per incident, upserted with MERGE, so responders can find related reports, for example several
residents reporting the same broken streetlight.

Embeddings come from IBM Granite (granite-embedding:30m) served locally by Ollama, so no
resident text ever leaves the deployment. Active only in DATABASE_MODE=db2.
"""
import logging
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.app.core.config import settings

logger = logging.getLogger("neighbourhood_safety.db2_vectors")

DDL = {
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

UPSERT_INCIDENT = """
    MERGE INTO incident_embeddings t
    USING (VALUES (CAST(:incident_id AS INTEGER), VECTOR(:embedding, {dim}, FLOAT32), CAST(:model AS VARCHAR(100))))
          AS s (incident_id, embedding, embedding_model)
    ON t.incident_id = s.incident_id
    WHEN MATCHED THEN UPDATE SET embedding = s.embedding, embedding_model = s.embedding_model
    WHEN NOT MATCHED THEN INSERT (incident_id, embedding, embedding_model)
                          VALUES (s.incident_id, s.embedding, s.embedding_model)
"""

SIMILAR_INCIDENTS = """
    SELECT other.incident_id, VECTOR_DISTANCE(other.embedding, target.embedding, COSINE) AS distance
    FROM incident_embeddings target
    JOIN incident_embeddings other ON other.incident_id <> target.incident_id
    WHERE target.incident_id = :incident_id
    ORDER BY distance
    FETCH FIRST {k} ROWS ONLY
"""

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
            backfilled = self._backfill_incidents()
            self.enabled = True
            self.error = None
            logger.info("Db2 vector search enabled (%s, %d dims); embedded %d existing incident(s).",
                        settings.OLLAMA_EMBED_MODEL, settings.EMBEDDING_DIM, backfilled)
        except Exception as exc:  # pragma: no cover - depends on environment
            self.enabled = False
            self.error = str(exc)[:300]
            logger.warning("Db2 vector search unavailable, falling back to BM25 only: %s", exc)

    def _load_model(self):
        """Connect to the local Ollama server and check that the Granite embedding model answers."""
        with self._lock:
            if self._model is None:
                import ollama
                client = ollama.Client(host=settings.OLLAMA_HOST, timeout=settings.LLM_TIMEOUT_SECONDS)
                probe = client.embed(model=settings.OLLAMA_EMBED_MODEL, input=["ping"]).embeddings[0]
                if len(probe) != settings.EMBEDDING_DIM:
                    raise RuntimeError(f"{settings.OLLAMA_EMBED_MODEL} returns {len(probe)} dims, expected {settings.EMBEDDING_DIM}")
                self._model = client
        return self._model

    def embed(self, texts: List[str]) -> List[List[float]]:
        return list(self._model.embed(model=settings.OLLAMA_EMBED_MODEL, input=texts).embeddings)

    def _ensure_tables(self) -> None:
        with self.engine.begin() as conn:
            existing = {
                row[0] for row in conn.execute(text(
                    "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = CURRENT SCHEMA "
                    "AND TABNAME = 'INCIDENT_EMBEDDINGS'"
                ))
            }
            for name, ddl in DDL.items():
                if name not in existing:
                    conn.execute(text(ddl.format(dim=settings.EMBEDDING_DIM)))
                    logger.info("Created Db2 table %s", name)

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
        vectors = self.embed([f"{r[1]}. {r[2]}" for r in rows])
        sql = text(UPSERT_INCIDENT.format(dim=settings.EMBEDDING_DIM))
        with self.engine.begin() as conn:
            for r, v in zip(rows, vectors, strict=True):
                conn.execute(sql, {"incident_id": int(r[0]), "embedding": to_vector_literal(v),
                                   "model": settings.OLLAMA_EMBED_MODEL})
        return len(rows)

    # ---- incidents -----------------------------------------------------------------------
    def index_incident(self, incident_id: int, title: str, description: str) -> bool:
        if not self.enabled:
            return False
        try:
            vector = self.embed([f"{title}. {description}"])[0]
            with self.engine.begin() as conn:
                conn.execute(text(UPSERT_INCIDENT.format(dim=settings.EMBEDDING_DIM)), {
                    "incident_id": int(incident_id), "embedding": to_vector_literal(vector),
                    "model": settings.OLLAMA_EMBED_MODEL,
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
            "model": settings.OLLAMA_EMBED_MODEL if self.enabled else None,
            "dimensions": settings.EMBEDDING_DIM if self.enabled else None,
            "reason": None if self.enabled else (self.error or "requires DATABASE_MODE=db2"),
        }


vector_store = Db2VectorStore()
