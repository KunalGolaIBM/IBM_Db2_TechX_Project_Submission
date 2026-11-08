"""The routing evaluation's cases: well formed, labelled with real documents, and the test split frozen."""

from __future__ import annotations

import pytest

from asof.domains import DOC_IDS
from asof.eval import routing_cases as rc


def test_the_routing_test_split_is_frozen():
    assert rc.split_sha256("routing-test") == rc.FROZEN["routing-test"]


@pytest.mark.parametrize("split", sorted(rc.SPLITS))
def test_every_case_is_well_formed(split):
    cases = rc.load(split)
    assert len({c.id for c in cases}) == len(cases)
    for c in cases:
        assert c.expected in (*DOC_IDS, rc.ASK) and c.expected in c.acceptable, c.id
        assert set(c.acceptable) <= {*DOC_IDS, rc.ASK}, c.id
        assert c.question.strip() and c.draft.strip() and c.note.strip(), c.id
        assert (c.expected == rc.ASK) == (c.category in ("ambiguous", "out_of_scope", "mixed")), c.id


def test_the_test_split_covers_both_documents_and_the_ask_cases():
    cases = rc.load("routing-test")
    assert len(cases) == 40
    by = {e: sum(c.expected == e for c in cases) for e in (*DOC_IDS, rc.ASK)}
    assert by == {"AURELIA-CSP": 15, "FERNHOLLOW-FEES": 15, rc.ASK: 10}
