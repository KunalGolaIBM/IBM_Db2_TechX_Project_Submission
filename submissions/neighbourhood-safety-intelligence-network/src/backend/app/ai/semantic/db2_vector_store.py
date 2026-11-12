"""Related-incident search on IBM Db2 with IBM's LangChain integration (`langchain-db2`).

Every incident is embedded with IBM Granite (granite-embedding:278m, served by Ollama through
`langchain-ollama`) and stored by `langchain_db2.DB2VS` in the Db2 table INCIDENT_EMBEDDINGS
(VECTOR column + JSON metadata). Responders get related reports, for example several residents
reporting the same broken streetlight, ranked by Db2 VECTOR_DISTANCE (cosine).

Resident text never leaves the machine: both Db2 and Ollama run locally.
"""
import logging
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.app.core.config import settings

logger = logging.getLogger("neighbourhood_safety.db2_vectors")

TABLE = "INCIDENT_EMBEDDINGS"
# Calibrated with granite-embedding:278m: two reports of the same event sit well below this cosine
# distance; different kinds of incidents sit above it.
SIMILAR_INCIDENT_MAX_DISTANCE = 0.20


@dataclass
class VectorHit:
    key: str
    distance: float


def _doc_id(incident_id: int) -> str:
    return f"inc-{int(incident_id):012d}"  # fits DB2VS's CHAR(16) primary key


class Db2VectorStore:
    def __init__(self) -> None:
        self.engine: Optional[Engine] = None
        self.store = None
        self._lock = threading.Lock()
        self.enabled = False
        self.error: Optional[str] = None

    def initialise(self, engine: Engine) -> None:
        """Open the DB2VS store and embed incidents that have no vector yet. Never raises: without
        Ollama the rest of the app keeps working and /health reports why."""
        if not settings.ENABLE_VECTOR_SEARCH:
            self.error = "disabled by ENABLE_VECTOR_SEARCH"
            return
        try:
            import ibm_db_dbi
            from langchain_community.vectorstores.utils import DistanceStrategy
            from langchain_db2.db2vs import DB2VS
            from langchain_ollama import OllamaEmbeddings

            from backend.app.database.db2_adapter import Db2Adapter

            embeddings = OllamaEmbeddings(model=settings.OLLAMA_EMBED_MODEL, base_url=settings.OLLAMA_HOST)
            if len(embeddings.embed_query("ping")) != settings.EMBEDDING_DIM:
                raise RuntimeError(f"{settings.OLLAMA_EMBED_MODEL} does not return {settings.EMBEDDING_DIM} dims")
            self.engine = engine
            client = ibm_db_dbi.connect(Db2Adapter().build_connection_string(), "", "")
            self.store = DB2VS(embedding_function=embeddings, table_name=TABLE, client=client,
                               distance_strategy=DistanceStrategy.COSINE)
            self.enabled = True
            self.error = None
            backfilled = self._backfill_incidents()
            logger.info("Db2 related-incident search enabled (langchain-db2, %s); embedded %d incident(s).",
                        settings.OLLAMA_EMBED_MODEL, backfilled)
        except Exception as exc:  # pragma: no cover - depends on the environment
            self.enabled = False
            self.error = str(exc)[:300]
            logger.warning("Db2 related-incident search unavailable: %s", exc)

    def _indexed_ids(self) -> set:
        with self.engine.connect() as conn:
            return {r[0].strip() for r in conn.execute(text(f"SELECT id FROM {TABLE}"))}

    def _backfill_incidents(self, batch: int = 500) -> int:
        """Embed incidents that are not in the vector table yet (seed data, older rows)."""
        with self.engine.connect() as conn:
            rows = conn.execute(text(f"SELECT id, title, description FROM incidents ORDER BY id FETCH FIRST {int(batch)} ROWS ONLY")).fetchall()
        indexed = self._indexed_ids()
        todo = [r for r in rows if _doc_id(r[0]) not in indexed]
        if todo:
            with self._lock:
                self.store.add_texts([f"{r[1]}. {r[2]}" for r in todo],
                                     metadatas=[{"incident_id": int(r[0])} for r in todo],
                                     ids=[_doc_id(r[0]) for r in todo])
        return len(todo)

    def index_incident(self, incident_id: int, title: str, description: str) -> bool:
        if not self.enabled:
            return False
        try:
            with self._lock:
                self.store.delete(ids=[_doc_id(incident_id)])
                self.store.add_texts([f"{title}. {description}"], metadatas=[{"incident_id": int(incident_id)}],
                                     ids=[_doc_id(incident_id)])
            return True
        except Exception as exc:  # embedding must never block an emergency report
            logger.warning("Could not index incident %s for similarity search: %s", incident_id, exc)
            return False

    def similar_incidents(self, incident_id: int, k: int = 5) -> List[VectorHit]:
        if not self.enabled:
            return []
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT title, description FROM incidents WHERE id = :i"), {"i": int(incident_id)}).first()
        if row is None:
            return []
        with self._lock:
            results = self.store.similarity_search_with_score(f"{row[0]}. {row[1]}", k=max(1, min(int(k), 20)) + 1)
        hits = [VectorHit(str(doc.metadata["incident_id"]), float(score)) for doc, score in results
                if int(doc.metadata.get("incident_id", -1)) != int(incident_id)]
        return [h for h in hits if h.distance <= SIMILAR_INCIDENT_MAX_DISTANCE][:k]

    def status(self) -> Dict[str, object]:
        return {
            "enabled": self.enabled,
            "library": "langchain-db2 (DB2VS)" if self.enabled else None,
            "model": settings.OLLAMA_EMBED_MODEL if self.enabled else None,
            "dimensions": settings.EMBEDDING_DIM if self.enabled else None,
            "reason": None if self.enabled else (self.error or "not initialised"),
        }


vector_store = Db2VectorStore()
