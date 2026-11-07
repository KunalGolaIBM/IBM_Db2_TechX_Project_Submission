#!/usr/bin/env python3
"""Ingest the two demo papers from data/samples/papers into Db2.

The PDFs are not committed. Run scripts/fetch_demo_papers.sh (or make
demo-papers) to download the public arXiv versions and seed them.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.repository import Db2Repository  # noqa: E402
from app.services.documents import DocumentService  # noqa: E402

PAPERS = [
    (
        "attention-is-all-you-need.pdf",
        "Attention Is All You Need (Vaswani et al., 2017)",
        "https://arxiv.org/abs/1706.03762",
    ),
    (
        "bert-pre-training.pdf",
        "BERT: Pre-training of Deep Bidirectional Transformers (Devlin et al., 2019)",
        "https://arxiv.org/abs/1810.04805",
    ),
]


def main() -> int:
    papers_dir = ROOT / "data" / "samples" / "papers"
    missing = [name for name, _, _ in PAPERS if not (papers_dir / name).exists()]
    if missing:
        print("Demo paper PDFs are missing:")
        for name in missing:
            print(f"  {papers_dir / name}")
        print("\nDownload them with one of:")
        print("  make demo-papers")
        print("  bash scripts/fetch_demo_papers.sh")
        print("\nSources:")
        for _, _, url in PAPERS:
            print(f"  {url}")
        return 2

    service = DocumentService(Db2Repository())
    for filename, title, url in PAPERS:
        data = (papers_dir / filename).read_bytes()
        result = service.ingest_upload(filename, "application/pdf", data, title=title)
        print(f"{'Already stored' if result['already_existed'] else 'Stored'}: "
              f"document #{result['document_id']} — {title}")
        print(f"  passages: {result['passage_count']} | source: {url}")

    print("\nPaper demo evidence is ready. Open the UI and click 'Paper demo'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
