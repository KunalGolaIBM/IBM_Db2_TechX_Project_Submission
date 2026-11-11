"""The US DOT refund rules as AsOf loads them: eCFR XML (kept byte for byte in ecfr/) -> plain text -> text-layer PDF.

    python -m asof.eval.real.text        # rewrites pdf/us_dot_refunds_v{1,2,3}.pdf

Each version's document is a short header (which sections, as of which eCFR date, in force from which date) and the
refund provisions copied from the XML: 14 CFR 259.5(b)(5) before the 2024 rule; 259.5(b)(5), 260.6 and the prompt
refund section (260.9, renumbered 260.10 on 2024-08-12) after it. A section is split at its lettered paragraphs
((a), (b), ...), one line each, so no clause is longer than intake's 4,000-byte limit.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET  # noqa: S405 - parses only the pinned eCFR files in ecfr/
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..unseen.pdfs import make_pdf

HERE = Path(__file__).resolve().parent
ECFR = HERE / "ecfr"
PDF = HERE / "pdf"
API = "https://www.ecfr.gov/api/versioner/v1/full/{on}/title-14.xml?part={part}&section={section}"


@dataclass(frozen=True)
class Source:
    on: str          # the eCFR point-in-time date fetched
    section: str     # e.g. "259.5"
    only: str | None = None  # a paragraph label to keep ("(5)"), or None for the whole section

    @property
    def path(self) -> Path:
        return ECFR / f"{self.on}_{self.section}.xml"

    @property
    def url(self) -> str:
        return API.format(on=self.on, part=self.section.split(".")[0], section=self.section)


@dataclass(frozen=True)
class Version:
    number: int
    effective: date
    sources: tuple[Source, ...]


# Effective dates from the eCFR versions endpoint (title-14.json?part=259 and ?part=260). 259.5's text dates from
# 2016-12-05 (the earliest point-in-time version) until the 2024 refund rule amended it on 2024-06-25. Part 260 took
# effect on 2024-06-25 too, and was corrected and partly renumbered on 2024-08-12 (260.9 "Providing prompt refunds"
# became 260.10). Part 260 as first published (2024-06-25 to 2024-08-11) is fetched but not loaded: the correction
# restructured 260.6, and AsOf cannot end a clause that a later version drops (trial-part260-as-published), so loading
# both texts paragraph by paragraph would leave 2024-06-25 paragraphs in force after 2024-08-12.
VERSIONS = (
    Version(1, date(2016, 12, 5), (Source("2023-01-03", "259.5", "(5)"),)),
    Version(2, date(2024, 6, 25), (Source("2024-07-01", "259.5", "(5)"),)),
    Version(3, date(2024, 8, 12), (Source("2025-06-02", "259.5", "(5)"), Source("2025-06-02", "260.6"),
                                   Source("2025-06-02", "260.10"))),
)
# Fetched to show the text did not change inside a version: 259.5 as of 2024-06-24 (v1's last day) differs from
# 2023-01-03 only by two notes linking the coming amendment.
# 259.5 as of 2026-07-02 (an amendment to other paragraphs) keeps (b)(5) word for word, so v3 stays open-ended.
EXTRA = (Source("2024-06-24", "259.5"), Source("2026-07-02", "259.5"), Source("2024-07-01", "260.6"),
         Source("2024-07-01", "260.9"))
# Intake and APPLY_POLICY_CHANGE store no date before 2020-01-01 (intake.MIN_DATE), so v1, in force on the eCFR from
# 2016-12-05, is loaded as in force from 2020-01-01; every question about it is dated later.
AS_OF_FLOOR = date(2020, 1, 1)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def paragraphs(source: Source) -> tuple[str, list[str]]:
    """The section's heading and its lettered paragraphs, each with its subparagraphs, as plain text."""
    root = ET.fromstring(source.path.read_bytes())  # noqa: S314 - a pinned file, not user input
    head = _clean("".join(root.findtext("HEAD") or ""))
    groups: list[str] = []
    for p in root.iter("P"):
        text = _clean("".join(p.itertext()))
        if not text:
            continue
        if re.match(r"^\([a-h]\) ", text) or not groups:  # (a) to (h); "(i)" is a subparagraph
            groups.append(text)
        else:
            groups[-1] += " " + text
    if source.only:  # one numbered item of 259.5(b)
        items = [_clean("".join(p.itertext())) for p in root.iter("P")]
        groups = [t for t in items if t.startswith(source.only + " ")]
        if len(groups) != 1:
            raise ValueError(f"{source.path.name}: no single paragraph {source.only}")
        groups = [f"(b){groups[0]}"]
    return head, groups


def document(version: Version) -> str:
    cited = ", ".join(f"14 CFR {s.section}{'(b)' + s.only if s.only else ''}" for s in version.sources)
    start = max(version.effective, AS_OF_FLOOR)
    lines = [f"US DOT airline refund rules, version {version.number}: {cited}.",
             f"Loaded into AsOf as in force from {start.isoformat()}. The eCFR shows this text from "
             f"{version.effective.isoformat()}; fetched as of {version.sources[0].on}. A demonstration; not legal advice.",
             ""]
    for s in version.sources:
        head, groups = paragraphs(s)
        lines += [head, *groups, ""]
    return "\n".join(lines).rstrip() + "\n"


def pdf_path(version: Version) -> Path:
    return PDF / f"us_dot_refunds_v{version.number}.pdf"


def build(version: Version) -> bytes:
    return make_pdf(document(version), f"US DOT refund rules v{version.number}")


def main() -> int:
    PDF.mkdir(exist_ok=True)
    for v in VERSIONS:
        pdf_path(v).write_bytes(build(v))
        print(f"wrote {pdf_path(v).name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
