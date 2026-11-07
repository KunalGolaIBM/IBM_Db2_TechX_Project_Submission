"""Claim verification tests, including the evidence-link guardrails."""

from __future__ import annotations

from app.models.domain import Classification, ExtractedClaim, PassageCandidate
from app.services.claim_verification import ClaimVerificationService
from tests.fakes import ScriptedLLM, verification_response

CLAIM = ExtractedClaim(
    original_claim="SolarCell-X achieved 92% conversion efficiency.",
    normalized_claim="SolarCell-X achieved 92% conversion efficiency.",
    claim_type="NUMERICAL",
)

PASSAGES = [
    PassageCandidate(
        passage_id=11,
        document_id=1,
        document_title="Synthetic study",
        filename="study.txt",
        passage_text="SolarCell-X achieved a conversion efficiency of 92% under standard test conditions.",
        page_number=1,
        passage_index=0,
        retrieval_score=7.25,
    ),
    PassageCandidate(
        passage_id=12,
        document_id=1,
        document_title="Synthetic study",
        filename="study.txt",
        passage_text="The coating reduced manufacturing cost by 15%.",
        page_number=1,
        passage_index=1,
        retrieval_score=2.0,
    ),
]


def service_returning(payload: str) -> ClaimVerificationService:
    return ClaimVerificationService(ScriptedLLM(lambda system, user: payload))


def test_supported_with_valid_passage_reference():
    result = service_returning(verification_response("SUPPORTED", [11])).verify(CLAIM, PASSAGES)
    assert result.classification == Classification.SUPPORTED
    assert [item.passage_id for item in result.evidence] == [11]
    assert result.evidence[0].relevance_score == 7.25


def test_fabricated_passage_id_is_downgraded():
    payload = verification_response("SUPPORTED", [999])
    result = service_returning(payload).verify(CLAIM, PASSAGES)
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE
    assert result.evidence == []
    assert "downgraded" in result.explanation.lower()


def test_contradicted_without_evidence_is_downgraded():
    payload = verification_response("CONTRADICTED", [])
    result = service_returning(payload).verify(CLAIM, PASSAGES)
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE
    assert result.evidence == []


def test_missing_evidence_never_becomes_contradiction():
    def handler(system: str, user: str) -> str:
        raise AssertionError("The LLM must not be called without candidates")

    result = ClaimVerificationService(ScriptedLLM(handler)).verify(CLAIM, [])
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE
    assert "not evidence that the claim is false" in result.explanation


def test_malformed_model_json_becomes_verification_error():
    result = service_returning("not json at all").verify(CLAIM, PASSAGES)
    assert result.classification == Classification.VERIFICATION_ERROR


def test_unsupported_classification_becomes_verification_error():
    result = service_returning(verification_response("PROBABLY_TRUE", [11])).verify(CLAIM, PASSAGES)
    assert result.classification == Classification.VERIFICATION_ERROR


def test_lowercase_classification_is_accepted():
    result = service_returning(verification_response("supported", [11])).verify(CLAIM, PASSAGES)
    assert result.classification == Classification.SUPPORTED


def test_duplicate_references_are_collapsed():
    payload = verification_response("SUPPORTED", [11, 11, 12])
    result = service_returning(payload).verify(CLAIM, PASSAGES)
    assert [item.passage_id for item in result.evidence] == [11, 12]


def test_numeric_conflict_overrides_insufficient_model_judgment():
    numeric_claim = ExtractedClaim(
        original_claim="The encoder consists of 8 identical layers.",
        normalized_claim="The encoder consists of 8 identical layers.",
        claim_type="NUMERICAL",
    )
    numeric_passage = PassageCandidate(
        passage_id=21,
        document_id=1,
        document_title="Attention Is All You Need",
        filename="paper.pdf",
        passage_text="The encoder is composed of a stack of N = 6 identical layers.",
        page_number=3,
        passage_index=0,
        retrieval_score=5.0,
    )
    payload = verification_response("INSUFFICIENT_EVIDENCE", [21])
    result = service_returning(payload).verify(numeric_claim, [numeric_passage])
    assert result.classification == Classification.CONTRADICTED
    assert "Deterministic numeric comparison" in result.explanation
    assert "deterministic_numeric_check" in result.verification_method
    assert result.numerical_analysis is not None
    assert "6 identical layers" in result.numerical_analysis


def test_numeric_conflict_attaches_evidence_without_model_citation():
    numeric_claim = ExtractedClaim(
        original_claim="The encoder consists of 8 identical layers.",
        normalized_claim="The encoder consists of 8 identical layers.",
        claim_type="NUMERICAL",
    )
    numeric_passage = PassageCandidate(
        passage_id=22,
        document_id=1,
        document_title="Attention Is All You Need",
        filename="paper.pdf",
        passage_text="The encoder is composed of a stack of N = 6 identical layers.",
        page_number=3,
        passage_index=0,
        retrieval_score=4.0,
    )
    payload = verification_response("INSUFFICIENT_EVIDENCE", [])
    result = service_returning(payload).verify(numeric_claim, [numeric_passage])
    assert result.classification == Classification.CONTRADICTED
    assert [item.passage_id for item in result.evidence] == [22]


