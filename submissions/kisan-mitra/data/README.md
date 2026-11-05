# Kisan Mitra (किसान मित्र) - Dataset Provenance & Licensing Documentation

This directory contains real, official government agricultural data and policy documents used by **Kisan Mitra** for Text-to-SQL price intelligence and native Db2 Vector RAG retrieval.

---

## 1. Mandi Market Prices Dataset (`mandi_prices_snapshot.csv`)

| Attribute | Details |
| :--- | :--- |
| **Dataset Title** | Current Daily Price of Various Commodities from Various Markets (Mandi) |
| **Source Authority** | AGMARKNET, Directorate of Marketing & Inspection (DMI), Ministry of Agriculture & Farmers Welfare |
| **Portal** | Open Government Data (OGD) Platform India ([data.gov.in](https://data.gov.in)) |
| **Resource ID** | `9ef84268-d588-465a-a308-a864a43d0070` |
| **API Endpoint** | `https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070` |
| **Retrieval Date** | 04 November 2026 |
| **License** | **Government Open Data License - India (GODL-India)** |
| **Geographic Coverage** | Primary focus on Uttar Pradesh (Mathura, Agra, Aligarh, Hathras, Lucknow, Kanpur, Meerut, Varanasi, Bareilly, Gorakhpur, Jhansi, Prayagraj, Ayodhya, Muzaffarnagar) with key benchmark markets in Punjab, Haryana, MP, Rajasthan, and Maharashtra. |
| **Key Commodities** | Potato (Aloo), Wheat (Gehun), Mustard (Sarson), Onion (Pyaz), Tomato (Tamatar), Rice/Paddy (Dhan/Chawal), Gram (Chana), Sugarcane (Ganna), Bajra, Soyabean. |

### Schema & Units:
- `state`: State name (e.g., `Uttar Pradesh`)
- `district`: District name (e.g., `Mathura`)
- `market`: Mandi name (e.g., `Mathura`, `Kosi Kalan`)
- `commodity`: Agricultural produce name (e.g., `Potato`)
- `variety`: Variety grade (e.g., `Desi`, `Dara`, `Black`, `Hybrid`)
- `arrival_date`: Date of market arrival (`YYYY-MM-DD`)
- `min_price`: Minimum arrival price (₹ per Quintal / 100 kg)
- `max_price`: Maximum arrival price (₹ per Quintal / 100 kg)
- `modal_price`: Most frequently traded price (₹ per Quintal / 100 kg)

---

## 2. Official Government Scheme Guidelines (`docs/`)

The documents in `data/docs/` are verbatim official policy manuals and operational guidelines issued by the Government of India and the Reserve Bank of India.

### Document 1: PM-KISAN Operational Guidelines (`PM_KISAN_Guidelines.pdf`)
- **Scheme**: Pradhan Mantri Kisan Samman Nidhi (PM-KISAN)
- **Issuing Authority**: Department of Agriculture & Farmers Welfare, Ministry of Agriculture & Farmers Welfare, Government of India
- **Source Portal**: [pmkisan.gov.in](https://pmkisan.gov.in)
- **Retrieval Date**: November 2026
- **License**: Government Open Data License - India (GODL-India)
- **Key Coverage**:
  - Income support of ₹6,000/- per year in three 4-monthly installments of ₹2,000/- via DBT.
  - Eligibility: All landholder farmer families having cultivable land in their names.
  - Exclusion Criteria: Institutional landholders, constitutional post holders, serving/retired government officers (Group A/B/C), income-tax payers, and certified professionals (doctors, engineers, lawyers, CAs).
  - e-KYC and Aadhaar-seeded bank account requirements.

### Document 2: PMFBY Revised Operational Guidelines (`PMFBY_Guidelines.pdf`)
- **Scheme**: Pradhan Mantri Fasal Bima Yojana (PMFBY)
- **Issuing Authority**: Department of Agriculture, Cooperation and Farmers Welfare, Ministry of Agriculture & Farmers Welfare, Government of India
- **Source Portal**: [pmfby.gov.in](https://pmfby.gov.in)
- **Retrieval Date**: November 2026
- **License**: Government Open Data License - India (GODL-India)
- **Key Coverage**:
  - Comprehensive risk insurance for food crops, oilseeds, and annual commercial/horticultural crops.
  - Farmer premium caps: 2.0% for Kharif food/oilseeds, 1.5% for Rabi food/oilseeds, and 5.0% for commercial/horticultural crops.
  - Balance actuarial premium subsidized equally (50:50) by Central and State Governments.
  - Loss assessment protocols: localized calamities (hailstorm, landslide, inundation, cloudburst) require mandatory reporting within 72 hours via the Crop Insurance App or toll-free helpline (14447).
  - Post-harvest loss coverage up to 14 days for crops kept in 'cut & spread' condition in fields.

### Document 3: Kisan Credit Card Scheme Master Guidelines (`KCC_Scheme_Guidelines.pdf`)
- **Scheme**: Kisan Credit Card (KCC) Scheme
- **Issuing Authority**: Reserve Bank of India (RBI) & National Bank for Agriculture and Rural Development (NABARD)
- **Source Portal**: [rbi.org.in](https://rbi.org.in) / [agricoop.nic.in](https://agricoop.nic.in)
- **Retrieval Date**: November 2026
- **License**: Government Open Data License - India (GODL-India)
- **Key Coverage**:
  - Flexible credit delivery mechanism for crop cultivation, post-harvest expenses, produce marketing, working capital for farm maintenance, and allied activities (dairy, fishery, animal husbandry).
  - Concessional short-term crop loans up to ₹3.00 lakh at 7% per annum interest subvention, with additional 3% Prompt Repayment Incentive (PRI), reducing effective interest to **4% per annum**.
  - Collateral-free agricultural loan limit waived up to ₹1.60 lakh.
  - Validity: 5 years with annual review and flexible revolving cash credit limit.

---

## 3. Licensing Information

All data and documents utilized in this project are published by the Government of India under the **Government Open Data License - India (GODL-India)**:
- Users are granted a worldwide, royalty-free, perpetual, non-exclusive license to use, adapt, publish, and translate the data for commercial and non-commercial purposes.
- Attribution to the respective Ministries (Ministry of Agriculture & Farmers Welfare, Reserve Bank of India, and data.gov.in) is preserved.
