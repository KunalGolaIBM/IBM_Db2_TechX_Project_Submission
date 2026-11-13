"""The unseen-domain set (SPR, written by GPT) is pinned byte for byte: AsOf is never tuned on it, and an edit fails here."""
from __future__ import annotations

import hashlib
import json
import pathlib

import pytest

UNSEEN = pathlib.Path(__file__).resolve().parents[1] / "src" / "asof" / "eval" / "unseen"
PINNED = {
    "spr_policy_v1.txt": "29de092dec57d16bc805154098743d063ed51d03f9a6bdbf526925290ef44a3b",
    "spr_policy_v2.txt": "787342ac7662d00b6038dce41a831d5e069b71da7bd02c67bc5f35d9a0acb78a",
    "spr_policy_v3.txt": "8634bab13d3c483f4497287dee2aac07cac58e2e27db2b717c71413ec6de1512",
    "spr_policy_all_versions.txt": "fd42aca851df7e2f2709eece4f843220ff60284bc789f397f0b84cfed7b5243b",
    "spr_40_test_cases.json": "18ede398f1aa11f6de903bdce5ac662d84998c881728ee31485407f688c114f0",
}


@pytest.mark.parametrize(("name", "sha256"), sorted(PINNED.items()))
def test_unseen_file_is_unchanged(name, sha256):
    assert hashlib.sha256((UNSEEN / name).read_bytes()).hexdigest() == sha256


def test_provenance_lists_every_pinned_file_and_its_sum():
    text = (UNSEEN / "PROVENANCE.md").read_text()
    for name, sha256 in PINNED.items():
        assert name in text and sha256 in text


def test_the_set_has_forty_cases():
    cases = json.loads((UNSEEN / "spr_40_test_cases.json").read_text())
    assert len(cases) == 40 and len({c["id"] for c in cases}) == 40
