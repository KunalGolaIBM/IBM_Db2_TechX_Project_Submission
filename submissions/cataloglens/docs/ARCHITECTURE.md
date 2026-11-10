# CatalogLens — System Architecture & Technical Specifications

> **Tagline:** Making the unknown structure of enterprise databases understandable.
> **Target Ecosystem:** IBM Db2 LUW & Db2 Developer Extension for VS Code.

---

## 1. High-Level System Architecture

CatalogLens is structured into distinct, decoupled layers separating deterministic catalog analysis from agentic reasoning:

```mermaid
flowchart TD
    subgraph ClientLayer ["Client & Interface Layer"]
        UI["Streamlit Frontend Application\n(Port 8501)"]
        VSCodeExt["IBM Db2 Developer Extension\n(VS Code SQL & Object Explorer)"]
    end

    subgraph APILayer ["Backend API Gateway"]
        FastAPI["FastAPI REST API\n(Port 8000)"]
    end

    subgraph AgenticLayer ["Agentic Intelligence Layer"]
        LG["LangGraph Investigation Pipeline"]
        Claude["Optional Anthropic Claude API\n(requires configured API key)"]
        EvVal["Evidence Validator Engine\n(Programmatic Hallucination Blocker)"]
    end

    subgraph EngineLayer ["Deterministic Analysis Engines"]
        RelDet["Relationship Detector\n(Declared & Inferred)"]
        DepAn["Dependency & Impact Analyzer\n(NetworkX Directed Graph)"]
        WfDet["Workflow Discovery Engine\n(O2C, Inventory, Billing, RMA)"]
    end

    subgraph DataLayer ["Data & Storage Layer"]
        Db2Mgr["Db2 Connection Manager\n(ibm_db Driver)"]
        LiveDb2[("IBM Db2 LUW Instance\nSYSCAT Catalog Views")]
        DemoDb[("Enterprise Demo Snapshot\n13 Tables, 2 Views")]
    end

    UI -->|HTTP / REST| FastAPI
    FastAPI --> LG
    FastAPI --> RelDet
    FastAPI --> DepAn
    FastAPI --> WfDet
    LG -.->|Optional LLM reasoning| Claude
    LG --> EvVal
    EvVal -.->|Validates against| RelDet
    RelDet --> Db2Mgr
    DepAn --> RelDet
    WfDet --> RelDet
    Db2Mgr -->|Native Protocol| LiveDb2
    Db2Mgr -.->|Fallback / Demo Mode| DemoDb
    VSCodeExt -->|Direct JDBC / CLI| LiveDb2
```

---

## 2. LangGraph Stateful Investigation Pipeline

CatalogLens uses a purposeful, 6-node state machine orchestrating database understanding:

```mermaid
flowchart LR
    Start([Start]) --> N1["1. MetadataRetriever\nFetch SYSCAT tables,\ncolumns & constraints"]
    N1 --> N2["2. SchemaAnalyzer\nCompile baseline metrics\n& ground-truth ledger"]
    N2 --> N3["3. RelationshipInvestigator\nDetect declared foreign keys\n& inferred candidate links"]
    N3 --> N4["4. Reasoning / Deterministic Fallback\nGenerate table interpretation\nand verification questions"]
    N4 --> N5["5. EvidenceValidator\nVerify all references programmatically;\nPenalize hallucinations"]
    N5 --> N6["6. ReportGenerator\nCompile validated report\n& evidence ledger"]
    N6 --> EndNode([Investigation Report])
```

### Typed State Structure (`InvestigationState`)

```python
class InvestigationState(TypedDict):
    schema_name: str
    selected_table: str
    investigation_question: Optional[str]
    use_demo: bool
    metadata: Optional[DbSchemaMetadata]
    declared_relationships: List[RelationshipEdge]
    inferred_relationships: List[RelationshipEdge]
    table_evidence_ledger: List[EvidenceClaim]
    ai_understanding: Optional[TableUnderstanding]
    validated_evidence: List[EvidenceClaim]
    discrepancies: List[str]
    final_report: Optional[Dict[str, Any]]
    errors: List[str]
```