def test_percentage_mismatch_does_not_deterministically_override():
    claim = ExtractedClaim(
        original_claim="The method improves accuracy by 5%.",
        normalized_claim="The method improves accuracy by 5%.",
        claim_type="NUMERICAL",
    )
    passage = PassageCandidate(
        passage_id=23,
        document_id=1,
        document_title="Study",
        filename="study.pdf",
        passage_text="95% of participants completed the survey.",
        page_number=2,
        passage_index=0,
        retrieval_score=4.0,
    )
    payload = verification_response("INSUFFICIENT_EVIDENCE", [])
    result = service_returning(payload).verify(claim, [passage])
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE
    assert result.evidence == []


def _passage(text: str, passage_id: int) -> PassageCandidate:
    return PassageCandidate(
        passage_id=passage_id,
        document_id=1,
        document_title="Study",
        filename="study.pdf",
        passage_text=text,
        page_number=1,
        passage_index=passage_id,
        retrieval_score=4.0,
    )


def test_conflicting_comparable_findings_are_insufficient_with_both_sides():
    claim = ExtractedClaim(
        original_claim="Method X improves accuracy by 10%.",
        normalized_claim="Method X improves accuracy by 10%.",
        claim_type="FACTUAL",
    )
    supporting = _passage("Study A reported that Method X improves accuracy by 10%.", 31)
    opposing = _passage(
        "Study B found no statistically significant improvement from Method X.", 32
    )
    payload = verification_response("SUPPORTED", [31])
    result = service_returning(payload).verify(claim, [supporting, opposing])
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE
    assert {item.passage_id for item in result.evidence} == {31, 32}
    assert "Conflicting evidence" in result.explanation
    assert result.verification_method.endswith("conflict_detection")


def test_noncomparable_population_does_not_trigger_conflict():
    claim = ExtractedClaim(
        original_claim="Method X improves accuracy by 10% in adults.",
        normalized_claim="Method X improves accuracy by 10% in adults.",
        claim_type="FACTUAL",
    )
    supporting = _passage("Study A reported that Method X improves accuracy by 10% in adults.", 33)
    different_population = _passage(
        "Study B found no significant improvement from Method X in mice.", 34
    )
    payload = verification_response("SUPPORTED", [33])
    result = service_returning(payload).verify(claim, [supporting, different_population])
    assert result.classification == Classification.SUPPORTED
    assert [item.passage_id for item in result.evidence] == [33]


def test_explicit_contradiction_with_quantitative_limitation_is_not_downgraded():
    claim = ExtractedClaim(
        original_claim="The Transformer relies primarily on convolutional layers.",
        normalized_claim="The Transformer relies primarily on convolutional layers.",
        claim_type="FACTUAL",
    )
    passage = _passage(
        "The Transformer is based solely on attention mechanisms, dispensing with "
        "recurrence and convolutions entirely.",
        36,
    )
    payload = verification_response(
        "CONTRADICTED",
        [36],
        explanation=(
            "Passage 36 states the model dispenses with convolutions, contradicting "
            "the claim."
        ),
        limitations="The evidence does not provide a quantitative measure of reliance.",
    )
    result = service_returning(payload).verify(claim, [passage])
    assert result.classification == Classification.CONTRADICTED


def test_conflicting_citations_on_both_sides_are_insufficient():
    claim = ExtractedClaim(
        original_claim="Method X improves accuracy by 10%.",
        normalized_claim="Method X improves accuracy by 10%.",
        claim_type="FACTUAL",
    )
    supporting = _passage("Study A reported that Method X improves accuracy by 10%.", 41)
    opposing = _passage(
        "Study B found no statistically significant improvement from Method X.", 42
    )
    payload = verification_response(
        "CONTRADICTED",
        [41, 42],
        explanation="Passage 41 supports the claim while passage 42 contradicts it.",
        limitations="The studies report conflicting results.",
    )
    result = service_returning(payload).verify(claim, [supporting, opposing])
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE
    assert {item.passage_id for item in result.evidence} == {41, 42}
    assert result.verification_method.endswith("conflict_detection")


def test_absence_phrasing_in_limitations_is_not_contradiction():
    claim = ExtractedClaim(
        original_claim="Smith et al. (2023) prove the Transformer eliminates hallucinations.",
        normalized_claim="Smith et al. (2023) prove the Transformer eliminates hallucinations.",
        claim_type="FACTUAL",
    )
    passage = _passage("The Transformer is based solely on attention mechanisms.", 43)
    payload = verification_response(
        "CONTRADICTED",
        [43],
        explanation="The passage describes attention mechanisms rather than the claimed result.",
        limitations="The evidence does not directly address hallucinations.",
    )
    result = service_returning(payload).verify(claim, [passage])
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE
    assert result.verification_method.endswith("citation_guard")


