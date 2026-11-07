"""Db2-backed persistence for documents, sessions, claims, and evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.db.connection import execute, insert_returning_id, query_all, transaction
from app.models.domain import Classification, EvidenceReference, ExtractedClaim, PassageCandidate

_TABLES = (
    "DOCUMENTS",
    "PASSAGES",
    "VERIFICATION_SESSIONS",
    "CLAIMS",
    "VERIFICATION_RESULTS",
    "EVIDENCE_LINKS",
)

_EVIDENCE_RELATIONSHIP = {
    Classification.SUPPORTED: "SUPPORTS",
    Classification.CONTRADICTED: "CONTRADICTS",
    Classification.INSUFFICIENT_EVIDENCE: "CONTEXT",
    Classification.VERIFICATION_ERROR: "CONTEXT",
}


class Db2Repository:
    """All SQL lives here so routes and services never build queries."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.schema = self.settings.db2_schema.upper()

    # ------------------------------------------------------------------ health
    def health(self) -> dict[str, Any]:
        with transaction(self.settings) as connection:
            row = query_all(
                connection,
                "SELECT CURRENT SERVER AS server, CURRENT TIMESTAMP AS now FROM SYSIBM.SYSDUMMY1",
            )[0]
            tables = query_all(
                connection,
                (
                    "SELECT TABNAME AS name FROM SYSCAT.TABLES "
                    "WHERE TABSCHEMA = ? AND TYPE = 'T' ORDER BY TABNAME"
                ),
                (self.schema,),
            )
            existing = {table["name"] for table in tables}
        return {
            "connected": True,
            "server": row["server"],
            "server_time": row["now"],
            "schema": self.schema,
            "tables": [name for name in _TABLES if name in existing],
            "missing_tables": [name for name in _TABLES if name not in existing],
        }

    def table_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        with transaction(self.settings) as connection:
            for table in _TABLES:
                rows = query_all(connection, f"SELECT COUNT(*) AS total FROM {table}")
                counts[table.lower()] = int(rows[0]["total"]) if rows else 0
        return counts

    # --------------------------------------------------------------- documents
    def get_document_by_hash(self, content_hash: str) -> dict | None:
        with transaction(self.settings) as connection:
            rows = query_all(
                connection,
                (
                    "SELECT D.DOCUMENT_ID, D.TITLE, D.FILENAME, D.CONTENT_HASH, D.SOURCE_TYPE, "
                    "D.EXTERNAL_ID, D.PROCESSING_STATUS, D.CREATED_AT, "
                    "(SELECT COUNT(*) FROM PASSAGES P WHERE P.DOCUMENT_ID = D.DOCUMENT_ID) AS PASSAGE_COUNT "
                    "FROM DOCUMENTS D WHERE D.CONTENT_HASH = ? FETCH FIRST 1 ROW ONLY"
                ),
                (content_hash,),
            )
        return rows[0] if rows else None

    def create_document(
        self,
        *,
        title: str,
        filename: str,
        content_hash: str,
        source_type: str,
        passages: Iterable[tuple[str, int | None, int | None, int | None]],
        external_id: str | None = None,
    ) -> dict[str, Any]:
        with transaction(self.settings) as connection:
            document_id = insert_returning_id(
                connection,
                (
                    "INSERT INTO DOCUMENTS (TITLE, FILENAME, CONTENT_HASH, SOURCE_TYPE, EXTERNAL_ID, "
                    "PROCESSING_STATUS) VALUES (?, ?, ?, ?, ?, 'READY')"
                ),
                (title, filename, content_hash, source_type, external_id),
            )
            count = 0
            for index, (text, page_number, char_start, char_end) in enumerate(passages):
                insert_returning_id(
                    connection,
                    (
                        "INSERT INTO PASSAGES (DOCUMENT_ID, PASSAGE_TEXT, PAGE_NUMBER, PASSAGE_INDEX, "
                        "CHAR_START, CHAR_END) VALUES (?, ?, ?, ?, ?, ?)"
                    ),
                    (document_id, text, page_number, index, char_start, char_end),
                )
                count += 1
            rows = query_all(
                connection,
                "SELECT CREATED_AT FROM DOCUMENTS WHERE DOCUMENT_ID = ?",
                (document_id,),
            )
        return {
            "document_id": document_id,
            "title": title,
            "filename": filename,
            "content_hash": content_hash,
            "source_type": source_type,
            "external_id": external_id,
            "processing_status": "READY",
            "passage_count": count,
            "created_at": rows[0]["created_at"],
        }

    def list_documents(self, limit: int = 50, *, include_datasets: bool = False) -> list[dict]:
        where = "" if include_datasets else "WHERE D.SOURCE_TYPE <> 'scifact' "
        with transaction(self.settings) as connection:
            return query_all(
                connection,
                (
                    "SELECT D.DOCUMENT_ID, D.TITLE, D.FILENAME, D.SOURCE_TYPE, D.PROCESSING_STATUS, "
                    "D.CREATED_AT, "
                    "(SELECT COUNT(*) FROM PASSAGES P WHERE P.DOCUMENT_ID = D.DOCUMENT_ID) AS PASSAGE_COUNT "
                    f"FROM DOCUMENTS D {where}ORDER BY D.CREATED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY"
                ),
            )

    def get_document(self, document_id: int) -> dict:
        with transaction(self.settings) as connection:
            rows = query_all(
                connection,
                (
                    "SELECT DOCUMENT_ID, TITLE, FILENAME, CONTENT_HASH, SOURCE_TYPE, EXTERNAL_ID, "
                    "PROCESSING_STATUS, CREATED_AT FROM DOCUMENTS WHERE DOCUMENT_ID = ?"
                ),
                (document_id,),
            )
            if not rows:
                raise NotFoundError("Evidence document not found.")
            passages = query_all(
                connection,
                (
                    "SELECT PASSAGE_ID, DOCUMENT_ID, PASSAGE_TEXT, PAGE_NUMBER, PASSAGE_INDEX, "
                    "CHAR_START, CHAR_END "
                    "FROM PASSAGES WHERE DOCUMENT_ID = ? ORDER BY PASSAGE_INDEX"
                ),
                (document_id,),
            )
        document = rows[0]
        document["passage_count"] = len(passages)
        document["passages"] = passages
        return document

    # --------------------------------------------------------- retrieval input
    def candidate_passages(
        self,
        document_ids: list[int] | None,
        tokens: list[str],
        limit: int = 500,
        source_type: str | None = None,
    ) -> list[PassageCandidate]:
        if (document_ids is not None and not document_ids) or not tokens:
            return []
        conditions: list[str] = []
        params: list[Any] = []
        if document_ids is not None:
            placeholders = ",".join("?" for _ in document_ids)
            conditions.append(f"P.DOCUMENT_ID IN ({placeholders})")
            params.extend(document_ids)
        if source_type:
            conditions.append("D.SOURCE_TYPE = ?")
            params.append(source_type)
        token_clauses = " OR ".join("LOWER(P.PASSAGE_TEXT) LIKE ?" for _ in tokens)
        conditions.append(f"({token_clauses})")
        params.extend(f"%{token}%" for token in tokens)
        where = " AND ".join(conditions)
        sql = (
            "SELECT P.PASSAGE_ID, P.DOCUMENT_ID, P.PASSAGE_TEXT, P.PAGE_NUMBER, P.PASSAGE_INDEX, "
            "D.TITLE AS DOCUMENT_TITLE, D.FILENAME "
            "FROM PASSAGES P JOIN DOCUMENTS D ON D.DOCUMENT_ID = P.DOCUMENT_ID "
            f"WHERE {where} "
            f"ORDER BY P.DOCUMENT_ID, P.PASSAGE_INDEX FETCH FIRST {int(limit)} ROWS ONLY"
        )
        with transaction(self.settings) as connection:
            rows = query_all(connection, sql, params)
        return [
            PassageCandidate(
                passage_id=int(row["passage_id"]),
                document_id=int(row["document_id"]),
                document_title=row["document_title"],
                filename=row["filename"],
                passage_text=row["passage_text"],
                page_number=row["page_number"],
                passage_index=int(row["passage_index"]),
            )
            for row in rows
        ]

    def bulk_import_documents(self, documents: list[dict[str, Any]]) -> dict[str, Any]:
        """Insert dataset documents in one transaction, skipping existing hashes.

        Each item: external_id, title, filename, content_hash, source_type,
        passages: [(text, page_number, char_start, char_end), ...].
        """
        with transaction(self.settings) as connection:
            existing_hashes = {
                row["content_hash"].strip()
                for row in query_all(connection, "SELECT CONTENT_HASH FROM DOCUMENTS")
            }
            imported = skipped = passage_count = 0
            for document in documents:
                if document["content_hash"] in existing_hashes:
                    skipped += 1
                    continue
                document_id = insert_returning_id(
                    connection,
                    (
                        "INSERT INTO DOCUMENTS (TITLE, FILENAME, CONTENT_HASH, SOURCE_TYPE, EXTERNAL_ID, "
                        "PROCESSING_STATUS) VALUES (?, ?, ?, ?, ?, 'READY')"
                    ),
                    (
                        document["title"],
                        document["filename"],
                        document["content_hash"],
                        document["source_type"],
                        document.get("external_id"),
                    ),
                )
                existing_hashes.add(document["content_hash"])
                for index, (text, page_number, char_start, char_end) in enumerate(
                    document["passages"]
                ):
                    insert_returning_id(
                        connection,
                        (
                            "INSERT INTO PASSAGES (DOCUMENT_ID, PASSAGE_TEXT, PAGE_NUMBER, PASSAGE_INDEX, "
                            "CHAR_START, CHAR_END) VALUES (?, ?, ?, ?, ?, ?)"
                        ),
                        (document_id, text, page_number, index, char_start, char_end),
                    )
                    passage_count += 1
                imported += 1
        return {"imported": imported, "skipped": skipped, "passages": passage_count}

    def external_id_map(self, source_type: str) -> dict[int, int]:
        with transaction(self.settings) as connection:
            rows = query_all(
                connection,
                "SELECT EXTERNAL_ID, DOCUMENT_ID FROM DOCUMENTS WHERE SOURCE_TYPE = ?",
                (source_type,),
            )
        mapping: dict[int, int] = {}
        for row in rows:
            try:
                mapping[int(row["external_id"])] = int(row["document_id"])
            except (TypeError, ValueError):
                continue
        return mapping

    def passages_for_source(self, source_type: str) -> list[PassageCandidate]:
        """Load all passages for a dataset source in one Db2 query."""
        with transaction(self.settings) as connection:
            rows = query_all(
                connection,
                (
                    "SELECT P.PASSAGE_ID, P.DOCUMENT_ID, P.PASSAGE_TEXT, P.PAGE_NUMBER, P.PASSAGE_INDEX, "
                    "D.TITLE AS DOCUMENT_TITLE, D.FILENAME "
                    "FROM PASSAGES P JOIN DOCUMENTS D ON D.DOCUMENT_ID = P.DOCUMENT_ID "
                    "WHERE D.SOURCE_TYPE = ? ORDER BY P.PASSAGE_ID"
                ),
                (source_type,),
            )
        return [
            PassageCandidate(
                passage_id=int(row["passage_id"]),
                document_id=int(row["document_id"]),
                document_title=row["document_title"],
                filename=row["filename"],
                passage_text=row["passage_text"],
                page_number=row["page_number"],
                passage_index=int(row["passage_index"]),
            )
            for row in rows
        ]

    # ---------------------------------------------------------------- sessions
    def create_session(self, submitted_text: str, model_provider: str) -> int:
        with transaction(self.settings) as connection:
            return insert_returning_id(
                connection,
                (
                    "INSERT INTO VERIFICATION_SESSIONS (SUBMITTED_TEXT, MODEL_PROVIDER, STATUS) "
                    "VALUES (?, ?, 'PROCESSING')"
                ),
                (submitted_text, model_provider),
            )

    def _finish_session(
        self,
        connection,
        session_id: int,
        status: str,
        error_message: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        execute(
            connection,
            (
                "UPDATE VERIFICATION_SESSIONS SET STATUS = ?, ERROR_MESSAGE = ?, "
                "COMPLETED_AT = CURRENT TIMESTAMP, DURATION_MS = ? WHERE SESSION_ID = ?"
            ),
            (status, error_message, duration_ms, session_id),
        )

    def set_session_status(
        self,
        session_id: int,
        status: str,
        error_message: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        with transaction(self.settings) as connection:
            self._finish_session(connection, session_id, status, error_message, duration_ms)

    def mark_session_failed(self, session_id: int, error_message: str, duration_ms: int | None) -> None:
        self.set_session_status(session_id, "FAILED", error_message, duration_ms)

    def save_results(
        self,
        session_id: int,
        claims: list[tuple[ExtractedClaim, Any]],
        status: str = "COMPLETED",
        duration_ms: int | None = None,
    ) -> None:
        """Persist claims, results, evidence links, and final status atomically."""
        with transaction(self.settings) as connection:
            for claim, assessment in claims:
                claim_id = insert_returning_id(
                    connection,
                    (
                        "INSERT INTO CLAIMS (SESSION_ID, ORIGINAL_CLAIM, NORMALIZED_CLAIM, CLAIM_TYPE, "
                        "POSITION_START, POSITION_END) VALUES (?, ?, ?, ?, ?, ?)"
                    ),
                    (
                        session_id,
                        claim.original_claim,
                        claim.normalized_claim,
                        claim.claim_type,
                        claim.position_start,
                        claim.position_end,
                    ),
                )
                result_id = insert_returning_id(
                    connection,
                    (
                        "INSERT INTO VERIFICATION_RESULTS (CLAIM_ID, CLASSIFICATION, EXPLANATION, LIMITATIONS, "
                        "NUMERICAL_ANALYSIS, VERIFICATION_METHOD, HUMAN_REVIEW_STATUS) "
                        "VALUES (?, ?, ?, ?, ?, ?, 'PENDING')"
                    ),
                    (
                        claim_id,
                        assessment.classification.value,
                        assessment.explanation,
                        assessment.limitations,
                        getattr(assessment, "numerical_analysis", None),
                        assessment.verification_method,
                    ),
                )
                relationship = _EVIDENCE_RELATIONSHIP.get(assessment.classification, "CONTEXT")
                for evidence in assessment.evidence:
                    insert_returning_id(
                        connection,
                        (
                            "INSERT INTO EVIDENCE_LINKS (RESULT_ID, PASSAGE_ID, EVIDENCE_RELATIONSHIP, "
                            "RELEVANCE_SCORE) VALUES (?, ?, ?, ?)"
                        ),
                        (
                            result_id,
                            evidence.passage_id,
                            relationship,
                            round(evidence.relevance_score, 6),
                        ),
                    )
            self._finish_session(connection, session_id, status, None, duration_ms)

    def list_sessions(self, limit: int = 25) -> list[dict]:
        with transaction(self.settings) as connection:
            sessions = query_all(
                connection,
                (
                    "SELECT S.SESSION_ID, S.STATUS, S.MODEL_PROVIDER, S.CREATED_AT, S.COMPLETED_AT, "
                    "S.DURATION_MS, LEFT(S.SUBMITTED_TEXT, 240) AS PREVIEW, "
                    "(SELECT COUNT(*) FROM CLAIMS C WHERE C.SESSION_ID = S.SESSION_ID) AS TOTAL_CLAIMS "
                    f"FROM VERIFICATION_SESSIONS S ORDER BY S.CREATED_AT DESC FETCH FIRST {int(limit)} ROWS ONLY"
                ),
            )
            for session in sessions:
                counts = query_all(
                    connection,
                    (
                        "SELECT R.CLASSIFICATION, COUNT(*) AS TOTAL "
                        "FROM CLAIMS C JOIN VERIFICATION_RESULTS R ON R.CLAIM_ID = C.CLAIM_ID "
                        "WHERE C.SESSION_ID = ? GROUP BY R.CLASSIFICATION"
                    ),
                    (session["session_id"],),
                )
                by_class = {row["classification"]: int(row["total"]) for row in counts}
                session["counts"] = {
                    "total": int(session["total_claims"]),
                    "supported": by_class.get(Classification.SUPPORTED.value, 0),
                    "contradicted": by_class.get(Classification.CONTRADICTED.value, 0),
                    "insufficient_evidence": by_class.get(Classification.INSUFFICIENT_EVIDENCE.value, 0),
                    "verification_error": by_class.get(Classification.VERIFICATION_ERROR.value, 0),
                }
        return sessions

    def get_session(self, session_id: int) -> dict:
        with transaction(self.settings) as connection:
            sessions = query_all(
                connection,
                (
                    "SELECT SESSION_ID, SUBMITTED_TEXT, MODEL_PROVIDER, STATUS, ERROR_MESSAGE, CREATED_AT, "
                    "COMPLETED_AT, DURATION_MS FROM VERIFICATION_SESSIONS WHERE SESSION_ID = ?"
                ),
                (session_id,),
            )
            if not sessions:
                raise NotFoundError("Verification session not found.")
            session = sessions[0]
            claims = query_all(
                connection,
                (
                    "SELECT C.CLAIM_ID, C.ORIGINAL_CLAIM, C.NORMALIZED_CLAIM, C.CLAIM_TYPE, "
                    "C.POSITION_START, C.POSITION_END, R.RESULT_ID, R.CLASSIFICATION, R.EXPLANATION, "
                    "R.LIMITATIONS, R.NUMERICAL_ANALYSIS, R.HUMAN_REVIEW_STATUS, R.VERIFICATION_METHOD, "
                    "R.CREATED_AT AS RESULT_CREATED_AT "
                    "FROM CLAIMS C LEFT JOIN VERIFICATION_RESULTS R ON R.CLAIM_ID = C.CLAIM_ID "
                    "WHERE C.SESSION_ID = ? ORDER BY C.CLAIM_ID"
                ),
                (session_id,),
            )
            evidence = query_all(
                connection,
                (
                    "SELECT E.RESULT_ID, E.PASSAGE_ID, E.RELEVANCE_SCORE, E.EVIDENCE_RELATIONSHIP, "
                    "P.PASSAGE_TEXT, P.PAGE_NUMBER, "
                    "P.PASSAGE_INDEX, D.DOCUMENT_ID, D.TITLE AS DOCUMENT_TITLE, D.FILENAME "
                    "FROM EVIDENCE_LINKS E "
                    "JOIN PASSAGES P ON P.PASSAGE_ID = E.PASSAGE_ID "
                    "JOIN DOCUMENTS D ON D.DOCUMENT_ID = P.DOCUMENT_ID "
                    "WHERE E.RESULT_ID IN (SELECT R.RESULT_ID FROM VERIFICATION_RESULTS R "
                    "JOIN CLAIMS C ON C.CLAIM_ID = R.CLAIM_ID WHERE C.SESSION_ID = ?) "
                    "ORDER BY E.RELEVANCE_SCORE DESC"
                ),
                (session_id,),
            )
        evidence_by_result: dict[int, list[dict]] = {}
        for item in evidence:
            evidence_by_result.setdefault(item["result_id"], []).append(item)
        for claim in claims:
            claim["evidence"] = evidence_by_result.get(claim.get("result_id"), [])
            claim.pop("result_id", None)

        counts = {
            "total": len(claims),
            "supported": sum(1 for c in claims if c.get("classification") == Classification.SUPPORTED.value),
            "contradicted": sum(1 for c in claims if c.get("classification") == Classification.CONTRADICTED.value),
            "insufficient_evidence": sum(
                1 for c in claims if c.get("classification") == Classification.INSUFFICIENT_EVIDENCE.value
            ),
            "verification_error": sum(
                1 for c in claims if c.get("classification") == Classification.VERIFICATION_ERROR.value
            ),
        }
        session["claims"] = claims
        session["counts"] = counts
        return session

    # ------------------------------------------------------------- test helper
    def truncate_all(self) -> None:
        """Used only by integration tests and explicit local resets."""
        with transaction(self.settings) as connection:
            for table in reversed(_TABLES):
                execute(connection, f"DELETE FROM {table}")
