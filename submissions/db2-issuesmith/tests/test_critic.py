from issuesmith.critic import review
from issuesmith.issue_writer import fallback_narrative, render_issue
from issuesmith.log_parser import extract_environment, extract_evidence
from issuesmith.sanitizer import sanitize
from conftest import SAMPLES

LOG = sanitize((SAMPLES / "02_quick_restart_stopped_container.log").read_text()).text
EV = [e.as_dict() for e in extract_evidence(LOG)]
ENV = extract_environment(LOG)


def _draft(narrative):
    return render_issue(narrative, ENV, EV, ["a", "b"], False, "Every time", [], [], 3, 1001)


def test_rule_based_draft_passes():
    n = fallback_narrative("RESTART", EV, ENV)
    title, body = _draft(n)
    v = review(title, body, n, LOG, ENV)
    assert v["passed"], v["feedback"]
    assert v["score"] == 100
    assert "Quick restart fails" in title


def test_overclaim_is_blocked():
    n = fallback_narrative("RESTART", EV, ENV)
    n["description"] = "The root cause is a bug in the quick restart code."
    v = review(*_draft(n), n, LOG, ENV)
    assert not v["passed"]
    assert any("Certainty" in f for f in v["feedback"])


def test_invented_quote_is_blocked():
    n = fallback_narrative("RESTART", EV, ENV)
    n["actual"] = ['The extension printed "fatal kernel panic in db2sysc process"']
    v = review(*_draft(n), n, LOG, ENV)
    assert not v["passed"]


def test_real_quote_is_allowed():
    n = fallback_narrative("RESTART", EV, ENV)
    n["actual"] = ['The extension reported "Quick restart failed, full restart required".']
    assert review(*_draft(n), n, LOG, ENV)["passed"]


def test_secret_in_body_is_blocked():
    n = fallback_narrative("RESTART", EV, ENV)
    n["impact"] = "Use PWD=hunter2 to reproduce."
    assert not review(*_draft(n), n, LOG, ENV)["passed"]
