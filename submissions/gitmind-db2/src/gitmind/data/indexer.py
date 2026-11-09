"""
GitMind 2.0 — Enterprise Repository Indexer & Knowledge Graph Constructor

Builds the unified Repository Knowledge Graph and Db2 Vector Store:
- Incremental and full indexing modes with atomic run tracking
- Git history extraction (commits, branches, parent-child links, diffs)
- Tree-sitter AST symbol extraction (functions, classes, methods, line ranges)
- Documentation chunking (Markdown headings, architecture docs)
- GitHub PR & Issue intent linkage (commit -> PR -> issue)
- Deterministic SHA-256 content deduplication and secret redaction
- Bounded batch sizes and transactional relational writes
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from git import Repo

import config
from data.db2.connection import Db2ConnectionManager, get_connection_manager
from data.db2.vector_store import Db2VectorStore, get_db2_vector_store
from tools.code_tools import _detect_language, _extract_definitions
from utils.repo_utils import get_head_sha, get_repo, get_repo_id, get_repo_key
from utils.security import is_path_safe_for_indexing, redact_secrets

logger = logging.getLogger("gitmind.indexer")


class RepositoryIndexer:
    """
    Ingests repository entities into IBM Db2 relational tables, Knowledge Graph,
    and Vector Store.
    """

    def __init__(
        self,
        connection_manager: Optional[Db2ConnectionManager] = None,
        vector_store: Optional[Db2VectorStore] = None,
    ):
        self.connection_manager = connection_manager or get_connection_manager()
        self.vector_store = vector_store or get_db2_vector_store()

    def index_repository(
        self,
        repo_path: str = ".",
        full: bool = False,
        days: int = 90,
    ) -> Dict[str, Any]:
        """
        Executes an incremental or full indexing operation on the repository.
        """
        repo = get_repo(repo_path)
        repo_id = get_repo_id(repo_path)
        repo_key = get_repo_key(repo_path)
        head_sha = get_head_sha(repo_path)
        run_id = str(uuid.uuid4())[:16].upper()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Check previous index state for incremental mode
        starting_head_sha = None
        if not full:
            with self.connection_manager.cursor() as cur:
                cur.execute(
                    "SELECT INDEXED_HEAD_SHA FROM GITMIND_REPOSITORIES WHERE REPO_ID = ?",
                    (repo_id,),
                )
                row = cur.fetchone()
                if row and row[0]:
                    starting_head_sha = str(row[0])

        index_mode = "full" if (full or not starting_head_sha) else "incremental"
        logger.info(f"Starting {index_mode} indexing for {repo_key} (HEAD: {head_sha[:8]})")

        # Record start in GITMIND_INDEX_RUNS
        with self.connection_manager.cursor() as cur:
            cur.execute(
                """
                INSERT INTO GITMIND_INDEX_RUNS
                    (RUN_ID, REPO_ID, INDEX_MODE, STARTING_HEAD_SHA, ENDING_HEAD_SHA,
                     INDEXED_ARTIFACTS, GENERATED_CHUNKS, FAILED_ARTIFACTS,
                     START_TIME, STATUS)
                VALUES (?, ?, ?, ?, ?, 0, 0, 0, ?, 'IN_PROGRESS')
                """,
                (run_id, repo_id, index_mode, starting_head_sha, head_sha, now),
            )

        artifacts_count = 0
        chunks_count = 0
        failed_count = 0
        error_summary = []

        try:
            # 1. Index Commits & Build Knowledge Graph
            c_arts, c_chunks, c_fails = self._index_commits(
                repo, repo_id, starting_head_sha, days if index_mode == "full" else 0
            )
            artifacts_count += c_arts
            chunks_count += c_chunks
            failed_count += c_fails

            # 2. Index Documentation
            d_arts, d_chunks, d_fails = self._index_documentation(repo, repo_id)
            artifacts_count += d_arts
            chunks_count += d_chunks
            failed_count += d_fails

            # 3. Index GitHub Data (if configured)
            if config.has_github_token():
                gh_arts, gh_chunks, gh_fails = self._index_github_data(repo_id, repo_path)
                artifacts_count += gh_arts
                chunks_count += gh_chunks
                failed_count += gh_fails

            # 4. Finalize Repository Record & Index Run
            comp_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            with self.connection_manager.cursor() as cur:
                cur.execute(
                    """
                    UPDATE GITMIND_REPOSITORIES
                    SET INDEXED_HEAD_SHA = ?, LAST_INDEXED_AT = ?, UPDATED_AT = ?
                    WHERE REPO_ID = ?
                    """,
                    (head_sha, comp_time, comp_time, repo_id),
                )
                cur.execute(
                    """
                    UPDATE GITMIND_INDEX_RUNS
                    SET INDEXED_ARTIFACTS = ?, GENERATED_CHUNKS = ?, FAILED_ARTIFACTS = ?,
                        COMPLETION_TIME = ?, STATUS = 'SUCCESS'
                    WHERE RUN_ID = ?
                    """,
                    (artifacts_count, chunks_count, failed_count, comp_time, run_id),
                )

            # Record audit event
            self._record_audit(
                repo_id,
                "INDEX_RUN_COMPLETED",
                "Indexer",
                {
                    "run_id": run_id,
                    "mode": index_mode,
                    "artifacts": artifacts_count,
                    "chunks": chunks_count,
                    "head": head_sha,
                },
            )

            return {
                "status": "SUCCESS",
                "mode": index_mode,
                "indexed_artifacts": artifacts_count,
                "generated_chunks": chunks_count,
                "failed_artifacts": failed_count,
                "head_sha": head_sha,
                "repo_id": repo_id,
            }

        except Exception as e:
            failed_msg = str(e)
            logger.exception(f"Indexing failed for run {run_id}: {failed_msg}")
            comp_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            with self.connection_manager.cursor() as cur:
                cur.execute(
                    """
                    UPDATE GITMIND_INDEX_RUNS
                    SET FAILED_ARTIFACTS = ?, COMPLETION_TIME = ?, STATUS = 'FAILED', ERROR_SUMMARY = ?
                    WHERE RUN_ID = ?
                    """,
                    (failed_count + 1, comp_time, failed_msg[:2000], run_id),
                )
            raise

    # -----------------------------------------------------------------------
    # Commit & Code Indexing Pipeline
    # -----------------------------------------------------------------------

    def _index_commits(
        self,
        repo: Repo,
        repo_id: str,
        starting_sha: Optional[str],
        days: int,
    ) -> Tuple[int, int, int]:
        """Index git commits, touched files, Tree-sitter symbols, and relations."""
        if starting_sha:
            try:
                commit_iter = list(repo.iter_commits(f"{starting_sha}..HEAD"))
            except Exception:
                commit_iter = list(repo.iter_commits(max_count=200))
        elif days > 0:
            commit_iter = list(repo.iter_commits(max_count=300))
        else:
            commit_iter = list(repo.iter_commits(max_count=200))

        artifacts_created = 0
        chunks_created = 0
        failed = 0

        vector_texts: List[str] = []
        vector_metas: List[Dict[str, Any]] = []
        vector_ids: List[str] = []

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        with self.connection_manager.connection() as conn:
            cur = conn.cursor()

            for commit in commit_iter:
                try:
                    c_sha = commit.hexsha
                    short_sha = commit.hexsha[:8]
                    message = redact_secrets(commit.message.strip())
                    author = commit.author.name or "Unknown"
                    c_date = commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S")
                    content_hash = hashlib.sha256(f"{c_sha}:{message}".encode()).hexdigest()

                    # 1. Insert Commit Artifact
                    c_artifact_id = hashlib.sha256(f"{repo_id}:commit:{c_sha}".encode()).hexdigest()[:16].upper()
                    cur.execute(
                        """
                        INSERT INTO GITMIND_ARTIFACTS
                            (ARTIFACT_ID, REPO_ID, ARTIFACT_TYPE, SOURCE_KEY, TITLE,
                             CONTENT, COMMIT_SHA, AUTHOR, CONTENT_HASH, CREATED_AT, UPDATED_AT)
                        VALUES (?, ?, 'commit', ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            c_artifact_id,
                            repo_id,
                            short_sha,
                            message.split("\n")[0][:500],
                            message,
                            c_sha,
                            author,
                            content_hash,
                            c_date,
                            now,
                        ),
                    )
                    artifacts_created += 1

                    # 2. Knowledge Graph: Parent Commits
                    for parent in commit.parents:
                        p_sha = parent.hexsha
                        p_artifact_id = hashlib.sha256(f"{repo_id}:commit:{p_sha}".encode()).hexdigest()[:16].upper()
                        # Ensure parent artifact shell exists
                        try:
                            cur.execute(
                                """
                                INSERT INTO GITMIND_ARTIFACTS
                                    (ARTIFACT_ID, REPO_ID, ARTIFACT_TYPE, SOURCE_KEY, TITLE,
                                     COMMIT_SHA, CONTENT_HASH, CREATED_AT, UPDATED_AT)
                                VALUES (?, ?, 'commit', ?, 'Parent commit', ?, ?, ?, ?)
                                """,
                                (p_artifact_id, repo_id, p_sha[:8], p_sha, p_sha, now, now),
                            )
                        except Exception:
                            pass

                        rel_id = hashlib.sha256(f"{repo_id}:{c_artifact_id}:{p_artifact_id}:COMMIT_PARENT".encode()).hexdigest()[:16].upper()
                        try:
                            cur.execute(
                                """
                                INSERT INTO GITMIND_RELATIONS
                                    (RELATION_ID, REPO_ID, SOURCE_ARTIFACT_ID, TARGET_ARTIFACT_ID,
                                     RELATION_TYPE, CREATED_AT)
                                VALUES (?, ?, ?, ?, 'COMMIT_PARENT', ?)
                                """,
                                (rel_id, repo_id, c_artifact_id, p_artifact_id, now),
                            )
                        except Exception:
                            pass

                    # 3. Touched Files & Tree-Sitter Symbols
                    diff_stats = commit.stats.files
                    for file_path in diff_stats.keys():
                        if not is_path_safe_for_indexing(file_path):
                            continue

                        f_art_id = hashlib.sha256(f"{repo_id}:file:{file_path}".encode()).hexdigest()[:16].upper()
                        # Upsert file artifact shell
                        try:
                            cur.execute(
                                """
                                INSERT INTO GITMIND_ARTIFACTS
                                    (ARTIFACT_ID, REPO_ID, ARTIFACT_TYPE, SOURCE_KEY, TITLE,
                                     FILE_PATH, CONTENT_HASH, CREATED_AT, UPDATED_AT)
                                VALUES (?, ?, 'file', ?, ?, ?, ?, ?, ?)
                                """,
                                (f_art_id, repo_id, file_path, file_path, file_path, f_art_id, now, now),
                            )
                            artifacts_created += 1
                        except Exception:
                            pass

                        # Relation: COMMIT_TOUCHES_FILE
                        rel_id = hashlib.sha256(f"{repo_id}:{c_artifact_id}:{f_art_id}:COMMIT_TOUCHES_FILE".encode()).hexdigest()[:16].upper()
                        try:
                            cur.execute(
                                """
                                INSERT INTO GITMIND_RELATIONS
                                    (RELATION_ID, REPO_ID, SOURCE_ARTIFACT_ID, TARGET_ARTIFACT_ID,
                                     RELATION_TYPE, CREATED_AT)
                                VALUES (?, ?, ?, ?, 'COMMIT_TOUCHES_FILE', ?)
                                """,
                                (rel_id, repo_id, c_artifact_id, f_art_id, now),
                            )
                        except Exception:
                            pass

                        # 4. Tree-Sitter AST Analysis on Changed Functions
                        lang = _detect_language(file_path)
                        if lang:
                            try:
                                # Read file blob at this commit
                                blob = commit.tree[file_path]
                                source_bytes = blob.data_stream.read()
                                definitions = _extract_definitions(source_bytes, lang)

                                for item in definitions:
                                    sym_name = item.get("name")
                                    sym_type = item.get("type", "function")
                                    start_line = item.get("start_line", 0)
                                    end_line = item.get("end_line", 0)

                                    if not sym_name or sym_name == "<anonymous>":
                                        continue

                                    sym_art_id = hashlib.sha256(
                                        f"{repo_id}:{sym_type}:{file_path}:{sym_name}:{start_line}".encode()
                                    ).hexdigest()[:16].upper()

                                    # Insert code symbol artifact
                                    try:
                                        cur.execute(
                                            """
                                            INSERT INTO GITMIND_ARTIFACTS
                                                (ARTIFACT_ID, REPO_ID, ARTIFACT_TYPE, SOURCE_KEY,
                                                 TITLE, FILE_PATH, COMMIT_SHA, START_LINE, END_LINE,
                                                 CONTENT_HASH, CREATED_AT, UPDATED_AT)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                            """,
                                            (
                                                sym_art_id,
                                                repo_id,
                                                sym_type,
                                                sym_name,
                                                f"{sym_type} {sym_name} in {file_path}",
                                                file_path,
                                                c_sha,
                                                start_line,
                                                end_line,
                                                sym_art_id,
                                                now,
                                                now,
                                            ),
                                        )
                                        artifacts_created += 1
                                    except Exception:
                                        pass

                                    # Relation: COMMIT_MODIFIES_FUNCTION
                                    rel_fn_id = hashlib.sha256(
                                        f"{repo_id}:{c_artifact_id}:{sym_art_id}:COMMIT_MODIFIES_FUNCTION".encode()
                                    ).hexdigest()[:16].upper()
                                    try:
                                        cur.execute(
                                            """
                                            INSERT INTO GITMIND_RELATIONS
                                                (RELATION_ID, REPO_ID, SOURCE_ARTIFACT_ID, TARGET_ARTIFACT_ID,
                                                 RELATION_TYPE, CREATED_AT)
                                            VALUES (?, ?, ?, ?, 'COMMIT_MODIFIES_FUNCTION', ?)
                                            """,
                                            (rel_fn_id, repo_id, c_artifact_id, sym_art_id, now),
                                        )
                                    except Exception:
                                        pass

                            except Exception:
                                pass

                    # Prepare Commit Vector Chunk
                    summary_text = (
                        f"Commit {short_sha} by {author} on {c_date}: {message}\n"
                        f"Changed files: {', '.join(list(diff_stats.keys())[:15])}"
                    )
                    vector_texts.append(summary_text)
                    vector_metas.append({
                        "type": "commit",
                        "hash": short_sha,
                        "commit_sha": c_sha,
                        "author": author,
                        "date": c_date,
                        "repo_id": repo_id,
                        "artifact_id": c_artifact_id,
                    })
                    vector_ids.append(f"{repo_id}:commit:{short_sha}")

                except Exception as err:
                    failed += 1
                    logger.warning(f"Error indexing commit {commit.hexsha[:8]}: {err}")

            conn.commit()
            cur.close()

        # Ingest vector chunks into Db2
        if vector_texts:
            try:
                self.vector_store.add_texts(
                    texts=vector_texts,
                    metadatas=vector_metas,
                    ids=vector_ids,
                    batch_size=50,
                )
                chunks_created += len(vector_texts)
            except Exception as e:
                logger.error(f"Vector ingestion error for commits: {e}")
                failed += len(vector_texts)

        return (artifacts_created, chunks_created, failed)

    # -----------------------------------------------------------------------
    # Documentation Indexing
    # -----------------------------------------------------------------------

    def _index_documentation(self, repo: Repo, repo_id: str) -> Tuple[int, int, int]:
        """Indexes README and docs markdown files chunked by section."""
        artifacts = 0
        chunks = 0
        failed = 0

        working_dir = Path(repo.working_dir)
        doc_files = list(working_dir.glob("*.md")) + list(working_dir.glob("docs/**/*.md"))

        vector_texts: List[str] = []
        vector_metas: List[Dict[str, Any]] = []
        vector_ids: List[str] = []

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        with self.connection_manager.cursor() as cur:
            for doc_file in doc_files:
                if not is_path_safe_for_indexing(str(doc_file)):
                    continue

                try:
                    rel_path = str(doc_file.relative_to(working_dir)).replace("\\", "/")
                    text = doc_file.read_text(encoding="utf-8", errors="replace")
                    text_redacted = redact_secrets(text)
                    c_hash = hashlib.sha256(text_redacted.encode()).hexdigest()

                    d_art_id = hashlib.sha256(f"{repo_id}:doc:{rel_path}".encode()).hexdigest()[:16].upper()
                    cur.execute(
                        """
                        INSERT INTO GITMIND_ARTIFACTS
                            (ARTIFACT_ID, REPO_ID, ARTIFACT_TYPE, SOURCE_KEY, TITLE,
                             CONTENT, FILE_PATH, CONTENT_HASH, CREATED_AT, UPDATED_AT)
                        VALUES (?, ?, 'doc', ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            d_art_id,
                            repo_id,
                            rel_path,
                            f"Documentation: {rel_path}",
                            text_redacted[:10000],
                            rel_path,
                            c_hash,
                            now,
                            now,
                        ),
                    )
                    artifacts += 1

                    # Section chunking on Markdown headings
                    sections = re.split(r"\n(?=#{1,3}\s)", text_redacted)
                    for idx, sec in enumerate(sections[:15]):
                        sec_clean = sec.strip()
                        if len(sec_clean) < 30:
                            continue

                        heading_match = re.match(r"^#{1,3}\s+(.+)", sec_clean)
                        sec_title = heading_match.group(1) if heading_match else f"Section {idx+1}"

                        chunk_text = f"Documentation ({rel_path} - {sec_title}):\n{sec_clean[:2000]}"
                        vector_texts.append(chunk_text)
                        vector_metas.append({
                            "type": "doc",
                            "file_path": rel_path,
                            "section": sec_title,
                            "repo_id": repo_id,
                            "artifact_id": d_art_id,
                        })
                        vector_ids.append(f"{repo_id}:doc:{rel_path}:{idx}")

                except Exception as ex:
                    failed += 1
                    logger.warning(f"Error indexing doc file {doc_file}: {ex}")

        if vector_texts:
            try:
                self.vector_store.add_texts(
                    texts=vector_texts,
                    metadatas=vector_metas,
                    ids=vector_ids,
                    batch_size=50,
                )
                chunks += len(vector_texts)
            except Exception as e:
                logger.error(f"Vector ingestion error for docs: {e}")
                failed += len(vector_texts)

        return (artifacts, chunks, failed)

    # -----------------------------------------------------------------------
    # GitHub PR & Issue Indexing
    # -----------------------------------------------------------------------

    def _index_github_data(self, repo_id: str, repo_path: str) -> Tuple[int, int, int]:
        """Indexes GitHub pull requests and issues, connecting PR -> issue -> commits."""
        artifacts = 0
        chunks = 0
        failed = 0

        try:
            from github_integration.github_client import GitHubClient
            client = GitHubClient(token=config.GITHUB_TOKEN, repo_path=repo_path)
            prs = client.get_prs(limit=50)
            issues = client.get_issues(limit=50)
        except Exception as e:
            logger.warning(f"GitHub client initialization failed: {e}")
            return (0, 0, 0)

        vector_texts: List[str] = []
        vector_metas: List[Dict[str, Any]] = []
        vector_ids: List[str] = []

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        with self.connection_manager.cursor() as cur:
            # PR Indexing
            for pr in prs:
                try:
                    num = pr.get("number")
                    title = redact_secrets(pr.get("title", ""))
                    body = redact_secrets(pr.get("body", "") or "")
                    author = pr.get("author", "unknown")
                    state = pr.get("state", "open")
                    c_hash = hashlib.sha256(f"pr:{num}:{title}".encode()).hexdigest()

                    pr_art_id = hashlib.sha256(f"{repo_id}:pr:{num}".encode()).hexdigest()[:16].upper()
                    cur.execute(
                        """
                        INSERT INTO GITMIND_ARTIFACTS
                            (ARTIFACT_ID, REPO_ID, ARTIFACT_TYPE, SOURCE_KEY, TITLE,
                             CONTENT, AUTHOR, SOURCE_URL, CONTENT_HASH, CREATED_AT, UPDATED_AT)
                        VALUES (?, ?, 'pr', ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            pr_art_id,
                            repo_id,
                            str(num),
                            f"PR #{num}: {title}",
                            body[:8000],
                            author,
                            f"https://github.com/pull/{num}",
                            c_hash,
                            now,
                            now,
                        ),
                    )
                    artifacts += 1

                    chunk_text = f"GitHub PR #{num} by {author} ({state}): {title}\nDescription: {body[:1000]}"
                    vector_texts.append(chunk_text)
                    vector_metas.append({
                        "type": "pr",
                        "number": str(num),
                        "author": author,
                        "state": state,
                        "repo_id": repo_id,
                        "artifact_id": pr_art_id,
                    })
                    vector_ids.append(f"{repo_id}:pr:{num}")

                except Exception as ex:
                    failed += 1
                    logger.warning(f"Error indexing PR {pr.get('number')}: {ex}")

            # Issue Indexing
            for issue in issues:
                try:
                    num = issue.get("number")
                    title = redact_secrets(issue.get("title", ""))
                    body = redact_secrets(issue.get("body", "") or "")
                    author = issue.get("author", "unknown")
                    state = issue.get("state", "open")
                    c_hash = hashlib.sha256(f"issue:{num}:{title}".encode()).hexdigest()

                    iss_art_id = hashlib.sha256(f"{repo_id}:issue:{num}".encode()).hexdigest()[:16].upper()
                    cur.execute(
                        """
                        INSERT INTO GITMIND_ARTIFACTS
                            (ARTIFACT_ID, REPO_ID, ARTIFACT_TYPE, SOURCE_KEY, TITLE,
                             CONTENT, AUTHOR, SOURCE_URL, CONTENT_HASH, CREATED_AT, UPDATED_AT)
                        VALUES (?, ?, 'issue', ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            iss_art_id,
                            repo_id,
                            str(num),
                            f"Issue #{num}: {title}",
                            body[:8000],
                            author,
                            f"https://github.com/issues/{num}",
                            c_hash,
                            now,
                            now,
                        ),
                    )
                    artifacts += 1

                    chunk_text = f"GitHub Issue #{num} by {author} ({state}): {title}\nDescription: {body[:1000]}"
                    vector_texts.append(chunk_text)
                    vector_metas.append({
                        "type": "issue",
                        "number": str(num),
                        "author": author,
                        "state": state,
                        "repo_id": repo_id,
                        "artifact_id": iss_art_id,
                    })
                    vector_ids.append(f"{repo_id}:issue:{num}")

                except Exception as ex:
                    failed += 1
                    logger.warning(f"Error indexing issue {issue.get('number')}: {ex}")

        if vector_texts:
            try:
                self.vector_store.add_texts(
                    texts=vector_texts,
                    metadatas=vector_metas,
                    ids=vector_ids,
                    batch_size=50,
                )
                chunks += len(vector_texts)
            except Exception as e:
                logger.error(f"Vector ingestion error for GitHub data: {e}")
                failed += len(vector_texts)

        return (artifacts, chunks, failed)

    def _record_audit(self, repo_id: str, event_type: str, actor: str, details: dict) -> None:
        """Helper to record audit log."""
        try:
            event_id = str(uuid.uuid4())[:16].upper()
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            with self.connection_manager.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO GITMIND_AUDIT_EVENTS
                        (EVENT_ID, REPO_ID, EVENT_TYPE, ACTOR, DETAILS, CREATED_AT)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (event_id, repo_id, event_type, actor, json.dumps(details), now),
                )
        except Exception:
            pass


# Singleton indexer
_global_indexer: Optional[RepositoryIndexer] = None


def get_repository_indexer() -> RepositoryIndexer:
    """Retrieve singleton RepositoryIndexer."""
    global _global_indexer
    if _global_indexer is None:
        _global_indexer = RepositoryIndexer()
    return _global_indexer

