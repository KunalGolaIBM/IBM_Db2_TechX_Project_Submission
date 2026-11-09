"""
GitMind — GitHub LangChain Tools

LangChain-compatible tools wrapping GitHubClient methods,
allowing LangGraph agents to query PRs, issues, reviews,
and perform commit → PR → issue tracing.
"""

from __future__ import annotations

from typing import Optional

from langchain.tools import tool

from config import GITHUB_TOKEN, has_github_token
from github_integration.github_client import GitHubClient

_client: Optional[GitHubClient] = None


def _get_client(repo_path: str = ".") -> GitHubClient:
    """Get or create a GitHub client."""
    global _client
    if _client is None:
        if not has_github_token():
            raise RuntimeError(
                "GitHub features require a GITHUB_TOKEN in your .env file. "
                "Create one at https://github.com/settings/tokens"
            )
        _client = GitHubClient(token=GITHUB_TOKEN, repo_path=repo_path)
    return _client


@tool
def search_prs(query: str, repo_path: str = ".") -> str:
    """
    Search pull requests by text query. Returns matching PRs
    with number, title, state, and author.
    """
    try:
        client = _get_client(repo_path)
        results = client.search_prs(query)
        return str(results) if results else "No matching pull requests found."
    except RuntimeError as e:
        return str(e)


@tool
def get_pr_context(pr_number: int, repo_path: str = ".") -> str:
    """
    Get full context for a pull request: details, reviews, and comments.
    Provides the human intent behind code changes.
    """
    try:
        client = _get_client(repo_path)
        details = client.get_pr_details(pr_number)
        reviews = client.get_pr_reviews(pr_number)
        comments = client.get_pr_comments(pr_number)

        return str({
            "pr": details,
            "reviews": reviews,
            "comments": comments,
        })
    except RuntimeError as e:
        return str(e)


@tool
def search_issues(query: str, repo_path: str = ".") -> str:
    """
    Search issues by text query. Returns matching issues
    with number, title, state, and author.
    """
    try:
        client = _get_client(repo_path)
        results = client.search_issues(query)
        return str(results) if results else "No matching issues found."
    except RuntimeError as e:
        return str(e)


@tool
def get_issue_context(issue_number: int, repo_path: str = ".") -> str:
    """
    Get full context for an issue: details and all comments.
    Provides the problem description and discussion history.
    """
    try:
        client = _get_client(repo_path)
        return str(client.get_issue_details(issue_number))
    except RuntimeError as e:
        return str(e)


@tool
def find_pr_for_commit(commit_hash: str, repo_path: str = ".") -> str:
    """
    Given a commit SHA, find the pull request(s) that introduced it.
    Useful for tracing: commit → PR → understanding why a change was made.
    """
    try:
        client = _get_client(repo_path)
        prs = client.find_pr_for_commit(commit_hash)
        if not prs:
            return f"No pull request found for commit {commit_hash}"
        return str(prs)
    except RuntimeError as e:
        return str(e)


@tool
def find_issues_for_pr(pr_number: int, repo_path: str = ".") -> str:
    """
    Given a PR number, find linked issues by scanning the PR body
    and commit messages for issue references (#NNN, closes #NNN, etc.).
    Useful for tracing: PR → issue → understanding the problem.
    """
    try:
        client = _get_client(repo_path)
        issues = client.find_issues_for_pr(pr_number)
        if not issues:
            return f"No linked issues found for PR #{pr_number}"
        return str(issues)
    except RuntimeError as e:
        return str(e)


@tool
def get_github_prs(state: str = "all", repo_path: str = ".") -> str:
    """
    List recent pull requests. State can be 'open', 'closed', or 'all'.
    """
    try:
        client = _get_client(repo_path)
        prs = client.get_prs(state=state)
        return str(prs) if prs else "No pull requests found."
    except RuntimeError as e:
        return str(e)


@tool
def get_github_issues(state: str = "all", repo_path: str = ".") -> str:
    """
    List recent issues (excluding PRs). State can be 'open', 'closed', or 'all'.
    """
    try:
        client = _get_client(repo_path)
        issues = client.get_issues(state=state)
        return str(issues) if issues else "No issues found."
    except RuntimeError as e:
        return str(e)

#  TOOL REGISTRY

GITHUB_TOOLS = [
    search_prs,
    get_pr_context,
    search_issues,
    get_issue_context,
    find_pr_for_commit,
    find_issues_for_pr,
    get_github_prs,
    get_github_issues,
]