---

## 3. IBM Db2 LUW Catalog Metadata Extraction Flow

All structural evidence originates from standard Db2 LUW `SYSCAT` system views:

```mermaid
sequenceDiagram
    autonumber
    participant App as CatalogLens Extractor
    participant Db2 as IBM Db2 LUW (SYSCAT)

    App->>Db2: SELECT SCHEMANAME FROM SYSCAT.SCHEMATA
    Db2-->>App: Non-system schemas (ENTERPRISE)
    App->>Db2: SELECT TABNAME, TYPE, REMARKS, CARD FROM SYSCAT.TABLES
    Db2-->>App: Tables and views metadata
    App->>Db2: SELECT COLNAME, TYPENAME, LENGTH, NULLS FROM SYSCAT.COLUMNS
    Db2-->>App: Column definitions and data types
    App->>Db2: SELECT CONSTNAME, COLNAME FROM SYSCAT.TABCONST / KEYCOLUSE (Type 'P')
    Db2-->>App: Primary keys
    App->>Db2: SELECT CONSTNAME, TABNAME, REFTABNAME FROM SYSCAT.REFERENCES
    Db2-->>App: Formally declared foreign keys
    App->>Db2: SELECT INDNAME, UNIQUERULE, COLNAMES FROM SYSCAT.INDEXES
    Db2-->>App: Physical indexes
    App->>Db2: SELECT VIEWNAME, TEXT FROM SYSCAT.VIEWS
    Db2-->>App: View SQL definitions and source object mappings
```

---

## 4. Evidence Validation & Hallucination Defense Flow

```mermaid
flowchart TD
    ClaudeOut["Reasoning Output\n(LLM response or deterministic fallback)"] --> Parser["Structured JSON Parser\n(Pydantic TableUnderstanding)"]
    Parser --> ExtractRefs["Extract Referenced Tables & Columns"]
    ExtractRefs --> EngineCheck{"Cross-reference with\nLoaded DbSchemaMetadata"}

    EngineCheck -->|Objects Exist in SYSCAT| CheckFK{"Matches Declared\nForeign Key?"}
    EngineCheck -->|Object Missing in SYSCAT| FlagHallucination["Flag Discrepancy:\n'Table does not exist'\nStatus: UNVERIFIED_ASSUMPTION\nConfidence halved (< 0.50)"]

    CheckFK -->|Yes| SetFact["Status: VERIFIED_FACT\nConfidence: 1.00"]
    CheckFK -->|No (Naming/Type Match)| SetSupported["Status: METADATA_SUPPORTED\nHeuristic candidate; manual verification required"]

    SetFact --> Ledger["Evidence Ledger Cards\n(Presented in UI)"]
    SetSupported --> Ledger
    FlagHallucination --> Ledger
```

---

## 5. Db2 Developer Extension for VS Code Synergy

CatalogLens and the IBM Db2 Developer Extension for VS Code serve distinct, mutually reinforcing roles:

| Capability | IBM Db2 Developer Extension (VS Code) | CatalogLens |
|---|---|---|
| **Primary User Goal** | Execute SQL, manage connection profiles, view raw DDL | Understand business context, discover hidden links, assess change risk |
| **Interface** | VS Code sidebar tree view & SQL editor tabs | Interactive Streamlit graph dashboard & FastAPI service |
| **Object Inspection** | Raw tree view of schemas, tables, columns, routines | Normalized structural view + cardinality + catalog remarks |
| **Relationship Mapping** | Explicit foreign keys only | Declared foreign keys + Inferred candidate relationships + Graph |
| **Semantic Understanding**| None | LangGraph investigation pipeline with optional Claude integration |
| **Dependency & Impact Analysis**| Manual query inspection | Automated multi-hop cascade dependency tracer & severity ratings |
| **Evidence Ledger** | None | Metadata-backed evidence and validation ledger |
| **Developer Synergy** | The developer inspects and modifies SQL in VS Code | The developer uses CatalogLens to discover *what* to write and assess *risk* |
