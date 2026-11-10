# CatalogLens — 3–5 Minute Live Hackathon Demonstration Script

This script provides a structured walkthrough for demonstrating **CatalogLens** in a screen recording or live hackathon evaluation.

---

## ⏱️ Step 0: Pre-Flight Check (0:00 - 0:30)

1. Launch the backend API:
   ```bash
   uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```
2. Launch the Streamlit frontend:
   ```bash
   streamlit run frontend/app.py
   ```
3. Open your browser to `http://localhost:8501`.
4. Point out the **System Status** pills in the sidebar:
   - Mode: `Enterprise Demo` (or `Live Db2 LUW` if connected).
   - Db2 Driver: `Installed`.
   - Reasoning: deterministic fallback (Claude is optional and requires an API key).

---

## ⏱️ Step 1: Overview & Value Proposition (0:30 - 1:00)

1. Navigate to **"1. Overview"**.
2. **Narration:**
   > *"Welcome to CatalogLens. In enterprise environments, databases accumulate hundreds of tables over decades. Developers know how to write SQL, but they don't know what the tables actually mean, what relationships are undocumented, or what will break if they change a column.*
   > *Our core philosophy is simple: Don't just ask AI to explain a database. Give AI the evidence needed to understand it."*
3. Highlight the KPI metrics: **13 Tables**, **2 Views**, **100 Columns**, **15 Declared Relationships**, and **2 Inferred Relationship Candidates** (verified live Db2 figures).

---

## ⏱️ Step 2: Database Connection & SYSCAT Grounding (1:00 - 1:30)

1. Navigate to **"2. Database Connection"**.
2. **Narration:**
   > *"CatalogLens is deeply grounded in IBM Db2 LUW. It queries real Db2 system catalogs — SYSCAT.TABLES, COLUMNS, TABCONST, REFERENCES, and INDEXES.*
   > *Here in the connection dashboard, we can configure a live Db2 instance with host, port, database, and credentials, or connect to the configured live Db2 database. The supplied SQL scripts create a synthetic order-management schema for testing."*
3. Show the **"Test Db2 Live Connection"** button, explaining how it runs a verifiable query (`SELECT 1 FROM SYSIBM.SYSDUMMY1`) rather than fabricating success.

---

## ⏱️ Step 3: Schema Explorer (1:30 - 2:00)

1. Navigate to **"3. Schema Explorer"**.
2. Select table **`ORD_HDR`**.
3. **Narration:**
   > *"In the Schema Explorer, we see a normalized catalog representation. We have column data types, nullability, primary keys, and catalog comments from SYSCAT.TABLES REMARKS.*
   > *We can toggle to the Views tab to see `V_ACTIVE_ORDERS` and inspect its underlying SQL definition."*

---

## ⏱️ Step 4: Intelligent Relationship Discovery (2:00 - 2:45)

1. Navigate to **"4. Relationship Intelligence"**.
2. **Narration:**
   > *"This is where CatalogLens shines. Look at this interactive relationship graph.*
   > *The solid blue lines represent Declared Relationships — verified facts from SYSCAT.REFERENCES.*
   > *Notice the dashed orange lines: these are Inferred Relationships discovered by our deterministic heuristic engine."*
3. Point out **`RETURN_HDR`**:
   > *"Notice `RETURN_HDR`. In legacy enterprise systems, foreign keys are frequently omitted from the catalog. CatalogLens identified two candidate links: `RETURN_HDR.ORDER_ID` to `ORD_HDR.ORDER_ID`, and `RETURN_HDR.CUST_REF_NO` to `CUSTOMER_MST.CUST_ID`. These are heuristic inferences, not declared foreign keys, and should be verified by a database expert."*
4. Filter by **"Inferred Only"** to highlight the discovered candidate links.

---

## ⏱️ Step 5: AI Table Understanding & LangGraph Pipeline (2:45 - 3:45)

1. Navigate to **"5. AI Table Understanding"**.
2. Select table **`RETURN_HDR`**.
3. Click **"🚀 Run Agentic Investigation Pipeline"**.
4. Show the progress indicators executing each node of the LangGraph state machine:
   - `MetadataRetriever` &rarr; `SchemaAnalyzer` &rarr; `RelationshipInvestigator` &rarr; reasoning / fallback &rarr; `EvidenceValidator` &rarr; `ReportGenerator`.
5. Review the results:
   - **Likely Business Purpose:** Explains RMA return authorization filings.
   - **Column Breakdown:** Identifies status codes, monetary amounts, and legacy reference IDs.
   - **Evidence Ledger:** Expand the citations to show exact catalog sources (`SYSCAT.TABLES`, `SYSCAT.COLUMNS`).
   - **Uncertainties:** Explain that the inferred `ORDER_ID` link has no declared foreign-key constraint in the Db2 catalog.

---

## ⏱️ Step 6: Dependency Investigation & Change Blast Radius (3:45 - 4:30)

1. Navigate to **"7. Dependency Investigation"**.
2. Select **`ORD_HDR`** and column **`ORDER_ID`**.
3. Click **"🔎 Run Dependency & Impact Trace"**.
4. **Narration:**
   > *"Suppose a developer needs to modify `ORD_HDR.ORDER_ID`. What is the impact?*
   > *CatalogLens computes an impact severity of CRITICAL. It immediately identifies that 3 direct tables (`ORD_LINE`, `PAYMENT_TXN`, `SHIPMENT_HDR`) and 1 dependent view (`V_ACTIVE_ORDERS`) rely on this column.*
   > *It also traces indirect cascades to `SHIPMENT_ITEM` and provides an actionable pre-change checklist of manual checks to perform in the IBM Db2 Developer Extension for VS Code before applying any DDL."*

---

## ⏱️ Step 7: Conclusion & Wrap-Up (4:30 - 5:00)

1. Navigate to **"8. Architecture and About"**.
2. Show the system architecture diagram and LangGraph workflow.
3. Conclude:
   > *"CatalogLens transforms undocumented enterprise databases from black boxes into transparent, verifiable systems. Built for the IBM Db2 ecosystem, using a LangGraph investigation pipeline, deterministic analysis, and traceable evidence. Thank you!"*
