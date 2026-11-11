"""Evidence Vault: validated uploads, parsing, grounded extraction, chunking, retrieval.

Retrieval engines (reported with every search result):
  * "db2-vector (langchain-db2 DB2VS, VECTOR_DISTANCE COSINE)" — DB_MODE=db2 on a
    Db2 build with the VECTOR type (12.1.2+). Chunks are written through
    langchain_db2.DB2VS and searched with Db2's VECTOR_DISTANCE.
  * "json-vector cosine (fallback)" — older Db2 or dev mode: vectors are stored in
    evidence_chunks.embedding_json and ranked in Python.

Every extracted claim carries document, page and section, plus the exact text
snippet it came from. Nothing is inferred that is not present in the text.
"""
from __future__ import annotations

import hashlib
import io
import logging
import math
import re
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.database import Database, IntegrityViolation

from .common import NotFound, audit, dumps, loads, new_id

log = logging.getLogger("recallguard.evidence")

ALLOWED_EXT = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv"}
DOC_TYPES = ("LAB_REPORT", "SUPPLIER_CERTIFICATE", "QC_RECORD", "CONTAMINATION_NOTICE", "OTHER")

CONTAMINANTS = [
    "Salmonella", "Listeria monocytogenes", "Listeria", "Escherichia coli O157", "E. coli O157", "E. coli",
    "Cronobacter", "Bacillus cereus", "Clostridium botulinum", "Staphylococcus aureus", "Enterobacteriaceae",
    "Aflatoxin", "Patulin", "Ochratoxin", "Lead", "Cadmium", "Mercury", "Arsenic", "Pesticide residue",
    "Glass fragments", "Metal fragments", "Undeclared peanut", "Undeclared milk", "Norovirus", "Hepatitis A",
]
RESULT_HINTS = re.compile(r"(not\s+detected|detected|positive|negative|cfu/g|mpn/g|mg/kg|µg/kg|ug/kg|ppm|ppb|exceed|within limit|above limit|below limit|presumptive|confirmed)", re.I)
SEVERITY_HINTS = re.compile(r"(pathogen|confirmed positive|exceeds?\s+(the\s+)?(legal\s+)?limit|urgent|immediate|recall|public health|critical|serotype)", re.I)
LOT_RE = re.compile(r"\b[A-Z]{3}-20\d{2}-\d{3}\b")
BATCH_RE = re.compile(r"\bPB-20\d{2}-\d{4}\b")
ISO_DATE_RE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
TEXT_DATE_RE = re.compile(r"\b\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+20\d{2}\b", re.I)
HEADING_RE = re.compile(r"^\s*((\d+(\.\d+)*[.)]?\s+[A-Z][\w &/-]{2,60})|([A-Z][A-Z &/-]{3,60}:?))\s*$")


class UploadRejected(ValueError):
    pass


# ----------------------------------------------------------------- embeddings
try:
    from langchain_core.embeddings import Embeddings as _LCEmbeddings
except Exception:  # pragma: no cover
    _LCEmbeddings = object  # type: ignore


