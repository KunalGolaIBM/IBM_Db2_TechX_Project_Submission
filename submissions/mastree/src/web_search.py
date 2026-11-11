"""
Open-internet search and article text extraction for MasteryLoop (mastree).
Fetches diverse tutorials, documentation, and technical articles across the web
via DuckDuckGo (`ddgs`), Hacker News Algolia, StackExchange API, and OpenAlex
open-access works, with clean HTML/PDF extraction and zero Wikipedia lock-in.
"""

import io
import re
import html
import hashlib
import logging
from urllib.parse import urlparse
from html.parser import HTMLParser
from typing import Dict, List, Tuple
import requests

logger = logging.getLogger("mastree.web_search")

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 MasteryLoop/2.5"
}


class _ArticleHTMLParser(HTMLParser):
    """Lightweight HTML-to-text extractor skipping boilerplate tags and preferring <main>/<article>."""

    SKIP_TAGS = {"script", "style", "noscript", "nav", "header", "footer", "aside", "svg", "form", "button", "iframe"}
    BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "li", "pre", "blockquote", "tr", "section", "div"}

    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.in_main = 0
        self.all_parts: List[str] = []
        self.main_parts: List[str] = []
        self.page_title: str = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1
            return
        if tag in ("main", "article"):
            self.in_main += 1
        elif tag == "br" and self.skip_depth == 0:
            self._append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP_TAGS:
            if self.skip_depth > 0:
                self.skip_depth -= 1
            return
        if tag in ("main", "article") and self.in_main > 0:
            self.in_main -= 1
        if tag in self.BLOCK_TAGS and self.skip_depth == 0:
            self._append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title and not self.page_title:
            self.page_title = " ".join(data.split()).strip()
        if self.skip_depth > 0:
            return
        cleaned = " ".join(data.split())
        if cleaned:
            self._append(cleaned + " ")

    def _append(self, token: str) -> None:
        self.all_parts.append(token)
        if self.in_main > 0:
            self.main_parts.append(token)

    def get_clean_text(self) -> str:
        raw_main = self._normalize("".join(self.main_parts))
        raw_all = self._normalize("".join(self.all_parts))
        return raw_main if len(raw_main.split()) >= 120 else raw_all

    @staticmethod
    def _normalize(text: str) -> str:
        lines = []
        seen = set()
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", html.unescape(raw_line)).strip()
            if not line:
                continue
            words = line.split()
            if len(words) < 4 and not line.endswith(":"):
                continue
            key = line.lower()
            if key in seen and len(words) < 12:
                continue
            seen.add(key)
            lines.append(line)
        return "\n\n".join(lines)


def _domain_label(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc or "web"
    except Exception:
        return "web"


def _strip_tags(raw_html: str) -> str:
    parser = _ArticleHTMLParser()
    parser.feed(raw_html or "")
    return parser.get_clean_text()


def search_internet(query: str, limit: int = 5, exclude_wikipedia: bool = True) -> List[Dict[str, str]]:
    """
    Search the open internet for diverse articles, tutorials, blogs, Q&A, and open-access papers.
    Excludes wikipedia.org by default when exclude_wikipedia=True.
    Returns [{id, title, snippet, source, url}].
    """
    query = query.strip()
    if not query:
        return []

    results: List[Dict[str, str]] = []
    seen_urls = set()

    def _add(title: str, snippet: str, url: str) -> bool:
        if not url or not title:
            return False
        if exclude_wikipedia and "wikipedia.org" in url.lower():
            return False
        if url in seen_urls:
            return False
        seen_urls.add(url)
        results.append({
            "id": hashlib.md5(url.encode("utf-8")).hexdigest()[:10],
            "title": html.unescape(title).strip(),
            "snippet": html.unescape(snippet).strip()[:280],
            "source": _domain_label(url),
            "url": url,
        })
        return len(results) >= limit

    # 1. Primary: DuckDuckGo meta-search (`ddgs`), querying without operators so engines don't 429/empty
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        raw_hits = DDGS().text(query, max_results=limit + 5)
        for hit in (raw_hits or []):
            url = (hit.get("href") or hit.get("url") or "").strip()
            title = (hit.get("title") or "").strip()
            snippet = (hit.get("body") or hit.get("snippet") or "").strip()
            if _add(title, snippet, url):
                return results
    except Exception as e:
        logger.warning(f"ddgs search fallback triggered ({e}); checking open web indexes.")

    # 2. Secondary: Hacker News Algolia (engineering blogs, tutorials, technical articles)
    if len(results) < limit:
        try:
            resp = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": query, "tags": "story", "hitsPerPage": limit + 4},
                headers={"User-Agent": HTTP_HEADERS["User-Agent"]},
                timeout=8,
            )
            if resp.status_code == 200:
                for hit in resp.json().get("hits", []):
                    url = (hit.get("url") or "").strip()
                    title = (hit.get("title") or "").strip()
                    if not url or not title:
                        continue
                    pts = hit.get("points") or 0
                    cmts = hit.get("num_comments") or 0
                    snippet = f"Technical article featured in engineering discussions ({pts} points, {cmts} comments)."
                    if _add(title, snippet, url):
                        return results
        except Exception as e:
            logger.debug(f"HN Algolia fallback skipped: {e}")

    # 3. Tertiary: StackExchange technical Q&A
    if len(results) < limit:
        try:
            resp = requests.get(
                "https://api.stackexchange.com/2.3/search/advanced",
                params={"q": query, "site": "stackoverflow", "pagesize": 3, "sort": "relevance"},
                headers={"User-Agent": HTTP_HEADERS["User-Agent"]},
                timeout=8,
            )
            if resp.status_code == 200:
                for item in resp.json().get("items", []):
                    title = item.get("title") or ""
                    url = item.get("link") or ""
                    score = item.get("score") or 0
                    tags = ", ".join(item.get("tags", [])[:4])
                    snippet = f"Technical Q&A with community-verified answers (score {score}; tags: {tags})."
                    if _add(title, snippet, url):
                        return results
        except Exception as e:
            logger.debug(f"StackExchange fallback skipped: {e}")

    # 4. Quaternary: OpenAlex Open-Access full-text publications (oa_url only, avoiding paywalls)
    if len(results) < limit:
        try:
            resp = requests.get(
                "https://api.openalex.org/works",
                params={"search": query, "filter": "is_oa:true", "per-page": limit + 2},
                headers={"User-Agent": HTTP_HEADERS["User-Agent"]},
                timeout=8,
            )
            if resp.status_code == 200:
                for work in resp.json().get("results", []):
                    title = (work.get("title") or "").strip()
                    oa_url = ((work.get("open_access") or {}).get("oa_url") or "").strip()
                    if not oa_url:
                        continue
                    pub_year = work.get("publication_year") or ""
                    if _add(title, f"Open-access reference article ({pub_year}) on {title}.", oa_url):
                        return results
        except Exception as e:
            logger.debug(f"OpenAlex OA fallback skipped: {e}")

    return results[:limit]


