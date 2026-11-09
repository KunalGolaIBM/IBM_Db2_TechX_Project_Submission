"""
GitMind — SQLite Data Layer

Caches structured repository data (commits, branches, PRs, issues)
for fast repeated access without re-querying git or GitHub APIs.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import DB_PATH


class GitMindDB:
    """SQLite database for caching repository metadata."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or DB_PATH)
        self._init_tables()

    @contextmanager
    def _connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_tables(self):
        """Create tables if they don't exist."""
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS commits (
                    hash TEXT PRIMARY KEY,
                    full_hash TEXT,
                    message TEXT NOT NULL,
                    author TEXT NOT NULL,
                    author_email TEXT DEFAULT '',
                    date TEXT NOT NULL,
                    files_changed TEXT DEFAULT '[]',
                    insertions INTEGER DEFAULT 0,
                    deletions INTEGER DEFAULT 0,
                    repo_path TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS branches (
                    name TEXT NOT NULL,
                    is_current INTEGER DEFAULT 0,
                    tracking TEXT,
                    ahead INTEGER DEFAULT 0,
                    behind INTEGER DEFAULT 0,
                    last_commit_hash TEXT,
                    repo_path TEXT NOT NULL,
                    PRIMARY KEY (name, repo_path)
                );

                CREATE TABLE IF NOT EXISTS tags (
                    name TEXT NOT NULL,
                    commit_hash TEXT NOT NULL,
                    date TEXT,
                    message TEXT,
                    repo_path TEXT NOT NULL,
                    PRIMARY KEY (name, repo_path)
                );

                CREATE TABLE IF NOT EXISTS pull_requests (
                    number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT,
                    state TEXT NOT NULL,
                    author TEXT NOT NULL,
                    created_at TEXT,
                    merged_at TEXT,
                    base_branch TEXT DEFAULT '',
                    head_branch TEXT DEFAULT '',
                    labels TEXT DEFAULT '[]',
                    repo_path TEXT NOT NULL,
                    PRIMARY KEY (number, repo_path)
                );

                CREATE TABLE IF NOT EXISTS issues (
                    number INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT,
                    state TEXT NOT NULL,
                    author TEXT NOT NULL,
                    created_at TEXT,
                    closed_at TEXT,
                    labels TEXT DEFAULT '[]',
                    assignees TEXT DEFAULT '[]',
                    repo_path TEXT NOT NULL,
                    PRIMARY KEY (number, repo_path)
                );

                CREATE TABLE IF NOT EXISTS comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_type TEXT NOT NULL,
                    parent_number INTEGER NOT NULL,
                    author TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT,
                    repo_path TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_commits_repo
                    ON commits(repo_path);
                CREATE INDEX IF NOT EXISTS idx_commits_date
                    ON commits(date);
                CREATE INDEX IF NOT EXISTS idx_commits_author
                    ON commits(author);
            """)

    #commit operations

    def upsert_commit(self, repo_path: str, **kwargs):
        """Insert or update a commit record."""
        import json

        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO commits
                    (hash, full_hash, message, author, author_email,
                     date, files_changed, insertions, deletions, repo_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    kwargs["hash"],
                    kwargs.get("full_hash", ""),
                    kwargs["message"],
                    kwargs["author"],
                    kwargs.get("author_email", ""),
                    str(kwargs["date"]),
                    json.dumps(kwargs.get("files_changed", [])),
                    kwargs.get("insertions", 0),
                    kwargs.get("deletions", 0),
                    repo_path,
                ),
            )

    def get_commits(self, repo_path: str, limit: int = 100) -> list[dict]:
        """Retrieve cached commits for a repo."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM commits WHERE repo_path = ? ORDER BY date DESC LIMIT ?",
                (repo_path, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    # pr operations

    def upsert_pr(self, repo_path: str, **kwargs):
        """Insert or update a pull request record."""
        import json

        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO pull_requests
                    (number, title, body, state, author,
                     created_at, merged_at, base_branch, head_branch,
                     labels, repo_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    kwargs["number"],
                    kwargs["title"],
                    kwargs.get("body"),
                    kwargs["state"],
                    kwargs["author"],
                    str(kwargs.get("created_at", "")),
                    str(kwargs.get("merged_at", "")),
                    kwargs.get("base_branch", ""),
                    kwargs.get("head_branch", ""),
                    json.dumps(kwargs.get("labels", [])),
                    repo_path,
                ),
            )

    def get_prs(self, repo_path: str, state: str = "all") -> list[dict]:
        """Retrieve cached PRs."""
        with self._connection() as conn:
            if state == "all":
                rows = conn.execute(
                    "SELECT * FROM pull_requests WHERE repo_path = ? ORDER BY number DESC",
                    (repo_path,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM pull_requests WHERE repo_path = ? AND state = ? ORDER BY number DESC",
                    (repo_path, state),
                ).fetchall()
            return [dict(row) for row in rows]

    # issue operations
    def upsert_issue(self, repo_path: str, **kwargs):
        """Insert or update an issue record."""
        import json

        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO issues
                    (number, title, body, state, author,
                     created_at, closed_at, labels, assignees, repo_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    kwargs["number"],
                    kwargs["title"],
                    kwargs.get("body"),
                    kwargs["state"],
                    kwargs["author"],
                    str(kwargs.get("created_at", "")),
                    str(kwargs.get("closed_at", "")),
                    json.dumps(kwargs.get("labels", [])),
                    json.dumps(kwargs.get("assignees", [])),
                    repo_path,
                ),
            )

    def get_issues(self, repo_path: str, state: str = "all") -> list[dict]:
        """Retrieve cached issues."""
        with self._connection() as conn:
            if state == "all":
                rows = conn.execute(
                    "SELECT * FROM issues WHERE repo_path = ? ORDER BY number DESC",
                    (repo_path,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM issues WHERE repo_path = ? AND state = ? ORDER BY number DESC",
                    (repo_path, state),
                ).fetchall()
            return [dict(row) for row in rows]

    # utility

    def clear_repo(self, repo_path: str):
        """Remove all cached data for a specific repo."""
        with self._connection() as conn:
            for table in ["commits", "branches", "tags", "pull_requests", "issues", "comments"]:
                conn.execute(f"DELETE FROM {table} WHERE repo_path = ?", (repo_path,))