def test_citation_claim_without_matching_source_is_insufficient():
    claim = ExtractedClaim(
        original_claim="Smith et al. (2023) prove that the Transformer eliminates hallucinations.",
        normalized_claim="Smith et al. (2023) prove that the Transformer eliminates hallucinations.",
        claim_type="FACTUAL",
    )
    passage = _passage(
        "The Transformer is based solely on attention mechanisms, dispensing with recurrence.",
        44,
    )
    payload = verification_response(
        "CONTRADICTED",
        [44],
        explanation="Passage 44 shows attention-based architecture, contradicting the claim.",
    )
    result = service_returning(payload).verify(claim, [passage])
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE
    assert result.verification_method.endswith("citation_guard")


def test_exclusive_objective_claim_with_additive_passage_is_contradicted():
    claim = ExtractedClaim(
        original_claim="BERT uses next sentence prediction as its only pre-training objective.",
        normalized_claim="BERT uses next sentence prediction as its only pre-training objective.",
        claim_type="FACTUAL",
    )
    passage = _passage(
        "In addition to the masked language model, we also use a next sentence "
        "prediction task that jointly pre-trains text-pair representations.",
        39,
    )
    payload = verification_response("INSUFFICIENT_EVIDENCE", [39])
    result = service_returning(payload).verify(claim, [passage])
    assert result.classification == Classification.CONTRADICTED
    assert result.verification_method.endswith("exclusivity_guard")


def test_additive_language_without_category_does_not_force_contradiction():
    claim = ExtractedClaim(
        original_claim="The model uses attention as its only objective.",
        normalized_claim="The model uses attention as its only objective.",
        claim_type="FACTUAL",
    )
    passage = _passage(
        "In addition to attention, the model also uses convolutional layers.", 40
    )
    payload = verification_response("INSUFFICIENT_EVIDENCE", [40])
    result = service_returning(payload).verify(claim, [passage])
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE


def test_universal_claim_about_absent_category_is_insufficient():
    claim = ExtractedClaim(
        original_claim="LoRA is compatible with every deep learning framework.",
        normalized_claim="LoRA is compatible with every deep learning framework.",
        claim_type="FACTUAL",
    )
    passage = _passage(
        "A small rank may not work for every task or dataset.", 37
    )
    payload = verification_response(
        "CONTRADICTED",
        [37],
        explanation=(
            "Passage 37 says a small rank may not work for every task, contradicting "
            "the claim about every deep learning framework."
        ),
    )
    result = service_returning(payload).verify(claim, [passage])
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE
    assert result.verification_method.endswith("scope_guard")


def test_universal_claim_with_category_present_can_be_contradicted():
    claim = ExtractedClaim(
        original_claim="BERT must be trained from scratch for every downstream task.",
        normalized_claim="BERT must be trained from scratch for every downstream task.",
        claim_type="FACTUAL",
    )
    passage = _passage(
        "BERT can be fine-tuned for a downstream task with one additional output layer.",
        38,
    )
    payload = verification_response("CONTRADICTED", [38])
    result = service_returning(payload).verify(claim, [passage])
    assert result.classification == Classification.CONTRADICTED


def test_unescaped_quotes_inside_evidence_quote_are_repaired():
    payload = """{
      "classification": "INSUFFICIENT_EVIDENCE",
      "explanation": "The passage does not address the claim.",
      "limitations": "No direct evidence was supplied.",
      "evidence": [
        {"passage_id": 11, "quote": "The model uses "encoder-decoder attention" layers."}
      ]
    }"""
    result = ClaimVerificationService(ScriptedLLM(lambda system, user: payload)).verify(
        CLAIM, PASSAGES
    )
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE


def test_malformed_json_is_retried_once():
    calls = {"n": 0}
    valid = verification_response("INSUFFICIENT_EVIDENCE", [])

    def handler(system: str, user: str) -> str:
        calls["n"] += 1
        return "not json" if calls["n"] == 1 else valid

    claim = ExtractedClaim(
        original_claim="An uncited claim.", normalized_claim="An uncited claim.", claim_type="FACTUAL"
    )
    result = ClaimVerificationService(ScriptedLLM(handler)).verify(claim, PASSAGES)
    assert calls["n"] == 2
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE


def test_absence_of_discussion_is_not_contradiction():
    claim = ExtractedClaim(
        original_claim="The Transformer eliminates hallucinations in all applications.",
        normalized_claim="The Transformer eliminates hallucinations in all applications.",
        claim_type="FACTUAL",
    )
    passage = _passage("The Transformer uses self-attention and dispenses with recurrence.", 35)
    payload = verification_response(
        "CONTRADICTED",
        [35],
        explanation="The passage does not address hallucinations.",
        limitations="No evidence about hallucination elimination.",
    )
    result = service_returning(payload).verify(claim, [passage])
    assert result.classification == Classification.INSUFFICIENT_EVIDENCE
    assert result.verification_method.endswith("absence_guard")
