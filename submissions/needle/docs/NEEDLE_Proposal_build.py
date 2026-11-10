#!/usr/bin/env python3
"""Build NEEDLE_Proposal.pdf from NEEDLE_Proposal.md with reportlab.

Usage:
    python NEEDLE_Proposal_build.py [--md NEEDLE_Proposal.md] [--out NEEDLE_Proposal.pdf] [--fonts DIR]

DIR holds IBMPlexSans-Regular.ttf, IBMPlexSans-SemiBold.ttf, IBMPlexSans-Italic.ttf and
IBMPlexMono-Regular.ttf (SIL Open Font License, https://github.com/IBM/plex). The env var
NEEDLE_FONTS_DIR also sets DIR. Without the fonts the script falls back to Helvetica/Courier.

Supported Markdown subset: front matter (key: value), "## " headings, paragraphs, "> " callout,
"- " bullets, "1. " numbered items, pipe tables, **bold**, *italic*, `code`, and the
"<!-- diagram -->" marker for the architecture diagram.
"""
import argparse
import os
import re
from pathlib import Path

from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, KeepTogether, ListFlowable,
                                ListItem, PageTemplate, Paragraph, Spacer, Table, TableStyle)

# Carbon-like tokens: neutral grays and one blue accent.
BLUE = colors.HexColor("#0f62fe")
BLUE_10 = colors.HexColor("#edf5ff")
G100 = colors.HexColor("#161616")
G70 = colors.HexColor("#525252")
G50 = colors.HexColor("#8d8d8d")
G20 = colors.HexColor("#e0e0e0")
G10 = colors.HexColor("#f4f4f4")
WHITE = colors.white

PAGE_W, PAGE_H = A4
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 44, 40, 46
CONTENT_W = PAGE_W - 2 * MARGIN_X

F, FB, FI, FM = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"


def register_fonts(font_dir):
    global F, FB, FI, FM
    files = {
        "Plex": "IBMPlexSans-Regular.ttf",
        "Plex-SemiBold": "IBMPlexSans-SemiBold.ttf",
        "Plex-Italic": "IBMPlexSans-Italic.ttf",
        "PlexMono": "IBMPlexMono-Regular.ttf",
    }
    if font_dir and all((Path(font_dir) / f).is_file() for f in files.values()):
        for name, f in files.items():
            pdfmetrics.registerFont(TTFont(name, str(Path(font_dir) / f)))
        pdfmetrics.registerFontFamily("Plex", normal="Plex", bold="Plex-SemiBold",
                                      italic="Plex-Italic", boldItalic="Plex-SemiBold")
        F, FB, FI, FM = "Plex", "Plex-SemiBold", "Plex-Italic", "PlexMono"
        return True
    return False


# ---------------------------------------------------------------- Markdown subset

def inline(text, code_size):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    out = []
    for part in re.split(r"(`[^`]+`)", text):
        if len(part) > 1 and part.startswith("`") and part.endswith("`"):
            out.append(f'<font face="{FM}" size="{code_size}">{part[1:-1]}</font>')
        else:
            part = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", part)
            part = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", part)
            out.append(part)
    return "".join(out)


def parse(md_text):
    lines = md_text.splitlines()
    meta, blocks, i = {}, [], 0
    if lines and lines[0].strip() == "---":
        i = 1
        while lines[i].strip() != "---":
            key, value = lines[i].split(":", 1)
            meta[key.strip()] = value.strip()
            i += 1
        i += 1
    para = []

    def flush():
        if para:
            blocks.append(("p", " ".join(para)))
            para.clear()

    def take(prefix_re):
        nonlocal i
        items = []
        while i < len(lines) and re.match(prefix_re, lines[i].strip()):
            items.append(re.sub(prefix_re, "", lines[i].strip(), count=1))
            i += 1
        return items

    while i < len(lines):
        st = lines[i].strip()
        if not st:
            flush()
            i += 1
        elif st.startswith("## "):
            flush()
            blocks.append(("h2", st[3:]))
            i += 1
        elif st == "<!-- diagram -->":
            flush()
            blocks.append(("diagram", None))
            i += 1
        elif st.startswith("> "):
            flush()
            blocks.append(("callout", " ".join(take(r"^> "))))
        elif st.startswith("- "):
            flush()
            blocks.append(("ul", take(r"^- ")))
        elif re.match(r"^\d+\. ", st):
            flush()
            blocks.append(("ol", take(r"^\d+\. ")))
        elif st.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if not re.match(r"^\|[\s\-:|]+\|$", row):
                    rows.append([c.strip() for c in row.strip("|").split("|")])
                i += 1
            blocks.append(("table", rows))
        else:
            para.append(st)
            i += 1
    flush()
    return meta, blocks


