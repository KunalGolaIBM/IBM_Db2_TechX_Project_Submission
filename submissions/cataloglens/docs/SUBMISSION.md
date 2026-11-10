# Hackathon Submission: CatalogLens
## An Agentic System for Understanding Undocumented Enterprise Databases

---

### 1. Executive Summary

- **Project Title:** CatalogLens
- **Full Title:** CatalogLens — An Agentic System for Understanding Undocumented Enterprise Databases
- **Tagline:** Making the unknown structure of enterprise databases understandable.
- **Target Platform:** IBM Db2 LUW & IBM Db2 Developer Extension for Visual Studio Code
- **Core Technology Stack:** Python 3.10+, FastAPI, Pydantic, LangGraph, optional Anthropic Claude API integration, Streamlit, NetworkX, Plotly, IBM `ibm_db`

---

### 2. The Problem Statement

Enterprise databases in banking, logistics, insurance, and retail accumulate decades of schema migrations. They frequently exhibit:
1. **Unfamiliar Table and Column Names:** Abbreviations such as `ORD_HDR`, `PM_TXN`, and `RET_HDR` make schemas difficult to interpret.
2. **Missing Catalog Foreign Keys:** Some relationships are represented in application logic or conventions rather than declared as Db2 foreign-key constraints.
3. **Outdated or Absent Documentation:** The original engineers who built the system may have moved on, leaving limited explanations of the schema.
4. **High Risk of Breaking Changes:** Developers may struggle to identify downstream dependencies when modifying a table or column.

Conventional database development tools (such as table explorers and query consoles) allow developers to *query* a database, but they do nothing to help developers *understand* what the database represents or how its components fit together.

---

### 3. The Proposed Solution: CatalogLens

**CatalogLens** is an agentic database intelligence platform that connects directly to IBM Db2 system catalogs (`SYSCAT`) and transforms raw catalog metadata into an understandable, evidence-backed representation of the enterprise database.

#### Core Product Philosophy
> *"Don't just ask AI to explain a database. Give AI the evidence needed to understand it."*

CatalogLens is designed to distinguish **Verified Facts** (grounded in Db2 constraints), **Metadata-Supported Inferences** (candidate links based on column naming and type compatibility), and **AI-generated interpretations**. Inferred links are hypotheses and should be verified before being treated as schema facts.

---

### 4. Key Capabilities & Features

1. **Db2 Connection Dashboard & Verifiable Test:**
   - Real IBM Db2 connectivity using the official `ibm_db` driver.
   - Genuine connection verification (`SELECT 1 FROM SYSIBM.SYSDUMMY1`).
   - Built-in, 1-click **Enterprise Demonstration Database** containing a complete 13-table, 2-view synthetic order-management schema with intentional real-world ambiguities.

2. **Db2 Schema Explorer:**
   - Deep inspection of tables, views, data types, nullability, primary keys, foreign keys, indexes, check constraints, and `REMARKS` descriptions.

3. **Intelligent Relationship Discovery:**
   - Interactive force-directed network graph (NetworkX + Plotly).
   - Clear visual differentiation:
     - **Declared Relationships (Verified Facts):** Sourced directly from `SYSCAT.REFERENCES` and displayed as declared constraints (solid blue lines).
     - **Inferred Relationships (Candidate Hypotheses):** Identified using key-name matching, naming heuristics, and data type compatibility (shown separately from declared constraints). Any confidence value is a heuristic score, not a statistically calibrated probability.

4. **AI Table Understanding via LangGraph:**
   - Select any table to trigger an agentic 6-step LangGraph pipeline.
   - The pipeline generates an interpretation of likely business purpose, column significance, workflow role, and verification questions. The deterministic fallback is the currently verified path; Claude API reasoning is optional and has not been verified in the current environment.

5. **Traceable Evidence Ledger:**
   - The evidence ledger associates supported observations with relevant Db2 catalog metadata, including table, column, relationship, and index information.
   - Programmatic validation rejects any claim referencing non-existent tables or columns.

6. **Business Workflow Discovery:**
   - Identifies end-to-end business lifecycles (Order-to-Cash, Inventory Allocation & Replenishment, Customer Billing Vault, Reverse Logistics) with progression steps and enterprise uncertainties.

7. **Dependency & Impact Investigation:**
   - Traces direct and indirect cascading dependents for any table or column.
   - Computes an objective impact severity rating (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
   - Produces an actionable pre-migration checklist of manual checks.

---

### 5. Synergy with the IBM Db2 Ecosystem

CatalogLens is built to complement the **IBM Db2 Developer Extension for Visual Studio Code**:
- The **Db2 Developer Extension** is the developer's execution workbench for writing SQL, testing queries, and inspecting physical objects inside VS Code.
- **CatalogLens** is the developer's architectural copilot for understanding the schema, identifying unconstrained relationships, and assessing the blast radius of proposed DDL changes.
- Together, they form an end-to-end workflow: **Understand with CatalogLens &rarr; Execute and Verify with Db2 Developer Extension**.

---

### 6. Technical Excellence & Reliability

- **Db2 Integration:** Connects to a live Db2 LUW instance and reads schema information from Db2 system catalogs.
- **Deterministic Fallback:** Table interpretation has a deterministic fallback when an Anthropic API key is not configured. Live Claude-powered reasoning has not been verified in the current environment.
- **Automated Testing:** 24 unit and API tests pass offline. These tests validate application behavior without requiring a live Db2 connection.
- **Evidence Validation:** The application checks generated claims against available metadata; inferred relationships remain candidates for human verification.
