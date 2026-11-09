"""
GitMind 2.0 — Repository Identification and Path Utilities

Provides stable, cross-environment repository identification:
- Invariant across clones, machines, and directory locations
- Canonical remote URL normalization (SSH, HTTPS, git://)
- Initial commit root hash fallback for un-pushed / local repositories
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional

from git import Repo, InvalidGitRepositoryError


def get_repo(repo_path: str = ".") -> Repo:
    """Helper: open git repo from path or parents."""
    try:
        return Repo(Path(repo_path).resolve(), search_parent_directories=True)
    except InvalidGitRepositoryError:
        raise ValueError(f"'{repo_path}' is not inside a Git repository.")


def get_repo_remote_url(repo_path: str = ".") -> Optional[str]:
    """Retrieve the primary remote URL (origin or first remote)."""
    try:
        repo = get_repo(repo_path)
        if repo.remotes:
            return repo.remotes.origin.url if "origin" in repo.remotes else repo.remotes[0].url
    except Exception:
        pass
    return None


def normalize_remote_url(url: str) -> str:
    """
    Normalizes Git remote URLs to a canonical form:
    git@github.com:foo/bar.git -> github.com/foo/bar
    https://github.com/foo/bar.git -> github.com/foo/bar
    """
    clean = url.strip()
    clean = re.sub(r"^git@[^:]+:", "github.com/", clean)
    clean = re.sub(r"^https?://", "", clean)
    clean = re.sub(r"\.git$", "", clean)
    return clean.strip("/")


def get_repo_key(repo_path: str = ".") -> str:
    """
    Returns a human-readable, stable key for the repository.
    e.g. 'vastavikadi/gitmind' or directory name.
    """
    remote_url = get_repo_remote_url(repo_path)
    if remote_url:
        norm = normalize_remote_url(remote_url)
        # return owner/repo if possible
        parts = norm.split("/")
        if len(parts) >= 2:
            return "/".join(parts[-2:])
        return norm

    try:
        repo = get_repo(repo_path)
        return Path(repo.working_dir).name
    except Exception:
        return Path(repo_path).resolve().name


def get_repo_id(repo_path: str = ".") -> str:
    """
    Returns a deterministic, 16-character SHA-256 identifier for the repository.
    Prioritizes:
    1. Canonical remote URL (e.g. github.com/vastavikadi/gitmind)
    2. Initial commit root hash (invariant across branches & clones)
    3. Normalized repo key
    """
    remote_url = get_repo_remote_url(repo_path)
    if remote_url:
        canonical = normalize_remote_url(remote_url).lower()
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16].upper()

    try:
        repo = get_repo(repo_path)
        # Root commit is invariant
        root_commits = list(repo.iter_commits(rev=None, max_parents=0))
        if root_commits:
            root_sha = root_commits[0].hexsha
            return hashlib.sha256(root_sha.encode("utf-8")).hexdigest()[:16].upper()
    except Exception:
        pass

    key = get_repo_key(repo_path).lower()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16].upper()


def get_head_sha(repo_path: str = ".") -> str:
    """Get the current HEAD commit hash."""
    repo = get_repo(repo_path)
    return repo.head.commit.hexsha