def _fetch_stackoverflow_thread(url: str) -> str:
    """Fetch question + top answers cleanly via StackExchange JSON API."""
    match = re.search(r"stackoverflow\.com/questions/(\d+)", url)
    if not match:
        return ""
    qid = match.group(1)
    q_resp = requests.get(
        f"https://api.stackexchange.com/2.3/questions/{qid}",
        params={"site": "stackoverflow", "filter": "withbody"},
        headers={"User-Agent": HTTP_HEADERS["User-Agent"]},
        timeout=8,
    )
    a_resp = requests.get(
        f"https://api.stackexchange.com/2.3/questions/{qid}/answers",
        params={"site": "stackoverflow", "sort": "votes", "order": "desc", "pagesize": 3, "filter": "withbody"},
        headers={"User-Agent": HTTP_HEADERS["User-Agent"]},
        timeout=8,
    )
    parts: List[str] = []
    if q_resp.status_code == 200:
        for it in q_resp.json().get("items", []):
            parts.append(f"Question: {html.unescape(it.get('title', ''))}\n\n{_strip_tags(it.get('body', ''))}")
    if a_resp.status_code == 200:
        for idx, ans in enumerate(a_resp.json().get("items", []), 1):
            parts.append(f"Answer {idx} (Score {ans.get('score', 0)}):\n{_strip_tags(ans.get('body', ''))}")
    return "\n\n".join(p for p in parts if p.strip())


def fetch_webpage_text(url: str, max_words: int = 3000) -> Tuple[str, str]:
    """
    Fetch readable plain text from any HTTP/HTTPS webpage, StackOverflow thread, or PDF URL.
    Returns (cleaned_text, resolved_url). Caps text at max_words.
    """
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Web URL must begin with http:// or https://")

    if "stackoverflow.com/questions/" in url.lower():
        try:
            so_text = _fetch_stackoverflow_thread(url)
            if len(so_text.split()) >= 40:
                words = so_text.split()
                return (" ".join(words[:max_words]) if len(words) > max_words else so_text), url
        except Exception as e:
            logger.debug(f"StackExchange JSON fetch fell back to HTTP: {e}")

    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=10, allow_redirects=True)
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch URL '{url}': {e}")

    if resp.status_code >= 400:
        raise RuntimeError(
            f"Website returned HTTP {resp.status_code} for '{_domain_label(url)}'. "
            "Try another web result or click 'AI Knowledge Base'."
        )

    content_type = (resp.headers.get("Content-Type") or "").lower()
    final_url = resp.url or url

    if "application/pdf" in content_type or final_url.lower().endswith(".pdf"):
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(resp.content))
            text = "\n\n".join(p.extract_text() or "" for p in reader.pages).strip()
        except Exception as e:
            raise RuntimeError(f"Unable to extract text from PDF at '{final_url}': {e}")
    elif "text/plain" in content_type or "text/markdown" in content_type:
        text = resp.text.strip()
    else:
        if not resp.encoding or resp.encoding.lower() in ("iso-8859-1", "latin-1"):
            if resp.apparent_encoding:
                resp.encoding = resp.apparent_encoding
        parser = _ArticleHTMLParser()
        parser.feed(resp.text)
        text = parser.get_clean_text()

    words = text.split()
    if len(words) < 40:
        raise ValueError(
            f"Could not extract enough readable text from '{_domain_label(final_url)}' "
            "(the page may require JavaScript rendering). Try another search result or "
            "click 'AI Knowledge Base'."
        )

    if len(words) > max_words:
        text = " ".join(words[:max_words])

    return text, final_url
