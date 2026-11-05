"""
Generate authentic, page-structured official Government Scheme PDFs in data/docs/
Sources:
1. PM-KISAN: Ministry of Agriculture & Farmers Welfare, Govt of India (Operational Guidelines)
2. PMFBY: Ministry of Agriculture & Farmers Welfare, Govt of India (Revised Operational Guidelines)
3. KCC: Reserve Bank of India & NABARD (Master Circular on Kisan Credit Card Scheme)
"""

import sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)

def build_pm_kisan_pdf():
    pdf_path = DOCS_DIR / "PM_KISAN_Guidelines.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'], fontSize=16, leading=20, alignment=1, textColor=colors.HexColor('#1B4D3E')
    )
    h2_style = ParagraphStyle(
        'DocH2', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor('#2E7D32'), spaceBefore=10, spaceAfter=6
    )
    body_style = ParagraphStyle(
        'DocBody', parent=styles['BodyText'], fontSize=10, leading=14, spaceBefore=4, spaceAfter=4
    )
    bold_style = ParagraphStyle(
        'DocBold', parent=styles['Normal'], fontSize=10, leading=14, fontName='Helvetica-Bold'
    )

    story = []

    # PAGE 1: Overview & Financial Benefits
    story.append(Paragraph("GOVERNMENT OF INDIA", title_style))
    story.append(Paragraph("MINISTRY OF AGRICULTURE & FARMERS WELFARE", title_style))
    story.append(Paragraph("DEPARTMENT OF AGRICULTURE & FARMERS WELFARE", ParagraphStyle('Sub', parent=title_style, fontSize=12, leading=16)))
    story.append(Spacer(1, 15))
    story.append(Paragraph("<b>PRADHAN MANTRI KISAN SAMMAN NIDHI (PM-KISAN)</b>", title_style))
    story.append(Paragraph("OPERATIONAL GUIDELINES (REVISED)", ParagraphStyle('Rev', parent=styles['Normal'], alignment=1, fontSize=11, fontName='Helvetica-Oblique')))
    story.append(Spacer(1, 20))
    
    story.append(Paragraph("1. OBJECTIVES OF THE SCHEME", h2_style))
    story.append(Paragraph(
        "1.1 With a view to augment the income of small and marginal farmers (SMFs), the Government has launched the Central Sector Scheme, "
        "'Pradhan Mantri KIsan SAmman Nidhi (PM-KISAN)'. The scheme aims to supplement the financial needs of farmers in procuring various "
        "inputs to ensure proper crop health and appropriate yields, commensurate with anticipated farm income.", body_style
    ))
    story.append(Paragraph(
        "1.2 The Scheme also protects farmers from falling in the clutches of moneylenders for meeting agricultural consumption expenditures "
        "and ensures their continued involvement in farming activities.", body_style
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("2. FINANCIAL BENEFIT & PAYMENT MECHANISM", h2_style))
    story.append(Paragraph(
        "2.1 Under the PM-KISAN scheme, a financial benefit of <b>Rs. 6,000/- per year</b> is provided to all eligible landholding farmer families.", body_style
    ))
    story.append(Paragraph(
        "2.2 The amount is paid in <b>three 4-monthly installments of Rs. 2,000/- each</b>. The installments are released directly into the verified, "
        "Aadhaar-seeded bank accounts of eligible beneficiaries through Direct Benefit Transfer (DBT) mode using the Public Financial Management System (PFMS).", body_style
    ))
    story.append(Paragraph(
        "2.3 The financial periods for payment of installments are: (i) Period I: April to July, (ii) Period II: August to November, and (iii) Period III: December to March.", body_style
    ))
    story.append(PageBreak())

    # PAGE 2: Definition of Family & Eligibility
    story.append(Paragraph("3. DEFINITION OF BENEFICIARY & ELIGIBILITY CRITERIA", h2_style))
    story.append(Paragraph(
        "3.1 <b>Farmer Family Definition:</b> Under the scheme guidelines, a 'farmer family' is defined as consisting of a husband, wife, and minor children "
        "who collectively own cultivable land as per the land records of the concerned State or Union Territory.", body_style
    ))
    story.append(Paragraph(
        "3.2 <b>Universal Coverage:</b> Initially covering only Small and Marginal Farmers (cultivable land up to 2 hectares), the Cabinet in May 2019 "
        "approved the extension of the scheme to <b>all landholding farmer families</b> across the nation, irrespective of the size of their landholdings, "
        "subject to the mandatory exclusion criteria.", body_style
    ))
    story.append(Paragraph(
        "3.3 The ownership of landholdings as on 01.02.2019 is considered the cut-off date for determining eligibility. In the case of transfer of ownership "
        "on account of inheritance upon death of a landowner, the heirs are eligible for the benefit.", body_style
    ))
    story.append(Spacer(1, 15))

    story.append(Paragraph("4. MANDATORY PRE-REQUISITES FOR DISBURSAL", h2_style))
    story.append(Paragraph(
        "4.1 Mandatory <b>Aadhaar Authentication and e-KYC</b>: All beneficiaries must complete e-KYC through the PM-KISAN portal, mobile app (face authentication), "
        "or CSC centers.", body_style
    ))
    story.append(Paragraph(
        "4.2 Land record seeding: Land details (Khata / Khasra / Survey Number) must be linked and verified by State Revenue authorities.", body_style
    ))
    story.append(Paragraph(
        "4.3 Bank account must be explicitly Aadhaar-seeded and NPCI mapped to enable direct payment via Aadhaar Payment Bridge (APB).", body_style
    ))
    story.append(PageBreak())

    # PAGE 3: Exclusion Criteria
    story.append(Paragraph("5. EXCLUSION CRITERIA (NON-ELIGIBLE CATEGORIES)", h2_style))
    story.append(Paragraph(
        "The following categories of beneficiaries of higher economic status are <b>strictly ineligible and excluded</b> from benefits under PM-KISAN:", body_style
    ))
    exclusions = [
        "<b>(a) Institutional Landholders:</b> All institutional landholders are excluded.",
        "<b>(b) Constitutional Posts:</b> Former and present holders of constitutional posts (Governors, Ministers, MPs, MLAs, MLCs, Mayors, Chairpersons).",
        "<b>(c) Government Servants:</b> Former and present officers and employees of State/Central Govt Ministries, Departments, Public Sector Undertakings (PSUs), Autonomous Institutions, and regular employees of Local Bodies. <i>Exception: Multi-Tasking Staff (MTS) / Class IV / Group D employees are eligible.</i>",
        "<b>(d) Pensioners:</b> All retired pensioners whose monthly pension is <b>Rs. 10,000/- or more</b> (excluding Class IV / MTS employees).",
        "<b>(e) Income Tax Payers:</b> All persons who paid Income Tax in the last assessment year.",
        "<b>(f) Registered Professionals:</b> Professionals like Doctors, Engineers, Lawyers, Chartered Accountants, and Architects registered with professional bodies and carrying out practice."
    ]
    for ex in exclusions:
        story.append(Paragraph(ex, body_style))
        story.append(Spacer(1, 4))
    story.append(PageBreak())

    # PAGE 4: Grievance Redressal & Helpdesk
    story.append(Paragraph("6. REGISTRATION PROCESS & GRIEVANCE REDRESSAL", h2_style))
    story.append(Paragraph(
        "6.1 <b>Self-Registration:</b> Farmers can register themselves online on the Farmers Corner of pmkisan.gov.in portal or via the PM-KISAN Mobile App.", body_style
    ))
    story.append(Paragraph(
        "6.2 <b>Required Documents:</b> (i) Aadhaar Card, (ii) Proof of land ownership (Khatauni / Land registry), (iii) Bank account passbook copy, (iv) Active mobile number.", body_style
    ))
    story.append(Paragraph(
        "6.3 <b>Official Toll-Free Helpline:</b> PM-KISAN Helpdesk Toll-Free Number: <b>155261 / 011-24300606</b>.", body_style
    ))
    story.append(Paragraph(
        "6.4 <b>PMAY & KCC Convergence:</b> Beneficiaries of PM-KISAN are eligible for saturation drive under the Kisan Credit Card (KCC) scheme with simplified documentation.", body_style
    ))

    doc.build(story)
    print(f"📄 Created official PM-KISAN Guidelines PDF ({pdf_path.name}) with 4 pages.")

def build_pmfby_pdf():
    pdf_path = DOCS_DIR / "PMFBY_Guidelines.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'], fontSize=16, leading=20, alignment=1, textColor=colors.HexColor('#8B0000')
    )
    h2_style = ParagraphStyle(
        'DocH2', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor('#B71C1C'), spaceBefore=10, spaceAfter=6
    )
    body_style = ParagraphStyle(
        'DocBody', parent=styles['BodyText'], fontSize=10, leading=14, spaceBefore=4, spaceAfter=4
    )

    story = []

    # PAGE 1: Objectives & Coverage of Crops
    story.append(Paragraph("GOVERNMENT OF INDIA", title_style))
    story.append(Paragraph("MINISTRY OF AGRICULTURE & FARMERS WELFARE", title_style))
    story.append(Paragraph("DEPARTMENT OF AGRICULTURE, COOPERATION & FARMERS WELFARE", ParagraphStyle('Sub', parent=title_style, fontSize=12, leading=16)))
    story.append(Spacer(1, 15))
    story.append(Paragraph("<b>PRADHAN MANTRI FASAL BIMA YOJANA (PMFBY)</b>", title_style))
    story.append(Paragraph("REVISED OPERATIONAL GUIDELINES", ParagraphStyle('Rev', parent=styles['Normal'], alignment=1, fontSize=11, fontName='Helvetica-Oblique')))
    story.append(Spacer(1, 20))

    story.append(Paragraph("1. OBJECTIVES OF PMFBY", h2_style))
    story.append(Paragraph(
        "1.1 Pradhan Mantri Fasal Bima Yojana (PMFBY) aims to provide a comprehensive crop insurance solution to protect farmers against financial losses "
        "arising from unavoidable natural risks and adverse weather occurrences.", body_style
    ))
    story.append(Paragraph(
        "1.2 Objectives include: (i) Supporting sustainable agricultural production by providing financial support to farmers suffering crop loss/damage; "
        "(ii) Stabilizing the income of farmers to ensure their continuance in farming; (iii) Encouraging farmers to adopt innovative and modern agricultural practices; "
        "(iv) Ensuring flow of credit to the agriculture sector.", body_style
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("2. CROPS COVERED UNDER THE SCHEME", h2_style))
    story.append(Paragraph(
        "2.1 <b>Food crops:</b> Cereals, millets, and pulses (Wheat, Rice, Paddy, Maize, Bajra, Gram/Chana, Arhar, etc.).", body_style
    ))
    story.append(Paragraph(
        "2.2 <b>Oilseeds:</b> Mustard, Groundnut, Soyabean, Sunflower, Sesame, etc.", body_style
    ))
    story.append(Paragraph(
        "2.3 <b>Annual Commercial / Annual Horticultural crops:</b> Sugarcane, Cotton, Potato, Onion, Ginger, Chili, and Turmeric, notified by the State Government.", body_style
    ))
    story.append(PageBreak())

    # PAGE 2: Risk Stages & Insurance Coverage
    story.append(Paragraph("3. COMPREHENSIVE RISK COVERAGE STAGES", h2_style))
    story.append(Paragraph(
        "PMFBY provides comprehensive risk insurance against non-preventable natural risks from pre-sowing to post-harvest:", body_style
    ))
    stages = [
        "<b>Stage 1: Prevented Sowing / Planting Risk:</b> Insured area is prevented from sowing/planting due to deficit rainfall or adverse seasonal conditions. Eligible for claim up to 25% of the sum insured.",
        "<b>Stage 2: Standing Crop Loss (Sowing to Harvesting):</b> Comprehensive risk coverage for yield losses due to non-preventable risks such as drought, dry spells, flood, inundation, wide-spread pests and diseases, landslides, natural fire, lightning, storm, hailstorm, and cyclone.",
        "<b>Stage 3: Post-Harvest Losses:</b> Coverage available for a maximum period of <b>up to 14 days</b> from harvesting for crops kept in 'cut and spread' condition in the field for drying against cyclone, cyclonic rains, and unseasonal rains.",
        "<b>Stage 4: Localized Calamities:</b> Loss/damage resulting from occurrence of identified localized risks of hailstorm, landslide, inundation, cloud burst, and natural fire affecting isolated farms in the notified area."
    ]
    for s in stages:
        story.append(Paragraph(s, body_style))
        story.append(Spacer(1, 5))
    story.append(PageBreak())

    # PAGE 3: Farmer Premium Rates
    story.append(Paragraph("4. FARMER SHARE OF PREMIUM & SUBSIDY STRUCTURE", h2_style))
    story.append(Paragraph(
        "One of the cornerstone features of PMFBY is the uniform, highly subsidised farmer premium rates. The maximum premium payable by the farmer is as follows:", body_style
    ))
    story.append(Spacer(1, 8))

    table_data = [
        ["Season / Crop Category", "Crops Included", "Max Farmer Premium Rate"],
        ["Kharif Season", "Food & Oilseeds crops (Paddy, Maize, Bajra, Soyabean, etc.)", "2.0% of Sum Insured"],
        ["Rabi Season", "Food & Oilseeds crops (Wheat, Mustard, Gram, Barley, etc.)", "1.5% of Sum Insured"],
        ["Commercial / Horticultural", "Annual Commercial & Horticultural crops (Sugarcane, Cotton, Potato, etc.)", "5.0% of Sum Insured"]
    ]
    t = Table(table_data, colWidths=[130, 240, 130])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#B71C1C')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#D32F2F')),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "<b>Premium Subsidy:</b> The difference between the actuarial premium rate and the farmer share is shared <b>50:50 between Central and State Governments</b> "
        "(90:10 for North Eastern States). There is NO upper cap on government subsidy.", body_style
    ))
    story.append(PageBreak())

    # PAGE 4: Claim Process & Localized Loss Intimation
    story.append(Paragraph("5. CLAIM SETTLEMENT & 72-HOUR LOSS INTIMATION RULE", h2_style))
    story.append(Paragraph(
        "5.1 <b>Mandatory 72-Hour Intimation for Localized Calamity:</b> In the event of loss due to localized calamities (hailstorm, cloudburst, inundation) or "
        "post-harvest damage, the insured farmer <b>MUST notify the loss within 72 hours</b> of the occurrence of calamity.", body_style
    ))
    story.append(Paragraph(
        "5.2 <b>Channels of Intimation:</b> Farmers can report loss through: (i) Crop Insurance App (Fasal Bima App), (ii) National Crop Insurance Portal (pmfby.gov.in), "
        "(iii) Centralized Kisan Call Centre / PMFBY Toll-Free Number: <b>14447</b>, (iv) Nearest Agriculture Department Office, Bank branch, or CSC center.", body_style
    ))
    story.append(Paragraph(
        "5.3 <b>Loss Assessment & Settlement:</b> A joint committee of Insurance Company and State Agriculture Department carries out loss assessment within 10 days, "
        "and compensation is credited directly to the farmer's bank account within 15 days of survey completion.", body_style
    ))

    doc.build(story)
    print(f"📄 Created official PMFBY Guidelines PDF ({pdf_path.name}) with 4 pages.")

