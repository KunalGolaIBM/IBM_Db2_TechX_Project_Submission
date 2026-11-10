"""Text-layer PDFs of GPT's three SPR policy versions, with not a word changed.

    python -m asof.eval.unseen.pdfs          # rewrites pdf/spr_policy_v1.pdf ... v3.pdf

Each .txt line becomes one or more PDF lines in Courier (so the fare table keeps its columns). A line longer
than the page is wrapped at spaces only, so no word is split or joined. The text is encoded in WinAnsi, which
holds every character the files use (em and en dashes, the curly apostrophe). The output has no timestamps,
so the same text always gives the same bytes; tests/test_unseen_pdfs.py checks that, and that intake's own
reader (intake.read_pdf) gets back exactly the .txt file's words.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSIONS = (1, 2, 3)
FONT_PT = 8.5
LEADING_PT = 11
LEFT_PT, TOP_PT = 45, 800
LINES_PER_PAGE = 68
WRAP_CHARS = 96  # Courier is 0.6 em wide: 96 x 5.1 pt fits the 505 pt between A4 margins


def text_path(version: int) -> Path:
    return HERE / f"spr_policy_v{version}.txt"


def pdf_path(version: int) -> Path:
    return HERE / "pdf" / f"spr_policy_v{version}.pdf"


def layout(text: str) -> list[str]:
    """The PDF's lines: each source line as is when it fits, else wrapped at spaces."""
    out: list[str] = []
    for line in text.split("\n"):
        if len(line) <= WRAP_CHARS:
            out.append(line)
        else:
            out += textwrap.wrap(line, WRAP_CHARS, break_long_words=False, break_on_hyphens=False)
    while out and not out[-1]:
        out.pop()
    return out


def _esc(line: str) -> bytes:
    raw = line.encode("cp1252")  # raises on a character WinAnsi cannot show, rather than dropping it
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def make_pdf(text: str, title: str) -> bytes:
    lines = layout(text)
    pages = [lines[i:i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)]
    objects: list[bytes] = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"]
    kids = []
    for page in pages:
        body = b"".join(b"(" + _esc(line) + b") Tj T*\n" for line in page)
        content = (f"BT /F1 {FONT_PT} Tf {LEADING_PT} TL {LEFT_PT} {TOP_PT} Td\n".encode() + body + b"ET")
        page_no, content_no = len(objects) + 1, len(objects) + 2
        kids.append(f"{page_no} 0 R")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> "
                       f"/Contents {content_no} 0 R >>".encode())
        objects.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()
    objects.append(b"<< /Title (" + _esc(title) + b") /Producer (asof.eval.unseen.pdfs) >>")
    info_no = len(objects)
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info {info_no} 0 R >>\nstartxref\n{xref}\n%%EOF\n"
            .encode())
    return bytes(out)


def build(version: int) -> bytes:
    return make_pdf(text_path(version).read_text(encoding="utf-8"), f"SPR policy v{version}")


def main() -> int:
    for v in VERSIONS:
        path = pdf_path(v)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(build(v))
        print(f"wrote {path.relative_to(HERE)} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