class HashingEmbeddings(_LCEmbeddings):  # type: ignore[misc]
    """Deterministic local embedder (feature hashing of unigrams + bigrams).

    Lexical, not neural: it needs no API key, which keeps the demo reproducible.
    Set EMBEDDING_PROVIDER=openai for neural embeddings.
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        toks = re.findall(r"[a-z0-9]+(?:[-.][a-z0-9]+)*", text.lower())
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        v = [0.0] * self.dim
        for t in feats:
            h = int.from_bytes(hashlib.blake2b(t.encode(), digest_size=8).digest(), "big")
            v[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [round(x / n, 6) for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class OpenAIEmbeddingsLite(_LCEmbeddings):  # type: ignore[misc]
    def __init__(self, api_key: str, dim: int) -> None:
        from openai import OpenAI

        self.client, self.dim = OpenAI(api_key=api_key), dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        r = self.client.embeddings.create(model="text-embedding-3-small", input=texts, dimensions=self.dim)
        return [d.embedding for d in r.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def get_embedder():
    s = get_settings()
    if s.embedding_provider == "openai" and s.openai_api_key:
        return OpenAIEmbeddingsLite(s.openai_api_key, s.embedding_dim), "openai text-embedding-3-small"
    return HashingEmbeddings(s.embedding_dim), "local hashing embedder (lexical)"


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# ----------------------------------------------------------------- DB2VS bridge
_db2vs = None


def get_db2_vector_store(db: Database):
    """langchain-db2 DB2VS bound to the app's ibm_db_dbi connection (Db2 12.1.2+ only)."""
    global _db2vs
    if _db2vs is not None:
        return _db2vs
    if db.mode != "db2" or not db.supports_vector():
        return None
    from langchain_community.vectorstores.utils import DistanceStrategy  # noqa: F401  (pulled by langchain-db2)
    from langchain_db2 import DB2VS

    emb, _ = get_embedder()
    _db2vs = DB2VS(embedding_function=emb, table_name=get_settings().vector_table,
                   client=db.raw_connection(), distance_strategy=_cosine_strategy())
    return _db2vs


def _cosine_strategy():
    try:
        from langchain_community.vectorstores.utils import DistanceStrategy
    except ImportError:  # pragma: no cover
        from langchain_db2.db2vs import DistanceStrategy  # type: ignore
    return DistanceStrategy.COSINE


def retrieval_engine(db: Database) -> str:
    if db.mode == "db2" and db.supports_vector():
        return "db2-vector (langchain-db2 DB2VS, VECTOR_DISTANCE COSINE)"
    return "json-vector cosine (fallback" + (", DEV MODE" if db.mode == "dev" else ", Db2 without VECTOR type") + ")"


# ----------------------------------------------------------------- parsing
def parse_pages(data: bytes, ext: str) -> list[str]:
    if ext == ".pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            return [(p.extract_text() or "") for p in reader.pages]
        except Exception as exc:
            raise UploadRejected(f"Unreadable PDF: {exc}") from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadRejected("Text files must be UTF-8 encoded") from exc
    # treat form-feed or '=== Page n ===' markers as page breaks
    pages = re.split(r"\f|^=+\s*page\s+\d+\s*=+\s*$", text, flags=re.I | re.M)
    return [p for p in pages if p.strip()] or [text]


def _sections(page_text: str) -> list[tuple[str, str]]:
    """Split a page into (section_label, paragraph) pairs."""
    section, out, buf = "", [], []
    for line in page_text.splitlines():
        if HEADING_RE.match(line) and len(line.strip()) < 70:
            if buf:
                out.append((section, "\n".join(buf).strip()))
                buf = []
            section = line.strip().rstrip(":")
        else:
            buf.append(line)
    if buf:
        out.append((section, "\n".join(buf).strip()))
    return [(s, t) for s, t in out if t]


def guess_doc_type(filename: str, text: str) -> str:
    f, t = filename.lower(), text.lower()
    if "certificate" in f or "certificate of" in t or "fssc" in t:
        return "SUPPLIER_CERTIFICATE" if "analysis" not in t else "LAB_REPORT"
    if "lab" in f or "test report" in t or "laboratory" in t:
        return "LAB_REPORT"
    if "notice" in f or "alert" in t:
        return "CONTAMINATION_NOTICE"
    if "qc" in f or "pasteuris" in t or "quality control" in t:
        return "QC_RECORD"
    return "OTHER"


