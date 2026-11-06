"""
Report Exporter utility for Db2 Sentinel AI.
Exports Suspicious Activity Reports (SAR) to formatted Markdown and PDF documents.
"""

from pathlib import Path
from typing import Dict, Any


def export_sar_to_markdown(narrative: str, output_path: Path) -> Path:
    """Writes the SAR narrative to a formatted Markdown file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(narrative)
    return output_path


def export_sar_to_pdf(narrative: str, output_path: Path) -> Path:
    """Attempts to export the SAR report to PDF using reportlab."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(str(output_path), pagesize=letter)
        width, height = letter
        y = height - 50

        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "CONFIDENTIAL REGULATORY FILING: SUSPICIOUS ACTIVITY REPORT")
        y -= 25

        c.setFont("Courier", 9)
        for line in narrative.split("\n"):
            if y < 50:
                c.showPage()
                c.setFont("Courier", 9)
                y = height - 50
            c.drawString(50, y, line[:95])
            y -= 12

        c.save()
        return output_path
    except Exception:
        # Fallback to .txt / .md if reportlab fails
        fallback_path = output_path.with_suffix(".txt")
        with open(fallback_path, "w", encoding="utf-8") as f:
            f.write(narrative)
        return fallback_path
