"""Unit tests for eval/build_queries.py masking and leakage filters (no DB, no Ollama)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
import build_queries as bq  # noqa: E402

M = bq.MASK


def test_variants():
    assert "openwebui" in bq.package_variants("open-webui")
    assert "yaml" in bq.package_variants("PyYAML")
    assert "jinja" in bq.package_variants("Jinja2")
    assert "jose" in bq.package_variants("python-jose")
    assert "apacheairflow" in bq.package_variants("apache-airflow-providers-google")
    assert "pgadmin" in bq.package_variants("pgadmin4")
    assert bq.package_variants("rq") == ["rq"]  # short full name kept
    assert bq.package_variants("") == []


def test_mask_separator_and_case_variants():
    t, n = bq.mask_text("Open WebUI and open_webui.utils and OPEN-WEBUI are affected", ["open-webui"])
    assert "webui" not in t.lower()
    assert n == 3
    assert t.startswith(M)


def test_mask_does_not_touch_substrings_of_other_words():
    t, _ = bq.mask_text("The django-filer app; djangoproject is unrelated", ["django"])
    assert "djangoproject" in t  # no boundary -> untouched
    assert "django-filer" not in t.lower() or M in t


def test_mask_removes_ids_and_urls():
    text = ("PyYAML before 5.4 (CVE-2020-14343, GHSA-8q59-q68h-6hv4) see https://github.com/yaml/pyyaml/issues/1 "
            "and PYSEC-2021-142.")
    t, n = bq.mask_text(text, ["PyYAML"], ["CVE-2020-14343"])
    for s in ("CVE-", "GHSA-", "PYSEC-", "http", "pyyaml", "PyYAML"):
        assert s.lower() not in t.lower(), s
    assert n >= 1
    assert "( )" not in t and "()" not in t


def test_mask_collapses_repeated_tokens():
    t, _ = bq.mask_text("jinja2 / Jinja templates", ["jinja2"])
    assert t.count(M) == 1


def test_contains_package():
    assert bq.contains_package("Remote code execution in PyYAML", ["pyyaml"])
    assert not bq.contains_package("Remote code execution in a YAML parser", ["requests"])
    assert not bq.contains_package("", ["x"])


def test_clean_and_first_part():
    raw = "## Summary\nBad [link](https://x.y/z) here.\n```python\nimport secret\n```\nMore text."
    c = bq.clean_text(raw)
    assert "##" not in c and "https" not in c and "import secret" not in c and "link" in c
    long = "Sentence one is here. " * 60
    fp = bq.first_part(long, 200)
    assert len(fp) <= 200 and fp.endswith(".")


def test_longest_shared_run():
    a = "an attacker can read arbitrary files on the server via path traversal"
    b = "via path traversal an attacker can read arbitrary files"
    assert bq.longest_shared_run(a, b) == 6  # "an attacker can read arbitrary files"
    assert bq.longest_shared_run("one two", "three four") == 0


def test_leak_reason():
    src = ["The flaw allows remote attackers to execute arbitrary code via crafted YAML documents."]
    ok = "Hey, loading some config files lets someone run their own code on our box. Known issue?"
    assert bq.leak_reason(ok, ["PyYAML"], src) is None
    assert bq.leak_reason("Is PyYAML broken? someone ran code on our server", ["PyYAML"], src) == "names_package"
    assert bq.leak_reason("Saw CVE-2020-1747 mentioned, is our loader affected by it?", ["PyYAML"], src) == "contains_advisory_id"
    copy = "I read that it allows remote attackers to execute arbitrary code via crafted input. Real?"
    assert bq.leak_reason(copy, ["PyYAML"], src) == "shares_6_word_run"
    assert bq.leak_reason("short", ["x"], src) == "too_short"


def test_rec_ids_are_stable():
    d = {"adv_id": "GHSA-aaaa-bbbb-cccc", "canon_id": "GHSA-aaaa-bbbb-cccc", "packages": ["x"], "row_bucket": 7}
    r = bq._rec("named", d, "q", {"GHSA-aaaa-bbbb-cccc": ["GHSA-aaaa-bbbb-cccc", "PYSEC-2021-1"]}, False)
    assert r["qid"] == "named:GHSA-aaaa-bbbb-cccc"
    assert r["gt"] == ["GHSA-aaaa-bbbb-cccc", "PYSEC-2021-1"]
