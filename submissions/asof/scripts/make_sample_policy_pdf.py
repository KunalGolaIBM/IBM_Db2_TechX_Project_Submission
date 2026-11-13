"""Render the policy documents written as HTML to PDF: the intake demo's sample (src/asof/data/samples) and the
intake evaluation's documents (src/asof/eval/intake).

    pip install playwright && playwright install chromium   # maintainers only; not a runtime dependency
    python scripts/make_sample_policy_pdf.py            # renders only PDFs that do not exist yet
    python scripts/make_sample_policy_pdf.py --force    # re-renders all (Chromium stamps the time, so the bytes and
                                                         # the SHA-256 change even when the text does not)

The PDFs are committed, so nobody running AsOf needs this script. It exists so a document can be
regenerated from its source instead of edited as a binary. The evaluation's documents are frozen:
never re-render those.
"""

from __future__ import annotations

import sys
from pathlib import Path

SAMPLES = Path(__file__).resolve().parents[1] / "src" / "asof" / "data" / "samples"
EVAL = SAMPLES.parents[1] / "eval" / "intake"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("This maintainer script needs playwright: pip install playwright && playwright install chromium")
        return 2
    sources = sorted(SAMPLES.glob("*.html")) + sorted(EVAL.glob("*.html"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for src in sources:
            out = src.with_suffix(".pdf")
            if out.exists() and "--force" not in sys.argv:
                continue
            page.goto(src.as_uri())
            page.pdf(path=str(out), format="A4", print_background=True, prefer_css_page_size=True)
            print(f"wrote {out.relative_to(SAMPLES.parents[2])} ({out.stat().st_size} bytes)")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
