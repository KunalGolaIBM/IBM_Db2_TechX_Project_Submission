"""The documents judges read: every relative link points at a file in this folder, and every #anchor at a heading.

GitHub turns a heading into an anchor by lower-casing it, dropping punctuation other than hyphens and spaces, and
turning spaces into hyphens; repeated headings get -1, -2. Links to other sites are not fetched.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = sorted({ROOT / "README.md", ROOT / "architecture.md", *(ROOT / "docs").glob("*.md")})
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|!\[[^\]]*\]\(([^)\s]+)\)")


def anchors(text: str) -> set[str]:
    seen: dict[str, int] = {}
    out = set()
    in_code = False
    for line in text.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"^#{1,6}\s+(.*?)\s*#*$", line)
        if not m:
            continue
        title = re.sub(r"`([^`]*)`", r"\1", m.group(1))
        title = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", title)
        slug = re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")
        n = seen.get(slug, 0)
        out.add(slug if n == 0 else f"{slug}-{n}")
        seen[slug] = n + 1
    return out


def links(text: str) -> list[str]:
    text = re.sub(r"(?ms)^```.*?^```", "", text)  # code blocks are not links
    return [a or b for a, b in LINK.findall(text)]


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: str(p.relative_to(ROOT)))
def test_every_relative_link_and_anchor_resolves(doc):
    broken = []
    for target in links(doc.read_text(encoding="utf-8")):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target):  # https:, mailto: and the like
            continue
        path, _, anchor = target.partition("#")
        dest = (doc.parent / path).resolve() if path else doc
        if not dest.exists():
            broken.append(target)
        elif anchor and dest.suffix == ".md" and anchor not in anchors(dest.read_text(encoding="utf-8")):
            broken.append(target)
    assert broken == []


def test_every_api_route_is_in_the_readme():
    """The README's endpoint table names every route the API serves (path parameters written as {id}), each as the
    whole path inside a code span, so /api/ledger does not count for /api/ledger/{id}."""
    api = (ROOT / "src" / "asof" / "api.py").read_text(encoding="utf-8")
    readme = re.sub(r"\{[a-z_]+\}", "{id}", (ROOT / "README.md").read_text(encoding="utf-8"))
    routes = [re.sub(r"\{[a-z_]+\}", "{id}", p) for p in re.findall(r'@app\.(?:get|post|put|delete)\("(/[^"]*)"', api)
              if p.startswith(("/api/", "/healthz"))]
    assert len(routes) > 30
    assert [p for p in routes if not re.search(rf"(GET|POST|PUT|DELETE) {re.escape(p)}[`?]", readme)] == []
