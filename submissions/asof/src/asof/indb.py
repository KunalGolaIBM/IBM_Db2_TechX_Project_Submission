"""In-database embeddings: Db2 12.1.5 calls the embedding model itself.

Setup registers the model once with CREATE EXTERNAL MODEL, then Db2 embeds clause text with
TO_EMBEDDING(text USING EMBEDDER): when the corpus is seeded, and inside APPLY_POLICY_CHANGE
when a new clause version arrives without a vector. Claims are still embedded locally by the
app (no network round trip per claim). Both sides use all-MiniLM-L6-v2, and setup proves the
two vectors agree before it relies on the database path.

Two providers: PROVIDER OPENAI (any OpenAI-compatible endpoint; OpenRouter by default) and PROVIDER WATSONX
(IBM watsonx.ai, ASOF_INDB_PROVIDER=watsonx), where Db2 itself exchanges the IBM Cloud API key for a token.
IBM documents CREATE EXTERNAL MODEL URLs as HTTPS. The documented path here is OpenRouter's
OpenAI-compatible embeddings endpoint over HTTPS. A plain-HTTP endpoint (for example a local
Ollama serving all-minilm) also worked in our tests, but that is undocumented behaviour, so it
is accepted only for a local host and only as a development convenience.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from urllib.parse import urlparse

import ibm_db_dbi
from langchain_core.embeddings import Embeddings

from . import db
from .config import Settings
from .embeddings import DIM

MODEL_NAME = "EMBEDDER"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "host.lima.internal"}
MIN_AGREEMENT = 0.999  # cosine between Db2's vector and the local one for the same text
PROBE_TEXT = "Bereavement fares must be requested before travel begins."

SQL_MODEL_EXISTS = "SELECT COUNT(*) FROM SYSCAT.EXTERNALMODELS WHERE MODELSCHEMA = CURRENT SCHEMA AND MODELNAME = 'EMBEDDER'"
SQL_PROBE = "VALUES VECTOR_SERIALIZE(TO_EMBEDDING(CAST(? AS VARCHAR(4300)) USING EMBEDDER))"


class InDbError(RuntimeError):
    pass


@dataclass(frozen=True)
class Endpoint:
    url: str
    documented: bool  # True for HTTPS, as IBM documents; False for a local plain-HTTP endpoint


def check_endpoint(url: str) -> Endpoint:
    parsed = urlparse(url)
    if parsed.scheme == "https" and parsed.hostname:
        return Endpoint(url, True)
    if parsed.scheme == "http" and parsed.hostname in LOCAL_HOSTS:
        return Endpoint(url, False)
    raise InDbError("the embedding endpoint must be HTTPS (plain HTTP is allowed only for a local endpoint)")


def model_exists(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA) -> bool:
    db.use_schema(conn, schema)
    return db.query(conn, SQL_MODEL_EXISTS)[0][0] > 0


def register(conn: ibm_db_dbi.Connection, settings: Settings, schema: str = db.SCHEMA) -> Endpoint:
    """(Re)create SCHEMA.EMBEDDER and let the policy editor use it. Commits.

    CREATE EXTERNAL MODEL accepts its model ID, URL and key only as string literals, so they go
    through db.string_literal, which rejects anything that could end the literal. The statement
    is never logged. Db2 does not expose the key in any catalog view.
    """
    if settings.asof_indb_provider == "watsonx":
        return _register_watsonx(conn, settings, schema)
    key = settings.embedding_key
    if key is None or not key.get_secret_value():
        raise InDbError("no API key for the embedding endpoint (EMBEDDING_API_KEY or OPENROUTER_API_KEY)")
    endpoint = check_endpoint(settings.embedding_api_url)
    if model_exists(conn, schema):
        db.execute(conn, f"DROP EXTERNAL MODEL {db.ident(schema)}.{db.ident(MODEL_NAME)}")
    try:
        db.execute(conn, f"CREATE EXTERNAL MODEL {db.ident(schema)}.{db.ident(MODEL_NAME)} PROVIDER OPENAI "
                         f"ID {db.string_literal(settings.embedding_api_model)} "
                         f"URL {db.string_literal(endpoint.url)} "
                         f"TYPE TEXT_EMBEDDING RETURNING VECTOR(384, FLOAT32) "
                         f"KEY {db.string_literal(key.get_secret_value())}")
    except ValueError:
        raise InDbError("the embedding model ID, URL or key contains characters Db2 DDL cannot take safely") from None
    db.execute(conn, f"GRANT USAGE ON EXTERNAL MODEL {db.ident(schema)}.{db.ident(MODEL_NAME)} "
                     f"TO USER {db.ident(settings.asof_editor_user)}")
    conn.commit()
    return endpoint


WATSONX_EMBEDDINGS_PATH = "/ml/v1/text/embeddings?version=2023-10-25"  # watsonx.ai rejects calls without a version


def watsonx_embeddings_url(settings: Settings) -> str:
    return settings.watsonx_url.rstrip("/") + WATSONX_EMBEDDINGS_PATH


def _register_watsonx(conn: ibm_db_dbi.Connection, settings: Settings, schema: str) -> Endpoint:
    """CREATE EXTERNAL MODEL ... PROVIDER WATSONX: Db2 exchanges the IBM Cloud API key for an IAM token and calls
    watsonx.ai itself. Same model as the local one (all-MiniLM-L6-v2, 384 dimensions), so probe() can prove the
    vectors agree. Db2 checks no credentials at CREATE time; probe() is the first call."""
    if not settings.watsonx_ready:
        raise InDbError("ASOF_INDB_PROVIDER=watsonx needs WATSONX_API_KEY and WATSONX_PROJECT_ID (or WATSONX_SPACE_ID)")
    endpoint = check_endpoint(watsonx_embeddings_url(settings))
    if model_exists(conn, schema):
        db.execute(conn, f"DROP EXTERNAL MODEL {db.ident(schema)}.{db.ident(MODEL_NAME)}")
    key = settings.watsonx_api_key.get_secret_value()
    try:
        if settings.watsonx_project_id:
            db.execute(conn, f"CREATE EXTERNAL MODEL {db.ident(schema)}.{db.ident(MODEL_NAME)} PROVIDER WATSONX "
                             f"ID {db.string_literal(settings.watsonx_embedding_model)} URL {db.string_literal(endpoint.url)} "
                             f"TYPE TEXT_EMBEDDING RETURNING VECTOR(384, FLOAT32) KEY {db.string_literal(key)} "
                             f"PROJECT_ID {db.string_literal(settings.watsonx_project_id)}")
        else:
            db.execute(conn, f"CREATE EXTERNAL MODEL {db.ident(schema)}.{db.ident(MODEL_NAME)} PROVIDER WATSONX "
                             f"ID {db.string_literal(settings.watsonx_embedding_model)} URL {db.string_literal(endpoint.url)} "
                             f"TYPE TEXT_EMBEDDING RETURNING VECTOR(384, FLOAT32) KEY {db.string_literal(key)} "
                             f"SPACE_ID {db.string_literal(settings.watsonx_space_id)}")
    except ValueError:
        raise InDbError("the watsonx model ID, URL, key or project ID contains characters Db2 DDL cannot take safely") from None
    db.execute(conn, f"GRANT USAGE ON EXTERNAL MODEL {db.ident(schema)}.{db.ident(MODEL_NAME)} "
                     f"TO USER {db.ident(settings.asof_editor_user)}")
    conn.commit()
    return endpoint


@dataclass(frozen=True)
class Probe:
    agreement: float
    latency_ms: int


def probe(conn: ibm_db_dbi.Connection, embeddings: Embeddings, schema: str = db.SCHEMA) -> Probe:
    """Embed one sentence in Db2 and locally; the two must agree before Db2's vectors are trusted."""
    import json

    db.use_schema(conn, schema)
    started = time.monotonic()
    try:
        text = db.query(conn, SQL_PROBE, (PROBE_TEXT,))[0][0]
    except db.DatabaseError as exc:
        raise InDbError(f"TO_EMBEDDING failed in Db2 (SQLSTATE {exc.sqlstate}); check the endpoint and key") from None
    latency = int((time.monotonic() - started) * 1000)
    remote = json.loads(text)
    local = embeddings.embed_query(PROBE_TEXT)
    if len(remote) != DIM:
        raise InDbError(f"the endpoint returned {len(remote)} dimensions, AsOf stores {DIM}")
    agreement = sum(a * b for a, b in zip(remote, local, strict=True)) / (
        math.sqrt(sum(a * a for a in remote)) * math.sqrt(sum(b * b for b in local)))
    if agreement < MIN_AGREEMENT:
        raise InDbError(f"Db2's vector and the local one disagree (cosine {agreement:.4f}); "
                        "the endpoint must serve the same model as EMBEDDING_MODEL")
    return Probe(round(agreement, 6), latency)
