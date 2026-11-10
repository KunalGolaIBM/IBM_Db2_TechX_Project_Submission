"""Shared tokenizer for NEEDLE (BM25 postings, doc_len, query terms).

Rules (deterministic, no external dependencies):
1. Lowercase the text (str.lower()).
2. Find "compound" tokens: runs of letters/digits joined by single '.', '-' or '_'
   characters, e.g. ``pyyaml``, ``log4j-core``, ``cve-2021-44228``, ``django.contrib``,
   ``ghsa-xxxx-yyyy-zzzz``, ``_process_picture_url`` -> ``process_picture_url``.
   Any other character (space, '/', ':', '(', quotes, a trailing '.', ...) separates tokens.
3. Emit every compound token as one whole token.
4. If the compound token contains a joiner, ALSO emit each of its parts
   (``log4j-core`` -> ``log4j-core``, ``log4j``, ``core``).
5. Drop tokens longer than MAX_TERM_LEN characters (NEEDLE.POSTING.TERM is VARCHAR(128));
   the parts of a dropped compound are still emitted.

The output keeps duplicates, so ``len(tokenize(text))`` is a document length and
``collections.Counter(tokenize(text))`` gives term frequencies.
No stop words are removed and no stemming is applied.

``index_text(doc)`` defines WHICH text of a docs.jsonl record is indexed for keywords.
``doc_len`` in docs.jsonl equals ``len(tokenize(index_text(doc)))``.
"""
from __future__ import annotations

import re
from typing import Iterable

MAX_TERM_LEN = 128

# [^\W_] = a Unicode letter or digit (word char without underscore).
_COMPOUND = re.compile(r"[^\W_]+(?:[._\-][^\W_]+)*")
_JOINER = re.compile(r"[._\-]")


def tokenize(text: str | None) -> list[str]:
    """Return the token list (with duplicates) for ``text``."""
    if not text:
        return []
    out: list[str] = []
    for m in _COMPOUND.finditer(text.lower()):
        tok = m.group(0)
        if len(tok) <= MAX_TERM_LEN:
            out.append(tok)
        if _JOINER.search(tok):
            for part in _JOINER.split(tok):
                if part and len(part) <= MAX_TERM_LEN:
                    out.append(part)
    return out


def index_text(doc: dict) -> str:
    """Text of one docs.jsonl record that the keyword index covers.

    adv_id + aliases + affected package names + summary + full details.
    """
    parts: Iterable[str] = (
        doc.get("adv_id") or "",
        " ".join(doc.get("aliases") or []),
        " ".join(doc.get("packages") or []),
        doc.get("summary") or "",
        doc.get("details") or "",
    )
    return "\n".join(p for p in parts if p)


if __name__ == "__main__":
    sample = "Log4j-core CVE-2021-44228 in django.contrib.admin; PyYAML <5.4 (see https://github.com/x/y)."
    print(tokenize(sample))
