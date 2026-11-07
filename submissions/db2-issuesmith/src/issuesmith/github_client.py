"""GitHub helpers: search existing issues (dedupe) and create an issue after human approval."""
from __future__ import annotations

import logging
import re

import requests

log = logging.getLogger(__name__)
API = "https://api.github.com"
_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "when", "is", "x", "n", "path"}


def keywords_from(text: str, limit: int = 5) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.lower())
    out: list[str] = []
    for w in words:
        if w not in _STOP and w not in out:
            out.append(w)
        if len(out) == limit:
            break
    return out


def search_issues(repo: str, terms: list[str], token: str = "", limit: int = 5) -> list[dict]:
    """Best-effort: returns [] on any network/rate-limit problem so the pipeline never breaks."""
    if not repo or not terms:
        return []
    q = " ".join(terms) + f" repo:{repo} is:issue"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(f"{API}/search/issues", params={"q": q, "per_page": limit}, headers=headers, timeout=15)
        r.raise_for_status()
        return [
            {"number": i["number"], "title": i["title"], "state": i["state"], "url": i["html_url"]}
            for i in r.json().get("items", [])
        ]
    except Exception as exc:
        log.info("GitHub search skipped: %s", exc)
        return []


def create_issue(repo: str, token: str, title: str, body: str) -> str:
    if not token or not repo:
        raise ValueError("Set GITHUB_TOKEN and GITHUB_TARGET_REPO in .env to post issues.")
    r = requests.post(
        f"{API}/repos/{repo}/issues",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        json={"title": title, "body": body},
        timeout=20,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"GitHub returned {r.status_code}: {r.text[:300]}")
    return r.json()["html_url"]