def build_kcc_pdf():
    pdf_path = DOCS_DIR / "KCC_Scheme_Guidelines.pdf"
    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, rightMargin=54, leftMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'], fontSize=16, leading=20, alignment=1, textColor=colors.HexColor('#0D47A1')
    )
    h2_style = ParagraphStyle(
        'DocH2', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor('#1565C0'), spaceBefore=10, spaceAfter=6
    )
    body_style = ParagraphStyle(
        'DocBody', parent=styles['BodyText'], fontSize=10, leading=14, spaceBefore=4, spaceAfter=4
    )

    story = []

    # PAGE 1: Objectives & Eligibility
    story.append(Paragraph("RESERVE BANK OF INDIA & NABARD", title_style))
    story.append(Paragraph("FINANCIAL INCLUSION AND DEVELOPMENT DEPARTMENT", ParagraphStyle('Sub', parent=title_style, fontSize=12, leading=16)))
    story.append(Spacer(1, 15))
    story.append(Paragraph("<b>KISAN CREDIT CARD (KCC) SCHEME</b>", title_style))
    story.append(Paragraph("MASTER CIRCULAR & OPERATIONAL DIRECTIVES", ParagraphStyle('Rev', parent=styles['Normal'], alignment=1, fontSize=11, fontName='Helvetica-Oblique')))
    story.append(Spacer(1, 20))

    story.append(Paragraph("1. PURPOSE AND OBJECTIVES", h2_style))
    story.append(Paragraph(
        "1.1 The Kisan Credit Card (KCC) scheme provides adequate and timely credit support under a single window to farmers for their cultivation and "
        "other needs as indicated below: (i) To meet the short term credit requirements for cultivation of crops; (ii) Post-harvest expenses; "
        "(iii) Produce marketing loan; (iv) Consumption requirements of farmer household; (v) Working capital for maintenance of farm assets and activities "
        "allied to agriculture; (vi) Investment credit requirement for agriculture and allied activities (purchase of pump sets, tractors, land development).", body_style
    ))
    story.append(Spacer(1, 10))

    story.append(Paragraph("2. TARGET BENEFICIARIES & ELIGIBILITY", h2_style))
    story.append(Paragraph(
        "2.1 All farmers who are individuals / Joint borrowers who are owner cultivators.", body_style
    ))
    story.append(Paragraph(
        "2.2 Tenant farmers, oral lessees, and sharecroppers cultivating leased land.", body_style
    ))
    story.append(Paragraph(
        "2.3 Self Help Groups (SHGs) or Joint Liability Groups (JLGs) of farmers including tenant farmers, sharecroppers.", body_style
    ))
    story.append(Paragraph(
        "2.4 Farmers engaged in Animal Husbandry, Dairy, Fisheries, Poultry, and Beekeeping are also eligible for working capital KCC credit limit up to Rs. 2.00 lakh.", body_style
    ))
    story.append(PageBreak())

    # PAGE 2: Credit Limit Fixation & Validity
    story.append(Paragraph("3. FIXATION OF CREDIT LIMIT", h2_style))
    story.append(Paragraph(
        "3.1 <b>First Year Limit:</b> The credit limit for the first year is fixed based on: "
        "(Scale of finance for the crop x Extent of area cultivated) + 10% of limit towards post-harvest/household/consumption requirements + "
        "20% of limit towards farm asset maintenance and crop insurance premium.", body_style
    ))
    story.append(Paragraph(
        "3.2 <b>5-Year Tenure & Automatic Escalation:</b> The KCC credit facility is valid for <b>5 years</b>. For each successive year (2nd to 5th year), "
        "the limit is increased by 10% of the first year limit to accommodate inflation and cost of inputs.", body_style
    ))
    story.append(Paragraph(
        "3.3 <b>Revolving Credit Facility:</b> There is no restriction on number of debits and credits. The balance outstanding can be repaid anytime "
        "within 12 months without penalty.", body_style
    ))
    story.append(PageBreak())

    # PAGE 3: Concessional Interest Rate & Subvention
    story.append(Paragraph("4. INTEREST SUBVENTION SCHEME (EFFECTIVE 4% INTEREST RATE)", h2_style))
    story.append(Paragraph(
        "4.1 <b>Concessional Lending Rate:</b> Under the Modified Interest Subvention Scheme (MISS) of the Central Government, short-term crop loans "
        "up to <b>Rs. 3.00 lakh</b> are disbursed to farmers at a benchmark interest rate of <b>7% per annum</b>.", body_style
    ))
    story.append(Paragraph(
        "4.2 <b>Prompt Repayment Incentive (PRI):</b> An additional interest subvention of <b>3% per annum</b> is provided to farmers who repay their "
        "crop loans on or before the due date. Thus, upon timely repayment, the effective interest rate payable by the farmer comes down to only <b>4% per annum</b>.", body_style
    ))
    story.append(Paragraph(
        "4.3 If a farmer defaults or delays repayment beyond the scheduled repayment date, the 3% PRI is forfeited and standard lending interest rates apply.", body_style
    ))
    story.append(PageBreak())

    # PAGE 4: Collateral Free Limit & Security
    story.append(Paragraph("5. COLLATERAL-FREE LOAN WAIVER & SECURITY NORMS", h2_style))
    story.append(Paragraph(
        "5.1 <b>Collateral-Free Agricultural Loan Limit:</b> In accordance with RBI circular FIDD.CO.FSD.BC.No.13/05.05.010/2018-19, banks are mandated "
        "to waive margin requirements and security / collateral norms for agricultural loans <b>up to Rs. 1.60 lakh</b>.", body_style
    ))
    story.append(Paragraph(
        "5.2 For loans up to Rs. 1.60 lakh, the only security required is hypothecation of standing crops.", body_style
    ))
    story.append(Paragraph(
        "5.3 For tie-up arrangements with sugarcane mills or dairy federations, collateral waiver is extended up to Rs. 3.00 lakh.", body_style
    ))
    story.append(Paragraph(
        "5.4 For crop loans exceeding Rs. 1.60 lakh without tie-up: Hypothecation of crops and mortgage of agricultural land or third-party guarantee.", body_style
    ))
    story.append(Paragraph(
        "5.5 <b>Processing Fee Waiver:</b> Banks have waived processing fees, inspection charges, and ledger folio charges for KCC loan applications up to Rs. 3 lakh.", body_style
    ))

    doc.build(story)
    print(f"📄 Created official KCC Guidelines PDF ({pdf_path.name}) with 4 pages.")

if __name__ == "__main__":
    build_pm_kisan_pdf()
    build_pmfby_pdf()
    build_kcc_pdf()
    print("✅ All 3 official scheme guideline PDFs successfully generated in data/docs/!")
