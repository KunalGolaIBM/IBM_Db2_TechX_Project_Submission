"""
Wikipedia and MediaWiki API integration for MasteryLoop.
Implements topic search (action=query, list=search) and plain-text extract
fetching (prop=extracts, explaintext=1, redirects=1, formatversion=2).
"""

import re
import urllib.parse
from typing import Dict, List, Optional, Tuple
import requests

USER_AGENT = "MasteryLoopBot/1.0 (https://github.com/mastree-dev/mastree; contact@masteryloop.org)"
WIKI_API_ENDPOINT = "https://en.wikipedia.org/w/api.php"


def clean_html(raw_html: str) -> str:
    """Strip HTML tags from MediaWiki snippets."""
    clean = re.sub(r"<.*?>", "", raw_html)
    clean = clean.replace("&quot;", '"').replace("&amp;", "&").replace("&#039;", "'").replace("&lt;", "<").replace("&gt;", ">")
    return clean.strip()


def search_wikipedia(query: str, limit: int = 3) -> List[Dict[str, str]]:
    """
    Search Wikipedia using the MediaWiki action=query&list=search API.
    Returns up to limit items with 'title' and 'snippet'.
    """
    query = query.strip()
    if not query:
        return []

    headers = {"User-Agent": USER_AGENT}
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": limit
    }

    try:
        response = requests.get(WIKI_API_ENDPOINT, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        search_results = data.get("query", {}).get("search", [])
        
        results = []
        for item in search_results:
            results.append({
                "id": str(item.get("pageid", item.get("title", ""))),
                "title": item.get("title", ""),
                "snippet": clean_html(item.get("snippet", "")),
                "source": "wikipedia",
                "url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(item.get('title', '').replace(' ', '_'))}"
            })
        return results
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Wikipedia search failed: Unable to connect to Wikipedia API ({e})")
    except Exception as e:
        raise RuntimeError(f"Error parsing Wikipedia search results: {e}")


def fetch_wikipedia_extract(title: str, max_words: int = 3000) -> Tuple[str, str]:
    """
    Fetch the plain text extract for a given Wikipedia title.
    Returns (extracted_text, source_url).
    Caps the plain text at approximately max_words (default 3000).
    """
    title = title.strip()
    if not title:
        raise ValueError("Wikipedia title cannot be empty.")

    headers = {"User-Agent": USER_AGENT}
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "redirects": 1,
        "formatversion": 2,
        "titles": title,
        "format": "json"
    }

    try:
        response = requests.get(WIKI_API_ENDPOINT, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        pages = data.get("query", {}).get("pages", [])
        if not pages:
            raise ValueError(f"No Wikipedia page found for '{title}'.")
        
        page = pages[0]
        if page.get("missing"):
            raise ValueError(f"Wikipedia article '{title}' does not exist.")

        raw_extract = page.get("extract", "").strip()
        if not raw_extract:
            raise ValueError(f"Wikipedia article '{title}' contains no text content.")

        # Cap at max_words
        words = raw_extract.split()
        if len(words) > max_words:
            capped_text = " ".join(words[:max_words]) + f"\n\n[Excerpt capped at {max_words} words for pedagogical focus]"
        else:
            capped_text = raw_extract

        encoded_title = urllib.parse.quote(page.get("title", title).replace(" ", "_"))
        source_url = f"https://en.wikipedia.org/wiki/{encoded_title}"

        return capped_text, source_url
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to fetch Wikipedia article: {e}")

