"""Text normalisation and lightweight similarity for duplicate detection."""

from __future__ import annotations

import hashlib
import re

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an and are at be by for from has have in is it near of on or the there this to was with".split()
)


def tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1}


def fingerprint(category: str, title: str, description: str) -> str:
    """SHA-256 of normalised content; identical re-submissions share a fingerprint."""
    norm = " ".join(sorted(tokens(f"{title} {description}")))
    return hashlib.sha256(f"{category.upper()}|{norm}".encode()).hexdigest()


def jaccard(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def duplicate_score(distance_m: float, radius_m: float, text_similarity: float) -> float:
    """Blend proximity and text overlap into [0, 1]."""
    proximity = max(0.0, 1.0 - distance_m / radius_m) if radius_m > 0 else 0.0
    return round(0.5 * proximity + 0.5 * text_similarity, 4)