# ---------------------------------------------------------------- Styles

def styles():
    return {
        "eyebrow": ParagraphStyle("eyebrow", fontName=F, fontSize=8.5, leading=11, textColor=G70),
        "title": ParagraphStyle("title", fontName=FB, fontSize=26, leading=30, textColor=G100,
                                spaceBefore=4),
        "subtitle": ParagraphStyle("subtitle", fontName=F, fontSize=13.5, leading=18, textColor=G100),
        "meta": ParagraphStyle("meta", fontName=F, fontSize=9, leading=12, textColor=G70, spaceBefore=6),
        "h2": ParagraphStyle("h2", fontName=FB, fontSize=11.5, leading=15, textColor=G100,
                             spaceBefore=8, spaceAfter=2, keepWithNext=1),
        "body": ParagraphStyle("body", fontName=F, fontSize=9.2, leading=12.4, textColor=G100,
                               spaceAfter=3),
        "li": ParagraphStyle("li", fontName=F, fontSize=9.2, leading=12.2, textColor=G100),
        "callout": ParagraphStyle("callout", fontName=F, fontSize=10, leading=14, textColor=G100),
        "th": ParagraphStyle("th", fontName=FB, fontSize=8.4, leading=11, textColor=G100),
        "td": ParagraphStyle("td", fontName=F, fontSize=8.4, leading=11, textColor=G100),
        "caption": ParagraphStyle("caption", fontName=F, fontSize=8, leading=10.5, textColor=G70,
                                  spaceBefore=3, spaceAfter=2),
    }


# ---------------------------------------------------------------- Diagram

def _text_block(d, cx, cy, lines):
    """lines: list of (text, font, size, color); centred on (cx, cy)."""
    gaps = [s * 1.25 for _, _, s, _ in lines]
    total = sum(gaps)
    y = cy + total / 2
    for (text, font, size, color), g in zip(lines, gaps):
        y -= g
        d.add(String(cx, y + (g - size) / 2 + size * 0.18, text, fontName=font, fontSize=size,
                     fillColor=color, textAnchor="middle"))


def _box(d, x, y, w, h, lines, fill=WHITE, stroke=G50, sw=0.6):
    d.add(Rect(x, y, w, h, fillColor=fill, strokeColor=stroke, strokeWidth=sw))
    _text_block(d, x + w / 2, y + h / 2, lines)


def _arrow(d, x1, y1, x2, y2, color=G70, both=False):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=0.9))

    def head(xa, ya, xb, yb):  # arrow head at (xb, yb) pointing from (xa, ya)
        import math
        ang = math.atan2(yb - ya, xb - xa)
        size, spread = 5.0, 0.42
        p1 = (xb - size * math.cos(ang - spread), yb - size * math.sin(ang - spread))
        p2 = (xb - size * math.cos(ang + spread), yb - size * math.sin(ang + spread))
        d.add(Polygon([xb, yb, p1[0], p1[1], p2[0], p2[1]], fillColor=color, strokeColor=color,
                      strokeWidth=0.2))

    head(x1, y1, x2, y2)
    if both:
        head(x2, y2, x1, y1)


