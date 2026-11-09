"""
GitMind 2.0 — Shared Multi-Agent Repository Intelligence & Memory

Central storage abstraction for GitMind 2.0 backed by IBM Db2:
- Unified repository metadata and artifact access
- Knowledge Graph relationship traversal (touches, modifies, references, parent_of)
- Multi-agent persistent memory & finding reuse across CLI sessions
- Grounded evidence verification layer
- Append-only audit logging
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import config
from data.db2.connection import Db2ConnectionManager, get_connection_manager
from data.db2.vector_store import Db2VectorStore, get_db2_vector_store
from data.evidence_models import AgentFinding, EvidenceReference, VerificationStatus
from utils.repo_utils import get_head_sha, get_repo_id, get_repo_key, get_repo_remote_url
from utils.security import sanitize_agent_input

logger = logging.getLogger("gitmind.repository_memory")


class RepositoryMemory:
    """
    Shared repository intelligence interface connecting LangGraph agents to IBM Db2.
    """

    def __init__(
        self,
        connection_manager: Optional[Db2ConnectionManager] = None,
        vector_store: Optional[Db2VectorStore] = None,
    ):
        self.connection_manager = connection_manager or get_connection_manager()
        self.vector_store = vector_store or get_db2_vector_store()

    # -----------------------------------------------------------------------
    # Repository Registration
    # -----------------------------------------------------------------------

    def ensure_repository_registered(self, repo_path: str = ".") -> str:
        """
        Registers or updates the repository in GITMIND_REPOSITORIES.
        Returns the stable REPO_ID.
        """
        repo_id = get_repo_id(repo_path)
        repo_key = get_repo_key(repo_path)
        remote_url = get_repo_remote_url(repo_path) or ""
        head_sha = ""
        try:
            head_sha = get_head_sha(repo_path)
        except Exception:
            pass

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        with self.connection_manager.cursor() as cur:
            # Check if exists
            cur.execute(
                "SELECT REPO_ID FROM GITMIND_REPOSITORIES WHERE REPO_ID = ?",
                (repo_id,),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    """
                    UPDATE GITMIND_REPOSITORIES
                    SET REPO_KEY = ?, REMOTE_URL = ?, INDEXED_HEAD_SHA = ?,
                        EMBEDDING_MODEL = ?, EMBEDDING_DIMENSION = ?, UPDATED_AT = ?
                    WHERE REPO_ID = ?
                    """,
                    (
                        repo_key,
                        remote_url,
                        head_sha,
                        config.EMBEDDING_MODEL,
                        config.get_embedding_dimension(),
                        now,
                        repo_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO GITMIND_REPOSITORIES
                        (REPO_ID, REPO_KEY, REMOTE_URL, DEFAULT_BRANCH, INDEXED_HEAD_SHA,
                         EMBEDDING_MODEL, EMBEDDING_DIMENSION, SCHEMA_VERSION, CREATED_AT, UPDATED_AT)
                    VALUES (?, ?, ?, 'main', ?, ?, ?, '2.0', ?, ?)
                    """,
                    (
                        repo_id,
                        repo_key,
                        remote_url,
                        head_sha,
                        config.EMBEDDING_MODEL,
                        config.get_embedding_dimension(),
                        now,
                        now,
                    ),
                )

        return repo_id

    # -----------------------------------------------------------------------
    # Semantic Search via Db2
    # -----------------------------------------------------------------------

    def search_repository_memory(
        self,
        query: str,
        repo_id: str,
        top_k: int = 5,
        filter_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Queries Db2 vectors for semantically related commits, PRs, issues, and code.
        Strictly restricted to the requested repo_id.
        """
        results = self.vector_store.similarity_search_with_score(
            query=query,
            k=top_k,
            repo_id=repo_id,
            filter_type=filter_type,
        )

        formatted = []
        for doc, distance in results:
            formatted.append({
                "text": doc.page_content,
                "score": round(1.0 - distance, 4) if distance is not None else 1.0,
                "distance": distance,
                "metadata": doc.metadata,
                "artifact_id": doc.metadata.get("artifact_id"),
                "artifact_type": doc.metadata.get("type"),
                "commit_sha": doc.metadata.get("hash") or doc.metadata.get("commit_sha"),
                "file_path": doc.metadata.get("file_path"),
            })

        return formatted

    # -----------------------------------------------------------------------
    # Relational & Knowledge Graph Queries
    # -----------------------------------------------------------------------

    def get_commit_context(self, commit_sha: str, repo_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves detailed commit artifact and all connected knowledge graph entities.
        """
        with self.connection_manager.cursor() as cur:
            cur.execute(
                """
                SELECT ARTIFACT_ID, TITLE, CONTENT, AUTHOR, FILE_PATH, CREATED_AT, CONTENT_HASH
                FROM GITMIND_ARTIFACTS
                WHERE REPO_ID = ? AND ARTIFACT_TYPE = 'commit'
                  AND (SOURCE_KEY LIKE ? OR COMMIT_SHA LIKE ?)
                FETCH FIRST 1 ROWS ONLY
                """,
                (repo_id, f"{commit_sha}%", f"{commit_sha}%"),
            )
            row = cur.fetchone()
            if not row:
                return None

            artifact_id, title, content, author, file_path, created_at, content_hash = row

            # Retrieve connected relations
            cur.execute(
                """
                SELECT R.RELATION_TYPE, A.ARTIFACT_ID, A.ARTIFACT_TYPE, A.SOURCE_KEY, A.TITLE, A.FILE_PATH
                FROM GITMIND_RELATIONS R
                JOIN GITMIND_ARTIFACTS A ON R.TARGET_ARTIFACT_ID = A.ARTIFACT_ID
                WHERE R.REPO_ID = ? AND R.SOURCE_ARTIFACT_ID = ?
                """,
                (repo_id, artifact_id),
            )
            relations = [
                {
                    "relation_type": r[0],
                    "target_artifact_id": r[1],
                    "target_type": r[2],
                    "source_key": r[3],
                    "title": r[4],
                    "file_path": r[5],
                }
                for r in cur.fetchall()
            ]

            return {
                "artifact_id": artifact_id,
                "commit_sha": commit_sha,
                "title": title,
                "content": content,
                "author": author,
                "created_at": str(created_at),
                "content_hash": content_hash,
                "relations": relations,
            }

    def get_file_history(self, file_path: str, repo_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieves commits and changes touching a specific file using the Knowledge Graph.
        """
        with self.connection_manager.cursor() as cur:
            cur.execute(
                """
                SELECT A.ARTIFACT_ID, A.COMMIT_SHA, A.TITLE, A.AUTHOR, A.CREATED_AT
                FROM GITMIND_ARTIFACTS A
                WHERE A.REPO_ID = ? AND A.FILE_PATH = ?
                ORDER BY A.CREATED_AT DESC
                FETCH FIRST ? ROWS ONLY
                """,
                (repo_id, file_path, limit),
            )
            rows = cur.fetchall()
            return [
                {
                    "artifact_id": r[0],
                    "commit_sha": r[1],
                    "title": r[2],
                    "author": r[3],
                    "created_at": str(r[4]),
                }
                for r in rows
            ]

    def get_symbol_history(
        self,
        symbol_name: str,
        repo_id: str,
        file_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Traces function/class evolution across commits using Tree-sitter indexed symbols.
        """
        with self.connection_manager.cursor() as cur:
            if file_path:
                cur.execute(
                    """
                    SELECT A.ARTIFACT_ID, A.SOURCE_KEY, A.COMMIT_SHA, A.FILE_PATH,
                           A.START_LINE, A.END_LINE, A.TITLE, A.CONTENT
                    FROM GITMIND_ARTIFACTS A
                    WHERE A.REPO_ID = ? AND A.ARTIFACT_TYPE IN ('function', 'class')
                      AND A.SOURCE_KEY = ? AND A.FILE_PATH = ?
                    ORDER BY A.CREATED_AT DESC
                    FETCH FIRST 20 ROWS ONLY
                    """,
                    (repo_id, symbol_name, file_path),
                )
            else:
                cur.execute(
                    """
                    SELECT A.ARTIFACT_ID, A.SOURCE_KEY, A.COMMIT_SHA, A.FILE_PATH,
                           A.START_LINE, A.END_LINE, A.TITLE, A.CONTENT
                    FROM GITMIND_ARTIFACTS A
                    WHERE A.REPO_ID = ? AND A.ARTIFACT_TYPE IN ('function', 'class')
                      AND A.SOURCE_KEY = ?
                    ORDER BY A.CREATED_AT DESC
                    FETCH FIRST 20 ROWS ONLY
                    """,
                    (repo_id, symbol_name),
                )

            rows = cur.fetchall()
            return [
                {
                    "artifact_id": r[0],
                    "symbol_name": r[1],
                    "commit_sha": r[2],
                    "file_path": r[3],
                    "start_line": r[4],
                    "end_line": r[5],
                    "title": r[6],
                    "content": r[7],
                }
                for r in rows
            ]

    def get_related_artifacts(
        self,
        artifact_id: str,
        repo_id: str,
        relation_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Traverses relationships in the Db2 Repository Knowledge Graph.
        """
        with self.connection_manager.cursor() as cur:
            if relation_types:
                placeholders = ",".join(["?"] * len(relation_types))
                params = [repo_id, artifact_id] + relation_types
                cur.execute(
                    f"""
                    SELECT R.RELATION_TYPE, A.ARTIFACT_ID, A.ARTIFACT_TYPE, A.SOURCE_KEY,
                           A.TITLE, A.FILE_PATH, A.COMMIT_SHA
                    FROM GITMIND_RELATIONS R
                    JOIN GITMIND_ARTIFACTS A ON R.TARGET_ARTIFACT_ID = A.ARTIFACT_ID
                    WHERE R.REPO_ID = ? AND R.SOURCE_ARTIFACT_ID = ?
                      AND R.RELATION_TYPE IN ({placeholders})
                    """,
                    tuple(params),
                )
            else:
                cur.execute(
                    """
                    SELECT R.RELATION_TYPE, A.ARTIFACT_ID, A.ARTIFACT_TYPE, A.SOURCE_KEY,
                           A.TITLE, A.FILE_PATH, A.COMMIT_SHA
                    FROM GITMIND_RELATIONS R
                    JOIN GITMIND_ARTIFACTS A ON R.TARGET_ARTIFACT_ID = A.ARTIFACT_ID
                    WHERE R.REPO_ID = ? AND R.SOURCE_ARTIFACT_ID = ?
                    """,
                    (repo_id, artifact_id),
                )

            return [
                {
                    "relation_type": r[0],
                    "artifact_id": r[1],
                    "artifact_type": r[2],
                    "source_key": r[3],
                    "title": r[4],
                    "file_path": r[5],
                    "commit_sha": r[6],
                }
                for r in cur.fetchall()
            ]

    # -----------------------------------------------------------------------
    # Persistent Findings & Multi-Agent Memory
    # -----------------------------------------------------------------------

    def save_finding(
        self,
        finding: AgentFinding,
        repo_id: str,
        agent_run_id: Optional[str] = None,
    ) -> str:
        """
        Persists a structured engineering finding and its supporting evidence in Db2.
        Also indexes the finding in the vector store for semantic recall in future sessions.
        """
        finding_id = hashlib.sha256(
            f"{repo_id}:{finding.agent_name}:{finding.title}:{datetime.now(timezone.utc).isoformat()}".encode()
        ).hexdigest()[:16].upper()

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        with self.connection_manager.cursor() as cur:
            cur.execute(
                """
                INSERT INTO GITMIND_FINDINGS
                    (FINDING_ID, REPO_ID, AGENT_RUN_ID, AGENT_NAME, FINDING_TYPE,
                     TITLE, SUMMARY, SEVERITY, STATUS, CREATED_AT)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
                """,
                (
                    finding_id,
                    repo_id,
                    agent_run_id,
                    finding.agent_name,
                    finding.finding_type,
                    finding.title,
                    finding.summary,
                    finding.severity,
                    now,
                ),
            )

            # Insert evidence citations
            for ev in finding.evidence:
                ev_id = str(uuid.uuid4())[:16].upper()
                cur.execute(
                    """
                    INSERT INTO GITMIND_FINDING_EVIDENCE
                        (EVIDENCE_ID, FINDING_ID, ARTIFACT_ID, COMMIT_SHA, FILE_PATH,
                         START_LINE, END_LINE, EVIDENCE_TYPE, CONTENT_HASH, SOURCE_URL, CREATED_AT)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ev_id,
                        finding_id,
                        ev.artifact_id,
                        ev.commit_sha,
                        ev.file_path,
                        ev.start_line,
                        ev.end_line,
                        ev.artifact_type,
                        ev.content_hash,
                        ev.source_url,
                        now,
                    ),
                )

        # Index finding into Db2 vector store for semantic retrieval
        try:
            finding_text = f"Historical finding by {finding.agent_name}: {finding.title}. {finding.summary}"
            self.vector_store.add_texts(
                texts=[finding_text],
                metadatas=[{
                    "type": "finding",
                    "finding_id": finding_id,
                    "finding_type": finding.finding_type,
                    "agent_name": finding.agent_name,
                    "repo_id": repo_id,
                    "severity": finding.severity,
                }],
                ids=[f"{repo_id}:finding:{finding_id}"],
            )
        except Exception as e:
            logger.warning(f"Failed to vector-index finding {finding_id}: {e}")

        # Audit finding creation
        self.record_audit_event(
            repo_id=repo_id,
            event_type="FINDING_CREATED",
            actor=finding.agent_name,
            details={"finding_id": finding_id, "title": finding.title, "type": finding.finding_type},
        )

        return finding_id

    def get_previous_findings(
        self,
        repo_id: str,
        finding_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves historical findings and their attached evidence for the repository.
        """
        with self.connection_manager.cursor() as cur:
            if finding_type:
                cur.execute(
                    """
                    SELECT FINDING_ID, AGENT_NAME, FINDING_TYPE, TITLE, SUMMARY, SEVERITY, CREATED_AT
                    FROM GITMIND_FINDINGS
                    WHERE REPO_ID = ? AND STATUS = 'ACTIVE' AND FINDING_TYPE = ?
                    ORDER BY CREATED_AT DESC
                    FETCH FIRST ? ROWS ONLY
                    """,
                    (repo_id, finding_type, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT FINDING_ID, AGENT_NAME, FINDING_TYPE, TITLE, SUMMARY, SEVERITY, CREATED_AT
                    FROM GITMIND_FINDINGS
                    WHERE REPO_ID = ? AND STATUS = 'ACTIVE'
                    ORDER BY CREATED_AT DESC
                    FETCH FIRST ? ROWS ONLY
                    """,
                    (repo_id, limit),
                )

            findings_raw = cur.fetchall()
            findings = []
            for row in findings_raw:
                f_id = row[0]
                cur.execute(
                    """
                    SELECT ARTIFACT_ID, COMMIT_SHA, FILE_PATH, START_LINE, END_LINE, EVIDENCE_TYPE, SOURCE_URL
                    FROM GITMIND_FINDING_EVIDENCE
                    WHERE FINDING_ID = ?
                    """,
                    (f_id,),
                )
                evidence = [
                    {
                        "artifact_id": e[0],
                        "commit_sha": e[1],
                        "file_path": e[2],
                        "start_line": e[3],
                        "end_line": e[4],
                        "artifact_type": e[5],
                        "source_url": e[6],
                    }
                    for e in cur.fetchall()
                ]

                findings.append({
                    "finding_id": f_id,
                    "agent_name": row[1],
                    "finding_type": row[2],
                    "title": row[3],
                    "summary": row[4],
                    "severity": row[5],
                    "created_at": str(row[6]),
                    "evidence": evidence,
                })

            return findings

    def get_similar_findings(
        self,
        query: str,
        repo_id: str,
        finding_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Semantically queries previous findings in Db2 to check for historical precedents.
        """
        results = self.vector_store.similarity_search_with_score(
            query=query,
            k=top_k,
            repo_id=repo_id,
            filter_type="finding",
        )

        findings = []
        for doc, dist in results:
            f_id = doc.metadata.get("finding_id")
            if not f_id:
                continue
            with self.connection_manager.cursor() as cur:
                cur.execute(
                    "SELECT AGENT_NAME, FINDING_TYPE, TITLE, SUMMARY, SEVERITY FROM GITMIND_FINDINGS WHERE FINDING_ID = ?",
                    (f_id,),
                )
                row = cur.fetchone()
                if row:
                    findings.append({
                        "finding_id": f_id,
                        "agent_name": row[0],
                        "finding_type": row[1],
                        "title": row[2],
                        "summary": row[3],
                        "severity": row[4],
                        "similarity_score": round(1.0 - dist, 4) if dist is not None else 1.0,
                    })

        if not findings:
            # Relational keyword search fallback across title and summary in Db2
            with self.connection_manager.cursor() as cur:
                like_term = f"%{query}%"
                cur.execute(
                    """
                    SELECT FINDING_ID, AGENT_NAME, FINDING_TYPE, TITLE, SUMMARY, SEVERITY, CREATED_AT
                    FROM GITMIND_FINDINGS
                    WHERE REPO_ID = ? AND (LOWER(TITLE) LIKE LOWER(?) OR LOWER(SUMMARY) LIKE LOWER(?))
                    ORDER BY CREATED_AT DESC
                    FETCH FIRST ? ROWS ONLY
                    """,
                    (repo_id, like_term, like_term, top_k),
                )
                for row in cur.fetchall():
                    findings.append({
                        "finding_id": row[0],
                        "agent_name": row[1],
                        "finding_type": row[2],
                        "title": row[3],
                        "summary": row[4],
                        "severity": row[5],
                        "similarity_score": 1.0,
                    })

        return findings

    # -----------------------------------------------------------------------
    # Evidence Verification Stage
    # -----------------------------------------------------------------------

    def verify_evidence(
        self,
        evidence_list: List[EvidenceReference],
        repo_id: str,
    ) -> List[EvidenceReference]:
        """
        Verifies each evidence citation against actual Db2 records or git history.
        Marks ungrounded / fabricated claims explicitly.
        """
        verified_list: List[EvidenceReference] = []

        with self.connection_manager.cursor() as cur:
            for ev in evidence_list:
                ev_copy = ev.model_copy()

                # Verify commit SHA
                if ev_copy.commit_sha:
                    sha_prefix = ev_copy.commit_sha[:8]
                    cur.execute(
                        """
                        SELECT ARTIFACT_ID FROM GITMIND_ARTIFACTS
                        WHERE REPO_ID = ? AND ARTIFACT_TYPE = 'commit'
                          AND (SOURCE_KEY LIKE ? OR COMMIT_SHA LIKE ?)
                        """,
                        (repo_id, f"{sha_prefix}%", f"{sha_prefix}%"),
                    )
                    if cur.fetchone():
                        ev_copy.verification_status = VerificationStatus.VERIFIED
                        ev_copy.verification_note = "Verified commit in repository database."
                    else:
                        ev_copy.verification_status = VerificationStatus.UNGROUNDED
                        ev_copy.verification_note = f"Commit '{ev_copy.commit_sha}' not found in indexed records."

                # Verify file path
                elif ev_copy.file_path:
                    cur.execute(
                        """
                        SELECT ARTIFACT_ID FROM GITMIND_ARTIFACTS
                        WHERE REPO_ID = ? AND FILE_PATH = ?
                        """,
                        (repo_id, ev_copy.file_path),
                    )
                    if cur.fetchone():
                        ev_copy.verification_status = VerificationStatus.VERIFIED
                        ev_copy.verification_note = f"Verified file '{ev_copy.file_path}' in repository."
                    else:
                        ev_copy.verification_status = VerificationStatus.INFERRED
                        ev_copy.verification_note = f"File '{ev_copy.file_path}' not directly indexed."

                # Verify PR or issue
                elif ev_copy.artifact_type in ("pr", "issue") and ev_copy.artifact_id:
                    cur.execute(
                        """
                        SELECT ARTIFACT_ID FROM GITMIND_ARTIFACTS
                        WHERE REPO_ID = ? AND ARTIFACT_ID = ?
                        """,
                        (repo_id, ev_copy.artifact_id),
                    )
                    if cur.fetchone():
                        ev_copy.verification_status = VerificationStatus.VERIFIED
                        ev_copy.verification_note = f"Verified {ev_copy.artifact_type} reference."
                    else:
                        ev_copy.verification_status = VerificationStatus.UNGROUNDED
                        ev_copy.verification_note = f"Unverified {ev_copy.artifact_type} reference."

                else:
                    ev_copy.verification_status = VerificationStatus.INFERRED
                    ev_copy.verification_note = "Contextually inferred reference."

                verified_list.append(ev_copy)

        return verified_list

    # -----------------------------------------------------------------------
    # Agent Run Tracing & Audit Events
    # -----------------------------------------------------------------------

    def start_agent_run(
        self,
        repo_id: str,
        query: str,
        workflow_name: str,
        agents_invoked: List[str],
    ) -> str:
        """Records beginning of a multi-agent investigation."""
        run_id = str(uuid.uuid4())[:16].upper()
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
        query_summary = query[:1000]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        with self.connection_manager.cursor() as cur:
            cur.execute(
                """
                INSERT INTO GITMIND_AGENT_RUNS
                    (RUN_ID, REPO_ID, QUERY_HASH, QUERY_SUMMARY, WORKFLOW_NAME,
                     AGENTS_INVOKED, LLM_PROVIDER, LLM_MODEL, PROMPT_VERSION,
                     STATUS, START_TIME)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '2.0', 'IN_PROGRESS', ?)
                """,
                (
                    run_id,
                    repo_id,
                    query_hash,
                    query_summary,
                    workflow_name,
                    ",".join(agents_invoked),
                    config.LLM_PROVIDER,
                    config.GEMINI_MODEL if config.LLM_PROVIDER == "gemini" else config.OPENAI_MODEL,
                    now,
                ),
            )

        self.record_audit_event(
            repo_id=repo_id,
            event_type="AGENT_EXECUTION_START",
            actor=workflow_name,
            details={"run_id": run_id, "query_summary": query_summary},
        )
        return run_id

    def complete_agent_run(self, run_id: str, status: str = "SUCCESS") -> None:
        """Marks completion of an agent run."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with self.connection_manager.cursor() as cur:
            cur.execute(
                "UPDATE GITMIND_AGENT_RUNS SET STATUS = ?, COMPLETION_TIME = ? WHERE RUN_ID = ?",
                (status, now, run_id),
            )

    def record_audit_event(
        self,
        repo_id: str,
        event_type: str,
        actor: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Appends an immutable audit event to GITMIND_AUDIT_EVENTS.
        """
        event_id = str(uuid.uuid4())[:16].upper()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        details_json = json.dumps(details or {})

        try:
            with self.connection_manager.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO GITMIND_AUDIT_EVENTS
                        (EVENT_ID, REPO_ID, EVENT_TYPE, ACTOR, DETAILS, CREATED_AT)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (event_id, repo_id, event_type, actor, details_json, now),
                )
        except Exception as e:
            logger.warning(f"Could not record audit event {event_id}: {e}")

        return event_id


# Singleton repository memory service
_repo_memory_instance: Optional[RepositoryMemory] = None


def get_repository_memory() -> RepositoryMemory:
    """Retrieve singleton RepositoryMemory instance."""
    global _repo_memory_instance
    if _repo_memory_instance is None:
        _repo_memory_instance = RepositoryMemory()
    return _repo_memory_instance

