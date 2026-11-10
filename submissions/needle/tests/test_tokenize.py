"""Identifier handling of the shared tokenizer (needle.tokenize) and the BM25 analyzer (needle.bm25). No DB."""
import json
import sys
from itertools import islice
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from needle.bm25 import (MAX_TERMS_PER_DOC, analyze, doc_terms, keep, prune_query_terms,  # noqa: E402
                         query_terms)
from needle.tokenize import index_text, tokenize  # noqa: E402


def test_identifiers_whole_plus_parts():
    assert tokenize("PyYAML") == ["pyyaml"]
    assert tokenize("log4j-core") == ["log4j-core", "log4j", "core"]
    assert tokenize("CVE-2021-44228") == ["cve-2021-44228", "cve", "2021", "44228"]
    assert tokenize("django.contrib.admin") == ["django.contrib.admin", "django", "contrib", "admin"]
    assert tokenize("GHSA-jfh8-c2jp-5v3q")[0] == "ghsa-jfh8-c2jp-5v3q"
    assert tokenize("PYSEC-2021-142")[0] == "pysec-2021-142"


def test_separators_and_trailing_punctuation():
    assert tokenize("pyyaml.") == ["pyyaml"]
    assert tokenize("(requests)") == ["requests"]
    assert tokenize("_process_picture_url") == ["process_picture_url", "process", "picture", "url"]
    assert tokenize("https://github.com/x/y") == ["https", "github.com", "github", "com", "x", "y"]
    assert tokenize("") == [] and tokenize(None) == []


def test_analyzer_drops_stopwords_and_single_chars_keeps_identifiers():
    toks = analyze("The PyYAML package in version 5.4.1 is not safe")
    assert "the" not in toks and "in" not in toks and "is" not in toks and "not" not in toks
    assert "pyyaml" in toks and "package" in toks and "5.4.1" in toks
    assert "5" not in toks and "4" not in toks and "1" not in toks  # 1-char parts dropped
    assert analyze("log4j-core") == ["log4j-core", "log4j", "core"]
    assert keep("x" * 128) and not keep("x" * 129) and not keep("é" * 65)  # 130 bytes > VARCHAR(128)


def test_query_terms_distinct_in_first_occurrence_order():
    assert query_terms("yaml load YAML Load pyyaml") == ["yaml", "load", "pyyaml"]
    assert query_terms("the a of") == []


def test_prune_query_terms_lowest_df_first():
    df = {"rare": 1, "mid": 50, "common": 9000, "tie_b": 50}
    assert prune_query_terms(["common", "mid", "rare", "unknown", "tie_b"], df, max_terms=3) == ["rare", "mid", "tie_b"]


def test_doc_terms_cap_keeps_highest_tf():
    words = [f"w{i:04d}" for i in range(MAX_TERMS_PER_DOC + 100)]
    details = " ".join(words) + " " + " ".join(["hot"] * 5)
    doc = {"adv_id": "TEST-1", "aliases": [], "packages": [], "summary": "", "details": details}
    toks = doc_terms(doc)
    assert len(set(toks)) == MAX_TERMS_PER_DOC
    assert toks.count("hot") == 5 and "test-1" in toks  # highest tf kept; first-position ties keep the id
    assert "w0611" not in toks  # last-seen tf=1 terms dropped


@pytest.mark.skipif(not (ROOT / "data" / "docs.jsonl").exists(), reason="data/docs.jsonl not built")
def test_doc_len_matches_shared_tokenizer_on_real_docs():
    with open(ROOT / "data" / "docs.jsonl", encoding="utf-8") as f:
        for line in islice(f, 500):
            d = json.loads(line)
            assert len(tokenize(index_text(d))) == d["doc_len"], d["adv_id"]