def diagram(width):
    H = 158
    d = Drawing(width, H)
    gap = 13
    w_osv, w_load, w_ret, w_ui = 62, 70, 76, 54
    w_db = width - (w_osv + w_load + w_ret + w_ui) - 4 * gap
    x_osv = 0
    x_load = x_osv + w_osv + gap
    x_db = x_load + w_load + gap
    x_ret = x_db + w_db + gap
    x_ui = x_ret + w_ret + gap

    oll_y, oll_h = 0, 24
    db_y = oll_h + 18
    db_h = H - db_y - 1
    mid = db_y + db_h / 2
    bh = 48

    T, S = 7.4, 6.4  # title / sub font sizes
    _box(d, x_osv, mid - bh / 2, w_osv, bh,
         [("OSV PyPI", FB, T, G100), ("advisories", FB, T, G100), ("JSON export", F, S, G70)])
    _box(d, x_load, mid - bh / 2, w_load, bh,
         [("Loader", FB, T, G100), ("Python · ibm_db", F, S, G70), ("MERGE, embeddings", F, S, G70)])
    _box(d, x_ret, mid - bh / 2, w_ret, bh,
         [("LangChain", FB, T, G100), ("retriever", FB, T, G100), ("+ ID verifier", F, S, G70)])
    _box(d, x_ui, mid - bh / 2, w_ui, bh,
         [("Streamlit", FB, T, G100), ("UI", FB, T, G100), ("analyst", F, S, G70)])

    # Db2 container
    d.add(Rect(x_db, db_y, w_db, db_h, fillColor=BLUE_10, strokeColor=BLUE, strokeWidth=1))
    d.add(String(x_db + 8, db_y + db_h - 12, "IBM Db2 12.1.5", fontName=FB, fontSize=8,
                 fillColor=BLUE))
    pad, inner_gap = 7, 4
    w_tri = 62
    x_tri = x_db + w_db - pad - w_tri
    x_tab = x_db + pad
    w_tab = x_tri - inner_gap - 4 - x_tab
    top = db_y + db_h - 18
    bottom = db_y + pad
    n = 4
    h_tab = (top - bottom - (n - 1) * inner_gap) / n
    tables = [
        ("ADV_DOC", "VECTOR(768) + ADV_DOC_VIX"),
        ("POSTING", "BM25 terms, statistics"),
        ("RCAC", "permissions + column mask"),
        ("SBOM_COMPONENT", "BUSINESS_TIME history"),
    ]
    for k, (name, sub) in enumerate(tables):
        y = top - (k + 1) * h_tab - k * inner_gap
        _box(d, x_tab, y, w_tab, h_tab, [(name, FB, 6.9, G100), (sub, F, 6.0, G70)],
             fill=WHITE, stroke=G50, sw=0.5)
    _box(d, x_tri, bottom, w_tri, top - bottom,
         [("NEEDLE.TRIAGE", FB, 7.0, WHITE), ("SQL PL procedure", F, 6.2, WHITE), ("", F, 3, WHITE),
          ("BM25 rank", F, 6.2, WHITE), ("+ FETCH APPROX", F, 6.2, WHITE), ("RRF fusion", F, 6.2, WHITE)],
         fill=BLUE, stroke=BLUE)

    # Ollama layer
    x_oll = x_load
    w_oll = x_ret + w_ret - x_load
    _box(d, x_oll, oll_y, w_oll, oll_h,
         [("Ollama (local):  nomic-embed-text for embeddings  ·  qwen3 for the cited memo", F, 7.2, G100)],
         fill=G10, stroke=G20)

    # Flows: data left to right, queries right to left
    _arrow(d, x_osv + w_osv, mid, x_load - 1, mid)
    _arrow(d, x_load + w_load, mid, x_db - 1, mid)
    _arrow(d, x_ui, mid, x_ret + w_ret + 1, mid)
    _arrow(d, x_ret, mid, x_db + w_db + 1, mid)
    _arrow(d, x_load + w_load / 2, oll_h, x_load + w_load / 2, mid - bh / 2 - 1, both=True)
    _arrow(d, x_ret + w_ret / 2, oll_h, x_ret + w_ret / 2, mid - bh / 2 - 1, both=True)
    return d


# ---------------------------------------------------------------- Page decoration

class NumberedCanvas(rl_canvas.Canvas):
    footer_text = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._decorate(total)
            super().showPage()
        super().save()

    def _decorate(self, total):
        self.saveState()
        self.setFillColor(BLUE)
        self.rect(0, PAGE_H - 4, PAGE_W, 4, stroke=0, fill=1)
        self.setStrokeColor(G20)
        self.setLineWidth(0.5)
        self.line(MARGIN_X, MARGIN_BOTTOM - 14, PAGE_W - MARGIN_X, MARGIN_BOTTOM - 14)
        self.setFont(F, 7.5)
        self.setFillColor(G70)
        self.drawString(MARGIN_X, MARGIN_BOTTOM - 26, self.footer_text)
        self.drawRightString(PAGE_W - MARGIN_X, MARGIN_BOTTOM - 26,
                             f"Page {self._pageNumber} of {total}")
        self.restoreState()


