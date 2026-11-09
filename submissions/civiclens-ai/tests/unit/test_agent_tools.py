"""Unit tests for the tool *guard rails* (validation, auditing, error handling).

These use an in-memory fake repository on purpose: they test argument validation
and audit behaviour, NOT Db2. Db2 behaviour is covered in tests/integration/.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from civiclens.agent.tools import MAX_TOOL_ROWS, CivicLensToolkit


class FakeRepo:
    def __init__(self, fail=False):
        self.audits, self.calls, self.fail = [], [], fail

    def utcnow(self):
        return datetime(2026, 11, 9)

    def list_complaints(self, db, **kw):
        if self.fail:
            raise RuntimeError("boom")
        self.calls.append(("list", kw))
        return []

    def get_complaint(self, db, cid):
        return None

    def hotspots(self, db, **kw):
        self.calls.append(("hotspots", kw))
        return []

    def write_audit(self, db, **kw):
        self.audits.append(kw)
        return len(self.audits)


def tools_by_name(repo):
    kit = CivicLensToolkit(SimpleNamespace(), investigation_id=7, repository=repo)
    return {t.name: t for t in kit.tools()}


def test_toolkit_exposes_only_allowlisted_tools():
    assert set(tools_by_name(FakeRepo())) == {
        "search_complaints",
        "get_complaint",
        "find_duplicate_candidates",
        "hotspot_summary",
    }


def test_tool_args_are_bounded():
    t = tools_by_name(FakeRepo())
    with pytest.raises(ValidationError):
        t["search_complaints"].invoke({"limit": MAX_TOOL_ROWS + 1})
    with pytest.raises(ValidationError):
        t["find_duplicate_candidates"].invoke({"complaint_id": 1, "radius_m": 50_000})
    with pytest.raises(ValidationError):
        t["search_complaints"].invoke({"category": "POTHOLE' OR 1=1 --"})


def test_every_call_is_audited_with_investigation_id():
    repo = FakeRepo()
    t = tools_by_name(repo)
    out = t["search_complaints"].invoke({"category": "POTHOLE", "days": 7})
    assert out == {"ok": True, "data": []}
    assert repo.calls[0][1]["category"].value == "POTHOLE"
    assert repo.audits[-1]["investigation_id"] == 7
    assert repo.audits[-1]["tool_name"] == "search_complaints"
    assert repo.audits[-1]["input_payload"]["category"] == "POTHOLE"


def test_failures_are_audited_and_not_leaked():
    repo = FakeRepo(fail=True)
    out = tools_by_name(repo)["search_complaints"].invoke({})
    assert out["ok"] is False and "boom" not in out["error"]
    assert repo.audits[-1]["success"] is False


def test_not_found_is_structured():
    out = tools_by_name(FakeRepo())["get_complaint"].invoke({"complaint_id": 99})
    assert out["data"] == {"found": False, "complaint_id": 99}


def test_audit_summaries_are_one_readable_line():
    from civiclens.agent.tools import summarise_result

    assert summarise_result([1, 2, 3]) == "3 rows"
    assert summarise_result({"found": False, "complaint_id": 9}) == "complaint #9 not found"
    long = {"complaint_id": 5, "category": "POTHOLE", "description": "x" * 5000}
    assert summarise_result(long) == "complaint #5 (POTHOLE) returned"  # complaint text is never dumped
    assert len(summarise_result({"k": "v" * 1000})) <= 300
