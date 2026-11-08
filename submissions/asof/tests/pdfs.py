"""Minimal text PDFs for the intake tests: real PDF syntax, so pypdf parses them as it parses any upload."""

from __future__ import annotations


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages: list[list[str]]) -> bytes:
    """One page per list of lines, in Helvetica, with a correct cross-reference table."""
    objects: list[bytes] = []
    kids = []
    font_no = 3
    next_no = 4
    page_objs: list[tuple[int, int, bytes]] = []
    for lines in pages:
        content = "BT /F1 11 Tf 14 TL 56 780 Td " + " ".join(f"({_esc(line)}) Tj T*" for line in lines) + " ET"
        page_objs.append((next_no, next_no + 1, content.encode("latin-1")))
        kids.append(f"{next_no} 0 R")
        next_no += 2
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for _page_no, content_no, content in page_objs:
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font_no} 0 R >> >> "
                       f"/Contents {content_no} 0 R >>".encode())
        objects.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


REVISION = [
    "Aurelia Air Customer Service Plan: Revision 2027-1",
    "This revision takes effect on 1 February 2027.",
    "1.1 First checked bag fee",
    "The first checked bag costs $45 each way on Economy fares.",
    "1.2 Sports equipment",
    "One set of golf clubs, skis or a snowboard may be checked for a fee of $75 each way.",
    "2.1 Travel credit validity",
    "This section applies to travel credits issued on or after 1 March 2027.",
    "Travel credits are valid for 24 months from the date they are issued. The booking must be made before the "
    "credit expires, but the flight itself may take place after the expiry date.",
    "3.1 Claiming delay compensation",
    "Delay compensation must be claimed within 1 year of the flight date through the online claims form.",
]
