"""CSV ingestion, label evidence and evaluation without exact-text retrieval leakage."""
import pytest

from load_scam_examples import DATA_DIR, example_id, load_examples, read_examples
from risk import RiskEngine, ScreenRequest
from signals import run_rules


class EvaluationRepo:
    """Remove ALL evaluation texts from retrieved candidates before selecting top-k.

    The supplied 15 evaluation messages also appear in the 105-row training CSV.
    Production still loads all 105 as requested; this adapter is evaluation-only.
    """

    def __init__(self, repo, heldout):
        self.repo = repo
        self.excluded = {row["text"].strip().casefold() for row in heldout}

    def __getattr__(self, name):
        return getattr(self.repo, name)

    def search_examples(self, vec, k=3):
        candidates = self.repo.search_examples(vec, k=max(1, len(self.repo.example_ids())))
        return [row for row in candidates if row["text"].strip().casefold() not in self.excluded][:k]


def evaluate_heldout(repo, embedder):
    heldout = read_examples(DATA_DIR / "heldout_v1.csv")
    assert len(heldout) == 15
    evaluation = EvaluationRepo(repo, heldout)
    engine = RiskEngine(evaluation, embedder)
    results = [engine.screen(ScreenRequest(message=row["text"]), persist=False) for row in heldout]
    assert all(match["text"].strip().casefold() not in evaluation.excluded
               for result in results for match in result.matched_examples)
    safe = [(row, result) for row, result in zip(heldout, results) if row["label"] == "safe"]
    scams = [(row, result) for row, result in zip(heldout, results) if row["label"] != "safe"]
    caught = sum(result.verdict != "ALLOW" for _, result in scams)
    allowed = sum(result.verdict == "ALLOW" for _, result in safe)
    print(f"Evaluation (all exact-text overlaps excluded): scams flagged {caught}/{len(scams)}; "
          f"safe allowed {allowed}/{len(safe)}")
    # Guard useful detections and benign banking notices without claiming perfect recall.
    assert results[0].verdict == "BLOCK"  # BVN phishing
    assert results[1].verdict != "ALLOW"  # job registration fee
    assert results[8].verdict != "ALLOW"  # customs clearance fee
    assert results[9].verdict != "ALLOW"  # guaranteed weekly investment returns
    assert all(result.verdict == "ALLOW" for _, result in safe)
    return caught, allowed


def test_loader_is_idempotent_and_keeps_evaluation_out_of_playbooks(repo, embedder):
    original_playbooks = len(repo.patterns)
    assert load_examples(repo, embedder) == {"rows": 105, "inserted": 105, "skipped": 0}
    assert load_examples(repo, embedder) == {"rows": 105, "inserted": 0, "skipped": 105}
    assert repo.example_ids() == {example_id(row) for row in read_examples()}
    assert len(repo.patterns) == original_playbooks == 25
    assert {row_id: row["source"] for row_id, row in repo.examples.items()} == {
        example_id(row): row["source"] for row in read_examples()}


def test_example_label_is_visible_in_verdict_evidence(repo, embedder):
    load_examples(repo, embedder)
    text = read_examples()[0]["text"]
    result = RiskEngine(repo, embedder).screen(ScreenRequest(message=text), persist=False)
    assert result.matched_examples[0]["label"] == "bank_phishing"
    assert result.matched_examples[0]["similarity"] == pytest.approx(1.0)
    assert any(r["code"] == "EXAMPLE_MATCH" and "bank_phishing" in r["evidence"] for r in result.reasons)


def test_safe_example_cannot_cancel_hard_risk(repo, embedder):
    text = "Send your OTP now"
    repo.insert_example("safe-test", {"label": "safe", "text": text, "source": "unit-test"},
                        embedder.embed([text])[0])
    result = RiskEngine(repo, embedder).screen(ScreenRequest(message=text), persist=False)
    assert result.verdict == "BLOCK" and result.risk_score >= 70


def test_heldout_pipeline_without_self_matches(repo, embedder):
    load_examples(repo, embedder)
    evaluate_heldout(repo, embedder)


def test_csv_requires_valid_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("text,label\nhello,safe\n", encoding="utf-8")
    with pytest.raises(ValueError, match="columns"):
        read_examples(path)


def test_safety_warning_does_not_hide_a_separate_credential_request():
    warning = "Never share your password, PIN, BVN or OTP with anyone. We will NEVER ask for such information."
    assert "CREDENTIALS" not in {s.code for s in run_rules(warning)}
    assert "CREDENTIALS" in {s.code for s in run_rules(warning + " Now send me your OTP.")}
    assert "CREDENTIALS" in {s.code for s in run_rules("Never share your OTP with anyone except me")}
    assert "CREDENTIALS" in {s.code for s in run_rules("Never share your OTP with anyone, send it to me now")}
