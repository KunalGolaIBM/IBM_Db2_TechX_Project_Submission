"""
GitMind — Pydantic Data Models

Structured representations for commits, authors, branches,
pull requests, issues, and other repository metadata.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# NOTE: This segment is created by using AI

class CommitRecord(BaseModel):
    """A single git commit."""

    hash: str = Field(..., description="Short commit hash (7 chars)")
    full_hash: str = Field(default="", description="Full SHA-1 hash")
    message: str = Field(..., description="Commit message")
    author: str = Field(..., description="Author name")
    author_email: str = Field(default="", description="Author email")
    date: datetime = Field(..., description="Commit timestamp")
    files_changed: list[str] = Field(default_factory=list)
    insertions: int = Field(default=0)
    deletions: int = Field(default=0)


class FileChange(BaseModel):
    """A file change within a commit."""

    path: str
    action: str  # added, modified, deleted, renamed, copied
    old_path: Optional[str] = None


class BranchRecord(BaseModel):
    """A git branch."""

    name: str
    is_current: bool = False
    tracking: Optional[str] = None  # remote tracking branch
    ahead: int = 0
    behind: int = 0
    last_commit_hash: Optional[str] = None
    last_commit_date: Optional[datetime] = None


class TagRecord(BaseModel):
    """A git tag."""

    name: str
    commit_hash: str
    date: Optional[datetime] = None
    message: Optional[str] = None


class ReflogEntry(BaseModel):
    """A single reflog entry."""

    index: int
    hash: str
    action: str  # commit, checkout, rebase, reset, merge, etc.
    description: str
    timestamp: Optional[datetime] = None


class StashEntry(BaseModel):
    """A single stash entry."""

    index: int
    branch: str
    message: str
    hash: Optional[str] = None


class RepoStatus(BaseModel):
    """Current repository status."""

    branch: str
    is_detached: bool = False
    staged: list[str] = Field(default_factory=list)
    modified: list[str] = Field(default_factory=list)
    untracked: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    is_merging: bool = False
    is_rebasing: bool = False
    is_cherry_picking: bool = False


class PRRecord(BaseModel):
    """A GitHub Pull Request."""

    number: int
    title: str
    body: Optional[str] = None
    state: str  # open, closed, merged
    author: str
    created_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    base_branch: str = ""
    head_branch: str = ""
    labels: list[str] = Field(default_factory=list)
    review_comments: int = 0


class IssueRecord(BaseModel):
    """A GitHub Issue."""

    number: int
    title: str
    body: Optional[str] = None
    state: str  # open, closed
    author: str
    created_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)


class ReviewRecord(BaseModel):
    """A GitHub Pull Request Review."""

    pr_number: int
    author: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED
    body: Optional[str] = None
    submitted_at: Optional[datetime] = None


class FunctionInfo(BaseModel):
    """A function/method extracted from AST analysis."""

    name: str
    file_path: str
    start_line: int
    end_line: int
    language: str
    parameters: list[str] = Field(default_factory=list)
    decorators: list[str] = Field(default_factory=list)
    docstring: Optional[str] = None


class DanglingObject(BaseModel):
    """A dangling git object (from git fsck)."""

    object_type: str  # commit, blob, tree
    hash: str
    description: Optional[str] = None
