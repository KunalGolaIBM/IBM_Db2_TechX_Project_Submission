"""
GitMind — GitHub Client

Wrapper around PyGithub for accessing PRs, issues, reviews,
comments, and discussions. Auto-detects the GitHub remote URL
from the local git repository configuration.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from itertools import islice
from git import Repo


class GitHubClient:
    """
    High-level GitHub API client that auto-discovers the repo
    from a local git checkout.
    """

    def __init__(self, token: str, repo_path: str = "."):
        from github import Github, GithubException

        self._gh = Github(token)
        self._repo_path = repo_path
        self._github_repo = None
        self._GithubException = GithubException

        owner_repo = self._detect_github_repo()
        if owner_repo:
            try:
                self._github_repo = self._gh.get_repo(owner_repo)
            except GithubException:
                self._github_repo = None

    def _detect_github_repo(self) -> Optional[str]:
        """
        Extract owner/repo from the git remote URL.
        Handles HTTPS and SSH formats:
          - https://github.com/owner/repo.git
          - git@github.com:owner/repo.git
        """
        try:
            repo = Repo(Path(self._repo_path).resolve(), search_parent_directories=True)
        except Exception:
            return None

        for remote in repo.remotes:
            url = remote.url

            # SSH format
            match = re.search(r"github\.com[:/]([^/]+/[^/.]+?)(?:\.git)?$", url)
            if match:
                return match.group(1)

        return None

    @property
    def is_connected(self) -> bool:
        """Check if we successfully connected to a GitHub repo."""
        return self._github_repo is not None

    @property
    def repo_full_name(self) -> str:
        return self._github_repo.full_name if self._github_repo else "unknown"

    # Pull Requests, get prs

    def get_prs(self, state: str = "all", limit: int = 30) -> list[dict]:
        """Get pull requests."""
        if not self._github_repo:
            return []

        prs = []
        for pr in islice(self._github_repo.get_pulls(state=state, sort="updated"),limit):
            prs.append({
                "number": pr.number,
                "title": pr.title,
                "state": pr.state,
                "author": pr.user.login,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
                "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                "base": pr.base.ref,
                "head": pr.head.ref,
                "labels": [l.name for l in pr.labels],
                "review_comments": pr.review_comments,
            })
        # print(f"The PRs from github/github_client.py are: {prs}")
        return prs

# Get pr details
    def get_pr_details(self, pr_number: int) -> dict:
        """Get detailed PR info including body."""
        if not self._github_repo:
            return {"error": "Not connected to GitHub"}

        try:
            pr = self._github_repo.get_pull(pr_number)
            # print(f"The PR details from github/github_client.py are: {pr}")
            return {
                "number": pr.number,
                "title": pr.title,
                "body": (pr.body or "")[:2000],
                "state": pr.state,
                "author": pr.user.login,
                "created_at": pr.created_at.isoformat() if pr.created_at else None,
                "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                "merged_by": pr.merged_by.login if pr.merged_by else None,
                "base": pr.base.ref,
                "head": pr.head.ref,
                "labels": [l.name for l in pr.labels],
                "additions": pr.additions,
                "deletions": pr.deletions,
                "changed_files": pr.changed_files,
                "commits": pr.commits,
                "review_comments": pr.review_comments,
            }
        except self._GithubException as e:
            return {"error": str(e)}

# Get pr reviews
    def get_pr_reviews(self, pr_number: int) -> list[dict]:
        """Get reviews for a PR."""
        if not self._github_repo:
            return []

        try:
            pr = self._github_repo.get_pull(pr_number)
            reviews = []
            for review in pr.get_reviews():
                reviews.append({
                    "author": review.user.login,
                    "state": review.state,
                    "body": (review.body or "")[:500],
                    "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None,
                })
            # print(f"The PR reviews from github/github_client.py are: {reviews}")
            return reviews
        except self._GithubException:
            return []

# Get pr comments
    def get_pr_comments(self, pr_number: int) -> list[dict]:
        """Get comments on a PR."""
        if not self._github_repo:
            return []

        try:
            pr = self._github_repo.get_pull(pr_number)
            comments = []
            for comment in pr.get_issue_comments():
                comments.append({
                    "author": comment.user.login,
                    "body": (comment.body or "")[:500],
                    "created_at": comment.created_at.isoformat() if comment.created_at else None,
                })
            # print(f"The PR comments from github/github_client.py are: {comments}")
            return comments
        except self._GithubException:
            return []

    # Issues, get issues

    def get_issues(self, state: str = "all", limit: int = 30) -> list[dict]:
        """Get issues (excluding PRs)."""
        if not self._github_repo:
            return []

        issues = []
        for issue in islice(self._github_repo.get_issues(state=state, sort="updated"),limit):
            if issue.pull_request:
                continue  # Skip PRs listed as issues
            issues.append({
                "number": issue.number,
                "title": issue.title,
                "state": issue.state,
                "author": issue.user.login,
                "created_at": issue.created_at.isoformat() if issue.created_at else None,
                "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                "labels": [l.name for l in issue.labels],
                "assignees": [a.login for a in issue.assignees],
            })
        # print(f"The issues from github/github_client.py are: {issues}")
        return issues

# Get issue details
    def get_issue_details(self, issue_number: int) -> dict:
        """Get detailed issue info including body and comments."""
        if not self._github_repo:
            return {"error": "Not connected to GitHub"}

        try:
            issue = self._github_repo.get_issue(issue_number)
            comments = []
            for comment in issue.get_comments()[:20]:
                comments.append({
                    "author": comment.user.login,
                    "body": (comment.body or "")[:500],
                    "created_at": comment.created_at.isoformat() if comment.created_at else None,
                })
            # print(f"The issue details from github/github_client.py are: {comments}")
            return {
                "number": issue.number,
                "title": issue.title,
                "body": (issue.body or "")[:2000],
                "state": issue.state,
                "author": issue.user.login,
                "created_at": issue.created_at.isoformat() if issue.created_at else None,
                "closed_at": issue.closed_at.isoformat() if issue.closed_at else None,
                "labels": [l.name for l in issue.labels],
                "assignees": [a.login for a in issue.assignees],
                "comments": comments,
            }
        except self._GithubException as e:
            return {"error": str(e)}

    # Commit -> PR -> Issue Tracing, find pr for commit

    def find_pr_for_commit(self, commit_hash: str) -> list[dict]:
        """Find PRs associated with a commit SHA."""
        if not self._github_repo:
            return []

        try:
            commit = self._github_repo.get_commit(commit_hash)
            prs = commit.get_pulls()
            # print(f"The PRs for commit from github/github_client.py are: {prs}")
            return [
                {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state,
                    "author": pr.user.login,
                }
                for pr in prs
            ]
        except self._GithubException:
            return []

# find issues for pr
    def find_issues_for_pr(self, pr_number: int) -> list[dict]:
        """
        Find issues linked to a PR by scanning the PR body and
        commit messages for issue references (#NNN, closes #NNN, etc.).
        """
        if not self._github_repo:
            return []

        try:
            pr = self._github_repo.get_pull(pr_number)
            text = f"{pr.title} {pr.body or ''}"

            # Also scan commit messages
            for commit in pr.get_commits():
                text += f" {commit.commit.message}"

            # Find issue references
            issue_numbers = set(re.findall(r"#(\d+)", text))
            issues = []
            for num_str in issue_numbers:
                num = int(num_str)
                if num == pr_number:
                    continue
                try:
                    issue = self._github_repo.get_issue(num)
                    if not issue.pull_request:
                        issues.append({
                            "number": issue.number,
                            "title": issue.title,
                            "state": issue.state,
                        })
                except self._GithubException:
                    continue

            # print(f"The issues for PR from github/github_client.py are: {issues}")
            return issues
        except self._GithubException:
            return []

# Search prs

    def search_prs(self, query: str, limit: int = 10) -> list[dict]:
        """Search PRs by text query."""
        if not self._github_repo:
            return []

        try:
            results = self._gh.search_issues(
                f"{query} repo:{self.repo_full_name} is:pr",
            )
            prs = []
            for issue in results[:limit]:
                prs.append({
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "author": issue.user.login,
                })
            # print(f"The PRs for search_prs from github/github_client.py are: {prs}")
            return prs
        except self._GithubException:
            return []

# search issues
    def search_issues(self, query: str, limit: int = 10) -> list[dict]:
        """Search issues by text query."""
        if not self._github_repo:
            return []

        try:
            results = self._gh.search_issues(
                f"{query} repo:{self.repo_full_name} is:issue",
            )
            issues = []
            for issue in results[:limit]:
                issues.append({
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "author": issue.user.login,
                })
            # print(f"The issues for search_issues from github/github_client.py are: {issues}")
            return issues
        except self._GithubException:
            return []
