"""
Architecture and About Page.
Explains the technical design, agentic framework, Db2 integration,
and Db2 Developer Extension synergy.
"""
import streamlit as st


def show_architecture_page():
    st.markdown("## 🏛️ System Architecture & Engineering Principles")
    st.markdown("Comprehensive overview of CatalogLens technical design, Db2 catalog integration, and agentic reasoning workflow.")

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "System Architecture",
        "LangGraph Workflow",
        "IBM Db2 & VS Code Extension Synergy",
        "Evidence Validation Ledger",
    ])

    with tab1:
        st.markdown("### 🧩 High-Level Architecture")
        st.markdown(
            """
            CatalogLens employs a decoupled, multi-tier architecture:
            - **Backend:** FastAPI REST API hosting deterministic analysis engines and LangGraph workflows.
            - **Database Layer:** Real connection manager using the official `ibm_db` driver querying Db2 LUW `SYSCAT` views.
            - **Reasoning Layer:** Deterministic heuristic fallback, with optional Anthropic Claude integration and structured output validation.
            - **Frontend:** Streamlit enterprise dashboard with Plotly force-directed graphs and responsive evidence ledgers.
            """
        )
        st.code(
            """
+-------------------------------------------------------------+
|                 Streamlit Frontend Dashboard                |
|  (Connection, Explorer, Relationship Graph, Evidence Views)  |
+------------------------------+------------------------------+
                               | REST / HTTP
                               v
+-------------------------------------------------------------+
|                     FastAPI Backend API                     |
|  (/health, /metadata, /tables, /relationships, /analyze)    |
+------------------------------+------------------------------+
                               |
        +----------------------+----------------------+
        |                                             |
        v                                             v
+-----------------------------+         +-----------------------------+
|   Deterministic Engines     |         |   LangGraph Agentic Graph   |
| - RelationshipDetector      |         | - MetadataRetriever         |
| - DependencyAnalyzer        |         | - SchemaAnalyzer            |
| - WorkflowDetector          |         | - RelationshipInvestigator  |
| - EvidenceService           |         | - Reasoning Engine          |
+--------------+--------------+         | - EvidenceValidator         |
               |                        | - ReportGenerator           |
               v                        +--------------+--------------+
+-----------------------------+                        |
|   IBM Db2 Connection &      |                        v
|   SYSCAT Catalog Extractor  |         +-----------------------------+
| (SYSCAT.TABLES, COLUMNS,    |         |   Optional Claude API       |
|  REFERENCES, TABCONST, etc.)|         |   (requires API key)        |
+-----------------------------+         +-----------------------------+
            """,
            language="text",
        )

    with tab2:
        st.markdown("### 🧠 Typed LangGraph State Machine")
        st.markdown(
            """
            Rather than simulating artificial chat between generic agents, CatalogLens uses a purposeful,
            typed LangGraph workflow with strict separation of concerns:
            1. **MetadataRetriever:** Queries SYSCAT metadata for the table and its schema.
            2. **SchemaAnalyzer:** Compiles table metrics, primary keys, and baseline facts.
            3. **RelationshipInvestigator:** Discovers declared foreign keys and candidate inferred links.
            4. **Reasoning Engine:** Produces hypotheses using deterministic heuristics; optional Claude integration can provide additional semantic analysis.
            5. **EvidenceValidator:** Deterministically validates all references, penalizing hallucinations.
            6. **ReportGenerator:** Assembles the final structured report.
            """
        )

    with tab3:
        st.markdown("### 🛠️ Synergy with Db2 Developer Extension for VS Code")
        st.markdown(
            """
            **How they complement each other:**
            - **Db2 Developer Extension for VS Code:** Provides a powerful developer environment directly inside the editor to connect to Db2, explore database objects, edit SQL, and execute queries against live databases.
            - **CatalogLens:** Functions as an independent, higher-level database intelligence system. While the developer extension gives developers the ability to execute SQL and inspect objects, CatalogLens provides the **business understanding**, **uncovers undocumented relationships**, and **evaluates cascading dependency risks**.
            - **Workflow:** A developer uses CatalogLens to understand an unfamiliar legacy schema, and uses the Db2 Developer Extension in VS Code to run targeted verification queries and verify proposed schema changes!
            """
        )

    with tab4:
        st.markdown("### 🛡️ Evidence Validation Philosophy")
        st.markdown(
            """
            > *"Don't just ask AI to explain a database. Give AI the evidence needed to understand it."*

            Every claim generated by CatalogLens is cross-referenced programmatically against the loaded `DbSchemaMetadata`.
            - **Verified Fact:** Direct 1-to-1 match with a Db2 catalog constraint (e.g. `SYSCAT.REFERENCES`).
            - **Metadata Supported:** Derived from valid existing tables, matching column data types, and structural patterns.
            - **Analysis Hypothesis:** A candidate interpretation produced by the reasoning engine; verify it against database evidence.
            - **Unverified Assumption:** Flagged whenever a claim mentions an invalid or non-existent database object.
            """
        )
