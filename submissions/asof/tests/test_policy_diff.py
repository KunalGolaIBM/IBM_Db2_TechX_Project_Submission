"""The version diff's two halves without Db2: text word by word, RULE_JSON key by key, and the row names the API takes."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi import HTTPException

from asof.api import row_ref
from asof.policy import rule_diff, text_diff


def _rebuild(segments, keep):
    return "".join(s["text"] for s in segments if s["op"] in keep)


@pytest.mark.parametrize("before, after", [
    ("The pet fee is $100 each way.", "The pet fee is $125 each way."),
    ("Bereavement fares must be requested before travel begins.",
     "Bereavement fares can be requested before travel or, within 90 days of ticket issue, after travel."),
    ("", "A new clause."),
    ("Same text.", "Same text."),
    ("Spacing  kept\nacross lines.", "Spacing kept\nacross lines!"),
])
def test_a_text_diff_rebuilds_both_versions_exactly(before, after):
    segments = text_diff(before, after)
    assert _rebuild(segments, {"equal", "delete"}) == before
    assert _rebuild(segments, {"equal", "insert"}) == after
    assert all(a["op"] != b["op"] for a, b in zip(segments, segments[1:], strict=False))  # runs are merged


def test_a_rewritten_sentence_reads_as_one_change_not_fragments():
    segments = text_diff("Fares must be requested before travel begins and no refund is available after travel.",
                         "Fares may be requested before travel or within 90 days after it, with a refund of the difference.")
    changes = [s for s in segments if s["op"] != "equal"]
    assert len(changes) <= 4  # "must"/"may", then one rewritten tail, not a word-by-word interleave


def test_only_the_changed_words_are_marked():
    segments = text_diff("The pet fee is $100 each way.", "The pet fee is $125 each way.")
    assert [s for s in segments if s["op"] != "equal"] == [{"op": "delete", "text": "$100 "}, {"op": "insert", "text": "$125 "}]


def test_rule_parameters_are_compared_key_by_key():
    rows = rule_diff({"retroactive_allowed": False, "request_window_days": 0, "documents": ["death certificate"]},
                     {"retroactive_allowed": True, "request_window_days": 90, "documents": ["death certificate"],
                      "window_starts": "ticket_issue"})
    assert [(r["key"], r["status"]) for r in rows] == [("documents", "same"), ("request_window_days", "changed"),
                                                       ("retroactive_allowed", "changed"), ("window_starts", "added")]
    assert rule_diff({"a": 1}, {})[0] == {"key": "a", "before": 1, "after": None, "status": "removed"}


def test_a_row_is_named_by_its_business_start_and_recorded_time():
    assert row_ref("2026-05-01_2026-11-06T04:00:00.123456") == (date(2026, 5, 1), datetime(2026, 11, 6, 4, 0, 0, 123456))
    with pytest.raises(HTTPException):
        row_ref("2026-02-30_2026-11-06T04:00:00")