def extract_claims(db: Database, pages: list[str], filename: str) -> dict[str, Any]:
    """Grounded, rule-based extraction. Each claim = value + page + section + verbatim snippet."""
    claims: list[dict[str, Any]] = []
    suppliers = db.query("SELECT supplier_id, supplier_name FROM suppliers")
    known_lots = {r["lot_id"] for r in db.query("SELECT lot_id FROM ingredient_lots")}
    known_batches = {r["batch_id"] for r in db.query("SELECT batch_id FROM production_batches")}
    seen: set[tuple[str, str, int]] = set()

    def add(kind: str, value: str, page: int, section: str, line: str, **extra: Any) -> None:
        key = (kind, value.lower(), page)
        if key in seen:
            return
        seen.add(key)
        claims.append({"type": kind, "value": value, "page": page, "section": section or None,
                       "snippet": line.strip()[:300], "source": filename, **extra})

    for pno, page in enumerate(pages, start=1):
        for section, para in _sections(page):
            for line in para.splitlines():
                if not line.strip():
                    continue
                for m in LOT_RE.findall(line):
                    if not m.startswith("PB-"):
                        add("lot_id", m, pno, section, line, exists_in_db=m in known_lots)
                for m in BATCH_RE.findall(line):
                    add("batch_id", m, pno, section, line, exists_in_db=m in known_batches)
                for m in ISO_DATE_RE.findall(line):
                    add("date", m, pno, section, line)
                for m in TEXT_DATE_RE.finditer(line):
                    add("date", m.group(0), pno, section, line)
                low = line.lower()
                for s in suppliers:
                    if s["supplier_name"].lower() in low:
                        add("supplier", s["supplier_name"], pno, section, line, supplier_id=s["supplier_id"])
                for c in CONTAMINANTS:
                    if re.search(rf"\b{re.escape(c)}\b", line, re.I):
                        add("contaminant", c, pno, section, line)
                        break
                if RESULT_HINTS.search(line) and any(re.search(rf"\b{re.escape(c)}\b", para, re.I) for c in CONTAMINANTS):
                    positive = bool(re.search(r"(?<!not\s)\b(detected|positive|confirmed|presumptive|exceed)", low)) and "not detected" not in low
                    add("test_result", line.strip()[:200], pno, section, line, positive=positive)
                if SEVERITY_HINTS.search(line):
                    add("severity_indicator", SEVERITY_HINTS.search(line).group(0), pno, section, line)
    positives = [c for c in claims if c["type"] == "test_result" and c.get("positive")]
    return {
        "claims": claims,
        "summary": {
            "lot_ids": sorted({c["value"] for c in claims if c["type"] == "lot_id"}),
            "batch_ids": sorted({c["value"] for c in claims if c["type"] == "batch_id"}),
            "contaminants": sorted({c["value"] for c in claims if c["type"] == "contaminant"}),
            "suppliers": sorted({c["value"] for c in claims if c["type"] == "supplier"}),
            "positive_results": len(positives),
            "unknown_ids": sorted({c["value"] for c in claims if c["type"] in ("lot_id", "batch_id") and not c.get("exists_in_db")}),
        },
        "method": "rule-based grounded extraction (regex + Db2 master-data matching)",
    }


