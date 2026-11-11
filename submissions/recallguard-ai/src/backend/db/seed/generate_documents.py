#!/usr/bin/env python3
"""Generate the fictional evidence documents used by the demo (db/seed/documents/).

All organisations, people and report numbers are invented for demonstration.
Run: python db/seed/generate_documents.py
"""
from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).with_name("documents")

LAB_PAGES = [
    [
        "SAHYADRI ANALYTICAL FOOD LABORATORY (FICTIONAL - DEMO DOCUMENT)",
        "TEST REPORT",
        "Report No: SAFL-2026-11-0457    Issue date: 2026-11-10",
        "Client: Pune Sauce Works (FAC-PUN), Pune, Maharashtra",
        "SAMPLE DETAILS:",
        "Product: Tomato puree (28 Brix), aseptic drums",
        "Supplier: Valle Rosso Tomato Cooperative",
        "Supplier lot: TOM-2026-041 (received 2026-10-02)",
        "Samples: 5 x 250 g taken 2026-11-07 from retained drums D-07, D-11, D-15, D-19, D-23",
        "RESULTS:",
        "Salmonella spp. (ISO 6579-1): Detected in 25 g - 3 of 5 samples positive",
        "Serotyping: Salmonella Typhimurium confirmed (drums D-11, D-15, D-19)",
        "Enterobacteriaceae (ISO 21528-2): 2.4 x 10^3 cfu/g - exceeds limit of 10 cfu/g",
        "Listeria monocytogenes (ISO 11290-1): Not detected in 25 g",
        "pH: 4.6 (specification <= 4.4) - above limit",
        "CONCLUSION:",
        "Lot TOM-2026-041 is NON-COMPLIANT. Pathogen confirmed positive.",
        "Recommend immediate hold of all remaining stock and a recall assessment of products made with this lot.",
    ],
    [
        "SAHYADRI ANALYTICAL FOOD LABORATORY (FICTIONAL - DEMO DOCUMENT)",
        "Report No: SAFL-2026-11-0457 - page 2",
        "METHODS AND CHAIN OF CUSTODY:",
        "Samples received at laboratory 2026-11-07 17:40, temperature 4 C, seals intact.",
        "Enrichment in buffered peptone water, RVS and MKTTn broths; confirmation by serology and PCR.",
        "QUALITY STATEMENT:",
        "Results relate only to the samples tested. Uncertainty of measurement available on request.",
        "Authorised by: Dr. A. Kulkarni (fictional), Head - Microbiology",
    ],
]

TEXT_DOCS = {
    "coa_TOM-2026-041_valle_rosso.txt": """CERTIFICATE OF ANALYSIS (FICTIONAL - DEMO DOCUMENT)
Issued by: Valle Rosso Tomato Cooperative - Quality Assurance
Certificate: COA-VR-2026-1001    Date: 2026-10-01

PRODUCT
Tomato puree (28 Brix), lot TOM-2026-041, 2,400 kg in 10 aseptic drums

RESULTS
Salmonella spp.: Not detected in 25 g (n=1 composite)
Brix: 28.2
pH: 4.3
Total plate count: 1.1 x 10^2 cfu/g

STATEMENT
The lot meets the agreed specification and is released for dispatch.
""",
    "qc_pasteurisation_log_PB-2026-1001.txt": """QUALITY CONTROL RECORD (FICTIONAL - DEMO DOCUMENT)
Pune Sauce Works - Process QC
Record: QR-2026-0102    Date: 2026-10-04

BATCH
Tomato base concentrate PB-2026-1001 made from lot TOM-2026-041

PASTEURISATION LOG
Target hold temperature: >= 90 C for 10 min
14:10-14:16 hold temperature dipped to 84.1 C for 6 min (steam valve fault)
Operator extended hold by 4 min; deviation not escalated to QA

ASSESSMENT
Deviation outcome: inconclusive. Lethality not demonstrated for the dip period.
""",
    "supplier_certificate_SUP-001_fssc22000.txt": """SUPPLIER CERTIFICATE (FICTIONAL - DEMO DOCUMENT)
Certification scheme: FSSC 22000 version 6
Certified organisation: Valle Rosso Tomato Cooperative (SUP-001), Nashik, Maharashtra
Certificate number: DEMO-FSSC-0099
Valid from 2025-03-01 to 2028-02-28

SCOPE
Processing of tomatoes into aseptic tomato puree and paste.
""",
    "lab_report_CHI-2026-017.txt": """TEST REPORT (FICTIONAL - DEMO DOCUMENT)
Deccan Analytical Services
Report No: DAS-2026-09-0211    Issue date: 2026-09-12

SAMPLE
Red chili powder, supplier Deccan Spice Traders, lot CHI-2026-017

RESULTS
Salmonella spp.: Detected in 2 of 5 x 25 g samples (confirmed positive)
Aflatoxin B1: 3.1 ug/kg - within limit

CONCLUSION
Lot CHI-2026-017 non-compliant for Salmonella. Recall assessment recommended.
""",
    "notice_MLK-2026-233_presumptive.txt": """CONTAMINATION NOTICE (FICTIONAL - DEMO DOCUMENT)
Hosur Dairy & Bakery - QA alert
Date: 2026-11-02

SUBJECT
Skimmed milk powder lot MLK-2026-233 from Sahyadri Dairy Farms

FINDINGS
Presumptive Cronobacter spp. on enrichment from one retained sample.
Confirmation by PCR is pending at the external laboratory.

ACTION
Lot placed on hold. Batches PB-2026-1020 and PB-2026-1021 used this lot.
""",
}


def make_pdf(path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle("SAFL-2026-11-0457 Test Report (fictional)")
    w, h = A4
    for lines in LAB_PAGES:
        y = h - 60
        for i, line in enumerate(lines):
            heading = line.endswith(":") or line.isupper()
            c.setFont("Helvetica-Bold" if heading or i == 0 else "Helvetica", 12 if i == 0 else 10)
            if heading and i > 0:
                y -= 8
            c.drawString(50, y, line)
            y -= 18
        c.showPage()
    c.save()


def main() -> None:
    OUT.mkdir(exist_ok=True)
    make_pdf(OUT / "lab_report_TOM-2026-041.pdf")
    for name, text in TEXT_DOCS.items():
        (OUT / name).write_text(text, encoding="utf-8")
    print("wrote", sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
