"""
Generates a PDF of the Round 1 Proposal for Db2 Sentinel AI.
"""

from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

DOCS_DIR = Path(__file__).resolve().parent
PDF_PATH = DOCS_DIR / "Round_1_Proposal_Db2_Sentinel_AI.pdf"
MD_PATH = DOCS_DIR / "Round_1_Proposal_Db2_Sentinel_AI.md"

def build_pdf():
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F62FE"),
    )
    sub_title_style = ParagraphStyle(
        "DocSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#393939"),
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#0F62FE"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#161616"),
        spaceAfter=6,
    )
    bullet_style = ParagraphStyle(
        "Bullet",
        parent=body_style,
        leftIndent=15,
        spaceAfter=4,
    )

    story = []

    # Title Banner
    story.append(Paragraph("IBM Db2Hack 2026 — Round 1 Proposal", sub_title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Db2 Sentinel AI: Autonomous Financial Crime Surveillance, Multi-Agent AML & Regulatory SAR Intelligence Platform", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Participant:</b> Soham (soham092510@gmail.com | GitHub: @soham-092510) &nbsp;|&nbsp; <b>Track:</b> AI Engineering", sub_title_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0F62FE"), spaceAfter=12))

    # Section 1
    story.append(Paragraph("1. Problem Statement", h2_style))
    story.append(Paragraph(
        "Global financial institutions face an estimated <b>$3.1 Trillion</b> in illicit money laundering and terrorist financing annually. "
        "While enterprise banking universally relies on <b>IBM Db2</b> for mission-critical core ledgers and high-throughput transactions, "
        "existing Anti-Money Laundering (AML) compliance tooling relies on brittle keyword rules and isolated point-solutions. This creates three critical failures: "
        "<br/>• <b>95% False-Positive Rate:</b> Compliance teams waste 80% of operational hours reviewing benign transactions."
        "<br/>• <b>Investigation Fatigue:</b> A single alert takes 4 to 6 hours of manual ledger querying, counterparty tracing, and document drafting."
        "<br/>• <b>Severe Regulatory Fines:</b> Missing statutory deadlines (FinCEN 30-day mandate, RBI STR guidelines) incurs billions in fines."
        "<br/>Crucially, existing AI attempts extract sensitive financial data into third-party vector databases, causing serious data privacy breaches (GDPR, PCI-DSS).",
        body_style
    ))

    # Section 2
    story.append(Paragraph("2. Proposed Solution & Key Features", h2_style))
    story.append(Paragraph(
        "<b>Db2 Sentinel AI</b> transforms IBM Db2 into an active, autonomous regulatory intelligence hub. It integrates <b>IBM Db2 12.1+ Native Vector Search</b>, "
        "<b>Recursive Common Table Expressions (CTEs)</b>, and <b>LangGraph cyclical multi-agent orchestration</b> to autonomously detect financial crime and compile "
        "legally compliant Suspicious Activity Reports (SARs) in <b>under 30 seconds</b>.",
        body_style
    ))
    story.append(Paragraph("• <b>In-Database Semantic Vector Matching:</b> Indexes FATF typologies using native Db2 <code>VECTOR(384, FLOAT32)</code> and <code>VECTOR_DISTANCE(..., 'COSINE')</code> within atomic transactions.", bullet_style))
    story.append(Paragraph("• <b>Recursive CTE Circular Flow Traversal:</b> Detects multi-hop circular fund routing (A &rarr; B &rarr; C &rarr; A) directly within IBM Db2 via SQL Common Table Expressions without external graph databases.", bullet_style))
    story.append(Paragraph("• <b>Window Velocity Analytics:</b> Employs Db2 window functions (<code>AVG OVER PARTITION</code>) to identify burst structuring patterns just below statutory reporting limits ($9,000–$9,999).", bullet_style))
    story.append(Paragraph("• <b>LangGraph Checkpoint Persistence in Db2:</b> Preserves intermediate agent states, tool outputs, and decisions in Db2 <code>AGENT_CHECKPOINTS</code> for ACID reliability, pause-and-resume workflows, and courtroom replayability.", bullet_style))
    story.append(Paragraph("• <b>Automated FinCEN / RBI SAR Filing:</b> Generates formal 5-part regulatory Suspicious Activity Reports with line-item citations to Db2 transaction record IDs.", bullet_style))
    story.append(Paragraph("• <b>Immutable Cryptographic Audit Trail:</b> Computes SHA-256 cryptographic signatures on all enforcement actions and stores them in the Db2 <code>AUDIT_TRAIL</code> table.", bullet_style))
    story.append(Paragraph("• <b>Dual-Mode Engine:</b> Operates natively on live IBM Db2 12.1+ (via <code>ibm_db</code> and SQLAlchemy <code>ibm_db_sa</code>), with an embedded zero-setup local emulation engine for instant reproducible evaluation.", bullet_style))

    # Section 3
    story.append(Paragraph("3. Selected Agentic AI Framework", h2_style))
    story.append(Paragraph(
        "<b>Framework:</b> <b>LangGraph</b> (Cyclical Multi-Agent StateGraph) & <b>LangChain Core</b>.<br/>"
        "<b>Orchestration Pipeline:</b><br/>"
        "1. <b>ScreeningAgent:</b> High-throughput rule & sanctions watchlist screening.<br/>"
        "2. <b>ForensicInvestigatorAgent:</b> Queries historical Db2 ledgers and performs native Db2 Vector similarity search.<br/>"
        "3. <b>GraphRiskAgent:</b> Recursive SQL CTE cycle discovery and network topology analysis.<br/>"
        "4. <b>SARDrafterAgent:</b> Auto-generates structured regulatory compliance filings.<br/>"
        "5. <b>SupervisorAgent:</b> Human-in-the-loop review, account freeze authorization, and cryptographic audit signing.",
        body_style
    ))

    # Section 4
    story.append(Paragraph("4. IBM Db2 Connector & Intended Integration", h2_style))
    story.append(Paragraph(
        "<b>Drivers & Connectors:</b> <code>ibm_db</code> (native C-driver bindings) and <code>ibm_db_sa</code> (SQLAlchemy dialect).<br/>"
        "<b>Db2 Capabilities Leveraged:</b> Native <code>VECTOR(384, FLOAT32)</code> column type; <code>VECTOR_DISTANCE(..., 'COSINE')</code>; "
        "<code>WITH RECURSIVE</code> Common Table Expressions; analytical window functions (<code>AVG OVER PARTITION</code>); "
        "transactional ACID locking; and temporal audit logging.",
        body_style
    ))

    # Section 5
    story.append(Paragraph("5. Proposed System Architecture & Workflow", h2_style))
    story.append(Paragraph(
        "<b>Workflow:</b> Inbound Wire Interception &rarr; <code>ScreeningAgent</code> (Db2 Watchlist & Threshold Check) "
        "&rarr; <code>ForensicInvestigatorAgent</code> (Db2 Vector Typology Matching) "
        "&rarr; <code>GraphRiskAgent</code> (Db2 Recursive CTE Loop Detection) "
        "&rarr; <code>SARDrafterAgent</code> (FinCEN/RBI Regulatory Narrative) "
        "&rarr; <code>SupervisorAgent</code> (Human Gatekeeper & Db2 Freeze) "
        "&rarr; <b>IBM Db2 12.1+ Ledger</b> (Checkpoints, Audit & SAR Storage).",
        body_style
    ))

    # Section 6
    story.append(Paragraph("6. Expected Impact & Enterprise Value", h2_style))
    story.append(Paragraph(
        "• <b>82% Reduction in False Positives:</b> Vector-grounded typology matching distinguishes routine commercial transfers from genuine structuring.<br/>"
        "• <b>90% Faster SAR Turnaround:</b> Generates complete, evidence-backed regulatory dossiers in under 30 seconds versus 4–6 hours of manual drafting.<br/>"
        "• <b>Zero Data Leakage:</b> Sensitive financial transactions and vectors remain inside IBM Db2's enterprise security boundary.<br/>"
        "• <b>Courtroom-Grade Auditability:</b> Every reasoning step and enforcement decision is immutably timestamped and cryptographically signed in Db2.",
        body_style
    ))

    doc.build(story)
    print(f"Generated PDF at {PDF_PATH}")

if __name__ == "__main__":
    build_pdf()
