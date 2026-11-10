# MediTwin AI — 3–5 Minute Live Demonstration & Presentation Script

**Project:** MediTwin AI — Traceable Clinical Record Intelligence Platform  
**Target Event:** IBM Db2Hack 2026 Submission  
**Author:** Solo Builder (Vipul Mishra)  
**Total Target Time:** ~4 minutes 30 seconds  

---

## Overview & Demo Checklist Before Starting
- [x] Streamlit app ready to run (`streamlit run app.py`).
- [x] Synthetic PDF lab reports located in `sample_data/synthetic_reports/`.
- [x] Test suite fully passing (`python -m pytest -v`: 80/80 passed).
- [x] Sidebar visible with Db2 and Gemini connection badges.

---

## Walkthrough Script

### Act 1: The Problem & The MediTwin Architecture (0:00 – 0:50)
*Screen: Title slide / Streamlit Dashboard*

**Presenter Talking Points:**
> "Hello judges and team IBM. Today, clinical records are scattered across multi-page PDF lab reports, clinic notes, and patient portals. 
> 
> The standard AI approach—dumping clinical documents into a vector database and asking an LLM to chat about them—fails in healthcare. LLMs hallucinate numbers, invent dates, and fail to calculate reliable deltas between laboratory tests.
> 
> **MediTwin AI takes a fundamentally different, architecturally sound approach:**
> 1. **IBM Db2 Community Edition** is our single authoritative system of record.
> 2. The LLM is strictly used for language understanding and structured extraction, never for independent medical decision-making.
> 3. **Every observation requires human verification before entering the trusted timeline.**
> 4. All patient Q&A is strictly grounded in parameterized Db2 queries with complete document provenance—down to the exact page and source text snippet."

---

### Act 2: Live Ingestion & LangGraph State Machine (0:50 – 1:50)
*Action: Click on "📄 Document Upload" in the sidebar.*

**Presenter Talking Points:**
> "Let's demonstrate **Pipeline A: Document Ingestion**.
> 
> We select synthetic patient **Synthetic Patient Alpha (`DEMO-001`)** and choose our multi-page lab report `SyntheticReport_A_Oct2026.pdf`.
> 
> First, our ingestion pipeline executes a SHA-256 cryptographic hash check. This prevents duplicate document uploads during Streamlit reruns and ensures document integrity.
> 
> We click **Step 1: Register Document in Db2**, which stores the document metadata and extracted text.
> 
> Next, we click **Step 2: Run LangGraph Extraction Workflow**.
> 
> Watch the progress: LangGraph executes our compiled state machine across `classify_request` $\rightarrow$ `parse_document` $\rightarrow$ `extract_observations` $\rightarrow$ `validate_extraction` $\rightarrow$ `human_review_gate`.
> 
> All 9 laboratory tests—including HbA1c, Fasting Blood Sugar, Lipid panels, and Hemoglobin—are extracted and validated using strict Pydantic v2 schemas. Notice that every observation has its observation date, unit, reference range, page number, and source snippet preserved.
> 
> Critically: **These records are stored in IBM Db2 with `review_status = 'PENDING'`. They do NOT appear in the patient timeline yet.**"

---

### Act 3: Mandatory Human Review Gate (1:50 – 2:40)
*Action: Click on "✅ Human Review" in the sidebar.*

**Presenter Talking Points:**
> "Now let's switch to the **Human Verification Gate**.
> 
> As a clinical reviewer, I inspect each pending observation alongside its exact provenance card:
> - I see observation #1: HbA1c at 6.4% from page 1, with the exact verbatim text quote.
> - Suppose I need to correct a test code or adjust a numeric value. Even delicate values like floating-point `0.0` are handled without data loss.
> - When I click **Approve**, the update to `OBSERVATION` and the write to our `AUDIT_LOG` execute **within the exact same atomic transaction**.
> 
> What if an observation is flawed or voided? If I click **Reject**, that record is marked as `REJECTED`. 
> 
> Our system guarantees that **rejected observations are completely excluded from patient timelines, charts, and Q&A evidence sets**."

---

