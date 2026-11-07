#!/usr/bin/env python3
"""Profile AEGIS pipeline stages on the real-paper demonstration.

Measures PDF extraction, claim extraction, Db2 retrieval, LLM verification, and
persistence separately. It creates a temporary session and deletes it afterwards.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.db.connection import execute, transaction  # noqa: E402
from app.db.repository import Db2Repository  # noqa: E402
from app.services.claim_extraction import ClaimExtractionService  # noqa: E402
from app.services.claim_verification import ClaimVerificationService  # noqa: E402
from app.services.document_processing import process_upload  # noqa: E402
from app.services.evidence_retrieval import LexicalRetrievalBackend  # noqa: E402
from app.services.llm import LangChainLLMClient  # noqa: E402

PAPERS = [
    ("attention-is-all-you-need.pdf", "Attention Is All You Need"),
    ("bert-pre-training.pdf", "BERT: Pre-training of Deep Bidirectional Transformers"),
]
RESPONSE_FILE = ROOT / "data" / "samples" / "paper_demo_response.txt"
OUTPUT = ROOT / "experiments" / "results" / "profile_pipeline.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile AEGIS pipeline stages")
    parser.add_argument("--model", default=None, help="Override LLM model")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()

    base = get_settings()
    settings = base.model_copy(update={"llm_model": args.model}) if args.model else base
    repository = Db2Repository(settings)
    llm = LangChainLLMClient(settings)

    timings: dict[str, float] = {}
    detail: dict = {}

    # 1. PDF processing (no database writes).
    pdf_started = time.monotonic()
    pdf_pages = {}
    for filename, _ in PAPERS:
        path = ROOT / "data" / "samples" / "papers" / filename
        if not path.exists():
            print(f"ERROR: missing {path}; run `make demo-papers`.", file=sys.stderr)
            return 2
        before = time.monotonic()
        processed = process_upload(filename, "application/pdf", path.read_bytes())
        pdf_pages[filename] = {
            "seconds": round(time.monotonic() - before, 3),
            "passages": len(processed.passages),
        }
    timings["pdf_processing_seconds"] = round(time.monotonic() - pdf_started, 3)
    detail["pdf"] = pdf_pages

    # Resolve the two paper documents from the library.
    documents = repository.list_documents(limit=100)
    selected: list[int] = []
    for title_prefix in [title for _, title in PAPERS]:
        match = next((doc for doc in documents if doc["title"].startswith(title_prefix)), None)
        if match:
            selected.append(int(match["document_id"]))
    if len(selected) < 2:
        print("ERROR: paper demo documents are not in Db2; run `make demo-papers`.", file=sys.stderr)
        return 2
    detail["document_ids"] = selected

    response_text = RESPONSE_FILE.read_text(encoding="utf-8")

    # 2. Claim extraction.
    extractor = ClaimExtractionService(llm, max_claims=settings.llm_max_claims)
    started = time.monotonic()
    claims = extractor.extract(response_text)
    timings["claim_extraction_seconds"] = round(time.monotonic() - started, 3)
    detail["claims"] = len(claims)

    # 3. Retrieval (production SQL-prefilter path).
    retriever = LexicalRetrievalBackend(repository, top_k=settings.llm_evidence_top_k)
    retrieval_seconds = 0.0
    candidate_sets = []
    retrieval_detail = []
    for claim in claims:
        before = time.monotonic()
        candidates = retriever.retrieve(claim, selected)
        elapsed = time.monotonic() - before
        retrieval_seconds += elapsed
        candidate_sets.append(candidates)
        retrieval_detail.append({
            "claim": claim.original_claim[:80],
            "seconds": round(elapsed, 3),
            "candidates": len(candidates),
        })
    timings["retrieval_seconds"] = round(retrieval_seconds, 3)
    detail["retrieval"] = retrieval_detail

    # 4. LLM verification.
    verifier = ClaimVerificationService(llm)
    verification_seconds = 0.0
    assessments = []
    verification_detail = []
    for claim, candidates in zip(claims, candidate_sets):
        before = time.monotonic()
        assessment = verifier.verify(claim, candidates)
        elapsed = time.monotonic() - before
        verification_seconds += elapsed
        assessments.append(assessment)
        verification_detail.append({
            "claim": claim.original_claim[:80],
            "classification": assessment.classification.value,
            "seconds": round(elapsed, 3),
            "evidence": len(assessment.evidence),
            "method": assessment.verification_method,
        })
    timings["llm_verification_seconds"] = round(verification_seconds, 3)
    detail["verification"] = verification_detail

    # 5. Persistence (temporary session, removed afterwards).
    session_id = repository.create_session(
        response_text, f"{settings.llm_provider}/{settings.llm_model}"
    )
    try:
        before = time.monotonic()
        repository.save_results(
            session_id,
            list(zip(claims, assessments)),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        timings["persistence_seconds"] = round(time.monotonic() - before, 3)
    finally:
        with transaction() as connection:
            execute(connection, "DELETE FROM VERIFICATION_SESSIONS WHERE SESSION_ID = ?", (session_id,))

    timings["total_seconds"] = round(
        timings["pdf_processing_seconds"]
        + timings["claim_extraction_seconds"]
        + timings["retrieval_seconds"]
        + timings["llm_verification_seconds"]
        + timings["persistence_seconds"],
        3,
    )

    result = {
        "model": f"{settings.llm_provider}/{settings.llm_model}",
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "top_k": settings.llm_evidence_top_k,
        "timings": timings,
        "detail": detail,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(timings, indent=2))
    print(f"\nWrote {output_path}")
    for item in verification_detail:
        print(
            f"  {item['seconds']:>6.1f}s  {item['classification']:<22} "
            f"{item['claim'][:65]}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
