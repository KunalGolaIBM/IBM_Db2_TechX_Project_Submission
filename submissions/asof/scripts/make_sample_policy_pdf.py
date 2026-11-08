"""Render the sample policy revision (src/asof/data/samples/*.html) to the PDF the intake demo uploads.

    pip install playwright && playwright install chromium   # maintainers only; not a runtime dependency
    python scripts/make_sample_policy_pdf.py

The PDF is committed, so nobody running AsOf needs this script. It exists so the sample can be
regenerated from its source instead of edited as a binary.
"""

from __future__ import annotations

import sys
from pathlib import Path

SAMPLES = Path(__file__).resolve().parents[1] / "src" / "asof" / "data" / "samples"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("This maintainer script needs playwright: pip install playwright && playwright install chromium")
        return 2
    sources = sorted(SAMPLES.glob("*.html"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for src in sources:
            page.goto(src.as_uri())
            out = src.with_suffix(".pdf")
            page.pdf(path=str(out), format="A4", print_background=True, prefer_css_page_size=True)
            print(f"wrote {out.relative_to(SAMPLES.parents[2])} ({out.stat().st_size} bytes)")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