### Act 4: Deterministic Longitudinal Timeline & Metric Trends (2:40 – 3:30)
*Action: Click on "👤 Patient Workspace" in the sidebar.*

**Presenter Talking Points:**
> "Let's open the **Patient Workspace**.
> 
> Here, MediTwin AI constructs a chronological timeline of all approved events.
> 
> Notice our **Metric Trend Analysis**:
> - We select **HbA1c**. Our deterministic trend engine plots the readings over time using interactive Plotly charts.
> - It calculates the exact absolute change: for example, `-0.4 %`, and the percentage change `-5.56%`.
> - Unlike standard LLMs, this math is computed deterministically in Python—it cannot hallucinate differences.
> - Furthermore, our unit compatibility guard guarantees that disparate units (like `mg/dL` vs `mmol/L`) will never be erroneously compared without a verified conversion."

---

### Act 5: Evidence-Grounded Q&A & Safety Interception (3:30 – 4:20)
*Action: Click on "💬 Ask MediTwin" in the sidebar.*

**Presenter Talking Points:**
> "Now let's test **Pipeline B: Patient Intelligence**.
> 
> Let's click the example question: *'How did HbA1c change over time?'*
> 
> LangGraph routes this query:
> 1. It identifies the metric `HBA1C` without LLM SQL generation.
> 2. It executes a **parameterized Db2 prepared statement** using bound variables.
> 3. It retrieves only approved records.
> 4. Gemini synthesizes a grounded response citing the exact values, dates, and trends.
> 
> Below the answer, MediTwin AI displays **Structured Evidence Cards** for full auditability:
> - Test Name, Value, Unit, Date
> - Source document name
> - Source page number
> - Exact verbatim text snippet
> 
> Now let's test our **Safety and Boundaries**:
> 1. **Insufficient Evidence:** What if we ask: *'What was my Thyroid TSH level?'* when no approved TSH records exist? The system immediately returns the exact mandated response:
>    > *'I could not find sufficient approved records to answer this question.'*
> 2. **Clinical Boundary:** If a user asks for diagnostic advice or prescription recommendations, our `safety_check_node` intercepts it, reminding the user that MediTwin AI is an evidence organization tool, not a medical device."

---

### Act 6: Compliance Audit Log & Test Certification (4:20 – 4:50)
*Action: Click on "📋 Audit History" in the sidebar.*

**Presenter Talking Points:**
> "Finally, let's look at **Audit History**.
> 
> In healthcare, governance is essential. Every document upload, observation correction, approval, rejection, and query is logged in an immutable, append-only Db2 `AUDIT_LOG` table with timestamps and actor IDs.
> 
> Behind this platform is a comprehensive test suite of **80 tests across unit, security, integration, and end-to-end categories**, achieving a **100% pass rate** in under 1.6 seconds.
> 
> MediTwin AI demonstrates how IBM Db2 and agentic AI combine to deliver a trustworthy, auditable, and traceably grounded healthcare record intelligence platform.
> 
> Thank you."

---

## Judge Q&A Cheat Sheet

| Question | Answer |
| :--- | :--- |
| **Why not use vector search / RAG?** | Vector search retrieves fuzzy semantic text chunks that can omit critical lab dates or confuse measurements across visits. MediTwin AI parses laboratory reports into structured relational rows in IBM Db2, enabling deterministic sorting, exact trend calculation, and SQL-level patient isolation. |
| **How is SQL injection prevented?** | All queries use prepared statements with variable parameter binding (`?` parameter markers via `ibm_db`). Dynamic SQL string concatenation is strictly prohibited throughout the entire codebase. |
| **How do you guarantee the LLM doesn't hallucinate numbers?** | Trend mathematics (deltas, percentages) are computed deterministically in Python before being passed to Gemini. The LLM is restricted by prompt and post-generation validation to report only facts present in the retrieved database evidence cards. |
| **How is patient data isolated?** | Foreign keys and unique composite constraints (`fk_obs_doc_patient` on `(document_id, patient_id)`) at the Db2 database level prevent cross-patient referencing. |
| **What happens if Db2 is temporarily offline?** | The application handles offline connectivity gracefully, displaying a clear offline status badge and guidance without inventing mock database states. |