# ---------------------------------------------------------------- Build

def build(md_path, out_path):
    meta, blocks = parse(Path(md_path).read_text(encoding="utf-8"))
    st = styles()
    story = [
        Paragraph(inline(meta.get("eyebrow", ""), 8), st["eyebrow"]),
        Paragraph(inline(meta.get("title", ""), 24), st["title"]),
        Paragraph(inline(meta.get("subtitle", ""), 12), st["subtitle"]),
        Paragraph(f'<b>{inline(meta.get("team", ""), 8)}</b>  ·  {inline(meta.get("date", ""), 8)}',
                  st["meta"]),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=0.6, color=G20, spaceBefore=0, spaceAfter=7),
    ]
    section = 0
    for kind, payload in blocks:
        if kind == "h2":
            section += 1
            story.append(Paragraph(
                f'<font color="#0f62fe">{section:02d}</font>&nbsp;&nbsp;{inline(payload, 10.5)}',
                st["h2"]))
        elif kind == "p":
            para = Paragraph(inline(payload, 8.6), st["body"])
            para.keepWithNext = payload.rstrip().endswith(":")  # keep a lead-in with its list/table
            story.append(para)
        elif kind == "callout":
            cell = Paragraph(inline(payload, 9.3), st["callout"])
            t = Table([[cell]], colWidths=[CONTENT_W])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), G10),
                ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            story += [t, Spacer(1, 2)]
        elif kind in ("ul", "ol"):
            items = [ListItem(Paragraph(inline(x, 8.6), st["li"]), spaceAfter=1.5) for x in payload]
            if kind == "ul":
                lst = ListFlowable(items, bulletType="bullet", start="•", bulletColor=BLUE,
                                   bulletFontName=F, bulletFontSize=9, leftIndent=12, bulletOffsetY=0)
            else:
                lst = ListFlowable(items, bulletType="1", bulletFormat="%s.", bulletColor=BLUE,
                                   bulletFontName=FB, bulletFontSize=9.2, leftIndent=14)
            story += [lst, Spacer(1, 3)]
        elif kind == "table":
            ncols = len(payload[0])
            fractions = {2: [0.44, 0.56], 4: [0.21, 0.24, 0.21, 0.34]}.get(ncols, [1 / ncols] * ncols)
            widths = [CONTENT_W * f for f in fractions]
            data = [[Paragraph(inline(c, 7.9), st["th"] if r == 0 else st["td"]) for c in row]
                    for r, row in enumerate(payload)]
            t = Table(data, colWidths=widths, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), G10),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, G50),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, G20),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story += [t, Spacer(1, 6)]
        elif kind == "diagram":
            caption = Paragraph(
                "Data flows left to right into Db2. Queries flow right to left: the UI calls the "
                "retriever, and the retriever calls <font face=\"%s\" size=\"7.4\">NEEDLE.TRIAGE</font> "
                "on the user's own connection, so RCAC applies to every call." % FM, st["caption"])
            story.append(KeepTogether([Spacer(1, 2), diagram(CONTENT_W), caption]))

    NumberedCanvas.footer_text = meta.get("footer", "")
    doc = BaseDocTemplate(
        str(out_path), pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
        title=f'{meta.get("title", "")} {meta.get("subtitle", "")}'.strip(),
        author=meta.get("team", ""), subject=meta.get("eyebrow", ""))
    frame = Frame(MARGIN_X, MARGIN_BOTTOM, CONTENT_W, PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame])])
    doc.build(story, canvasmaker=NumberedCanvas)


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", default=str(here / "NEEDLE_Proposal.md"))
    ap.add_argument("--out", default=str(here / "NEEDLE_Proposal.pdf"))
    ap.add_argument("--fonts", default=os.environ.get("NEEDLE_FONTS_DIR", str(here / "fonts")))
    args = ap.parse_args()
    plex = register_fonts(args.fonts)
    print(f"fonts: {'IBM Plex' if plex else 'Helvetica fallback'}")
    build(args.md, args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
