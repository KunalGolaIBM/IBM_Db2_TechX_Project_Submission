#!/usr/bin/env python3
"""Seed AEGIS with the small, clearly labelled synthetic demonstration document.

This script only inserts source evidence, never verification judgments. The
demo must execute the real LangChain pipeline to produce classifications.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.repository import Db2Repository  # noqa: E402
from app.services.document_processing import process_text  # noqa: E402
from app.services.documents import DocumentService  # noqa: E402

SAMPLE = ROOT / "data" / "samples" / "synthetic_solarcell_study.txt"


def main() -> int:
    if not SAMPLE.exists():
        print(f"ERROR: sample document missing: {SAMPLE}")
        return 2
    data = SAMPLE.read_bytes()
    processed = process_text(
        data,
        filename="synthetic_solarcell_study.txt",
        title="Synthetic demo — SolarCell-X Controlled Efficiency Trial (fictional)",
    )
    service = DocumentService(Db2Repository())
    result = service.ingest_processed(processed)
    print("Synthetic evidence document ready:")
    print(f"  document_id:  {result['document_id']}")
    print(f"  passages:     {result['passage_count']}")
    print(f"  deduplicated: {result['already_existed']}")
    print("\nOpen the AEGIS UI, click 'Load synthetic demo', and run verification.")
    print("The classifications are produced by the configured LLM, not hardcoded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