# ----------------------------------------------------------------- ingest
def ingest_document(db: Database, *, filename: str, data: bytes, uploaded_by: str, role: str,
                    incident_id: str | None = None, doc_type: str | None = None) -> dict[str, Any]:
    settings = get_settings()
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename or "upload").name)[:120] or "upload"
    ext = Path(safe).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise UploadRejected(f"File type '{ext or 'none'}' not allowed. Allowed: {', '.join(ALLOWED_EXT)}")
    if not data:
        raise UploadRejected("Empty file")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise UploadRejected(f"File exceeds {settings.max_upload_mb} MB limit")
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        raise UploadRejected("File content is not a PDF")
    if doc_type and doc_type not in DOC_TYPES:
        raise UploadRejected(f"doc_type must be one of {DOC_TYPES}")
    if incident_id and not db.query_one("SELECT incident_id FROM contamination_incidents WHERE incident_id = ?", (incident_id,)):
        raise NotFound(f"Incident {incident_id} not found")

    sha = hashlib.sha256(data).hexdigest()
    existing = db.query_one("SELECT document_id FROM evidence_documents WHERE sha256 = ?", (sha,))
    if existing:
        if incident_id:
            db.execute("UPDATE evidence_documents SET incident_id = ? WHERE document_id = ? AND incident_id IS NULL",
                       (incident_id, existing["document_id"]))
        doc = get_document(db, existing["document_id"])
        doc["duplicate"] = True
        return doc

    pages = parse_pages(data, ext)
    full = "\n".join(pages)
    if not full.strip():
        raise UploadRejected("No extractable text (scanned PDFs need OCR first)")
    dtype = doc_type or guess_doc_type(safe, full)
    extracted = extract_claims(db, pages, safe)
    doc_id = new_id("DOC")
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    stored = path / f"{doc_id}_{safe}"
    stored.write_bytes(data)

    embedder, emb_name = get_embedder()
    chunks = []
    for pno, page in enumerate(pages, start=1):
        for section, para in _sections(page):
            for i in range(0, len(para), 800):
                chunks.append((pno, section, para[i:i + 800]))
    vectors = embedder.embed_documents([c[2] for c in chunks]) if chunks else []

    try:
        with db.transaction():
            db.execute(
                "INSERT INTO evidence_documents (document_id, incident_id, filename, doc_type, mime_type, size_bytes, sha256, page_count, "
                "verification_status, extracted_json, uploaded_by, storage_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (doc_id, incident_id, safe, dtype, ALLOWED_EXT[ext], len(data), sha, len(pages), "UNVERIFIED",
                 dumps(extracted), uploaded_by, str(stored)))
            for n, ((pno, section, text), vec) in enumerate(zip(chunks, vectors)):
                db.execute(
                    "INSERT INTO evidence_chunks (chunk_id, document_id, chunk_no, page_no, section_label, content, embedding_json) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (f"{doc_id}-C{n:03d}", doc_id, n, pno, (section or None) and section[:120], text[:4000], dumps(vec)))
            audit(db, uploaded_by, role, "EVIDENCE_UPLOADED", "EVIDENCE", doc_id,
                  {"filename": safe, "doc_type": dtype, "sha256": sha, "incident_id": incident_id,
                   "claims": len(extracted["claims"])})
    except IntegrityViolation:
        stored.unlink(missing_ok=True)
        raise

    vs = None
    try:
        vs = get_db2_vector_store(db)
        if vs is not None and chunks:
            vs.add_texts([c[2] for c in chunks],
                         metadatas=[{"id": f"{doc_id}-C{n:03d}", "document_id": doc_id, "page_no": c[0], "section": c[1]}
                                    for n, c in enumerate(chunks)])
    except Exception as exc:  # vector indexing must never lose the evidence itself
        log.warning("DB2VS indexing failed, JSON-vector fallback remains available: %s", exc)
    doc = get_document(db, doc_id)
    doc["indexing"] = {"chunks": len(chunks), "embedder": emb_name, "engine": retrieval_engine(db)}
    return doc


def seed_document(db: Database, path: Path, *, doc_id_hint: str | None = None, incident_id: str | None = None,
                  doc_type: str | None = None, verified: bool = False) -> dict[str, Any]:
    doc = ingest_document(db, filename=path.name, data=path.read_bytes(), uploaded_by="system.seed", role="admin",
                          incident_id=incident_id, doc_type=doc_type)
    if verified:
        db.execute("UPDATE evidence_documents SET verification_status = 'VERIFIED' WHERE document_id = ?", (doc["document_id"],))
    return doc


# ----------------------------------------------------------------- queries
def _doc_row(r: dict[str, Any]) -> dict[str, Any]:
    r = dict(r)
    r["extracted"] = loads(r.pop("extracted_json", None), {})
    r.pop("storage_path", None)
    return r


def list_documents(db: Database, incident_id: str | None = None, doc_type: str | None = None) -> list[dict[str, Any]]:
    where, params = [], []
    if incident_id:
        where.append("incident_id = ?")
        params.append(incident_id)
    if doc_type:
        where.append("doc_type = ?")
        params.append(doc_type)
    rows = db.query(
        "SELECT document_id, incident_id, filename, doc_type, mime_type, size_bytes, sha256, page_count, verification_status, "
        "extracted_json, uploaded_by, created_at FROM evidence_documents"
        + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY created_at DESC, document_id", params)
    return [_doc_row(r) for r in rows]


def get_document(db: Database, document_id: str) -> dict[str, Any]:
    r = db.query_one(
        "SELECT document_id, incident_id, filename, doc_type, mime_type, size_bytes, sha256, page_count, verification_status, "
        "extracted_json, uploaded_by, created_at, storage_path FROM evidence_documents WHERE document_id = ?", (document_id,))
    if not r:
        raise NotFound(f"Document {document_id} not found")
    return _doc_row(r)


def set_verification(db: Database, document_id: str, status: str, actor: str, role: str) -> dict[str, Any]:
    if status not in ("UNVERIFIED", "VERIFIED", "DISPUTED"):
        raise ValueError("invalid verification status")
    get_document(db, document_id)
    db.execute("UPDATE evidence_documents SET verification_status = ? WHERE document_id = ?", (status, document_id))
    audit(db, actor, role, "EVIDENCE_VERIFICATION_SET", "EVIDENCE", document_id, {"status": status})
    return get_document(db, document_id)


def search(db: Database, query: str, k: int = 8, incident_id: str | None = None) -> dict[str, Any]:
    query = (query or "").strip()[:300]
    if not query:
        return {"query": query, "results": [], "engine": retrieval_engine(db)}
    k = max(1, min(int(k), 25))
    vs = None
    try:
        vs = get_db2_vector_store(db)
    except Exception as exc:  # pragma: no cover - only reachable on Db2
        log.warning("DB2VS unavailable: %s", exc)
    results: list[dict[str, Any]] = []
    if vs is not None:
        for doc, dist in vs.similarity_search_with_score(query, k=k * 2):
            md = doc.metadata or {}
            results.append({"chunk_id": md.get("id"), "document_id": md.get("document_id"), "page_no": md.get("page_no"),
                            "section_label": md.get("section"), "content": doc.page_content, "score": round(1 - float(dist), 4)})
    else:
        embedder, _ = get_embedder()
        qv = embedder.embed_query(query)
        rows = db.query(
            "SELECT c.chunk_id, c.document_id, c.page_no, c.section_label, c.content, c.embedding_json "
            "FROM evidence_chunks c JOIN evidence_documents d ON d.document_id = c.document_id"
            + (" WHERE d.incident_id = ?" if incident_id else ""), (incident_id,) if incident_id else ())
        terms = [t for t in re.findall(r"\w{3,}", query.lower())]
        for r in rows:
            vec = loads(r.pop("embedding_json"), [])
            score = _cos(qv, vec) if vec else 0.0
            text = r["content"].lower()
            score += 0.05 * sum(1 for t in terms if t in text)  # light lexical boost
            r["score"] = round(score, 4)
            results.append(r)
    docs = {d["document_id"]: d for d in list_documents(db)}
    out = []
    for r in sorted(results, key=lambda x: x["score"], reverse=True):
        d = docs.get(r["document_id"])
        if not d or (incident_id and d.get("incident_id") != incident_id):
            continue
        out.append({**r, "filename": d["filename"], "doc_type": d["doc_type"],
                    "verification_status": d["verification_status"],
                    "citation": f"{d['filename']} · p.{r['page_no']}" + (f" · {r['section_label']}" if r.get("section_label") else "")})
        if len(out) >= k:
            break
    return {"query": query, "results": out, "engine": retrieval_engine(db)}
