# PROJECT CONCEPTS — Db2Hack Idea Exploration & Ranking

**Date:** 30 October 2026 (IST) — M0 research. **No implementation has begun.**
**Evaluation basis:** the union of both official rubrics (see `REQUIREMENTS_MATRIX.md` §5) — IBM Db2 depth (≤30%), Innovation & real-world impact (≤25%), Technical architecture & AI (≤20%), Security (15% in website rubric), Reproducibility & code quality (15%), Documentation & presentation (10%). Website's own idea guidance (✅ `/submit` quick-start): "Pick a real problem… Most strong ideas are RAG apps, AI agents or text-to-SQL."

Scores are 1–10 per dimension; weighted total uses the **maximal** weight per dimension across both rubrics (Db2 30, Innovation 25, Arch/AI 20, Security 15, Repro 15, Docs 10 → total weight 115, normalized to 100).

---

## Concept 1 — "CampusDocs Q&A": RAG assistant over institutional documents

- **Real problem:** Students/staff can't find answers in sprawling college handbooks, exam rules, scholarship policies, hostel/mess regulations (PDFs scattered across portals).
- **Intended users:** Students, parents, college administrative staff.
- **Why Db2 is essential:** Db2 stores document chunks **and** their embeddings in `VECTOR` columns; retrieval is a single SQL statement combining semantic similarity with `WHERE` filters (department, year, doc version) — exactly the "filter + vector in one query" differentiator vs. standalone vector DBs (✅ Db2 AI Cookbook module 01 premise).
- **Actual DB interactions:** ingest (chunk→embed→INSERT), filtered similarity search (DB2VS), citation table lookups, query-logging table.
- **AI functionality:** RAG — nomic-embed-text for chunks/questions, granite4.2:3b for grounded answer generation with citations.
- **Approved Db2 package:** `langchain-db2` (DB2VS) + `ibm_db`.
- **AI framework:** LangChain.
- **Technical complexity:** Low. **Demo potential:** High (ask real handbook questions live, show SQL). **Innovation:** Medium — classic RAG, many such projects exist. **Timeline feasibility:** Excellent (half a day).
- ⚠️ Risk: closest to "generic chatbot" perception — must lean on citations + filtered SQL to differentiate.

## Concept 2 — "Ticket Twin": Support-ticket dedup & triage intelligence

- **Real problem:** IT/help-desk teams drown in duplicate/near-duplicate tickets; agents waste time re-answering known issues.
- **Intended users:** IT support teams, SaaS help desks, college TPO/IT cell.
- **Why Db2 is essential:** Tickets live in relational tables (status, priority, assignee — real columns); near-duplicate detection = vector similarity **plus** SQL filters in one statement; Db2 keeps ticket data and embeddings together under one access-control model.
- **Actual DB interactions:** ticket CRUD, VECTOR column similarity search for "is this a duplicate of an open ticket?", keyword (LIKE/FT) + vector hybrid, audit tables.
- **AI functionality:** Embedding-based duplicate detection; RAG answer draft from past resolved tickets; optional triage classification (JSON output from granite4.2).
- **Approved Db2 package:** `langchain-db2` (+ `db2-sqlglot-dialect` for safe SQL handling if needed).
- **AI framework:** LangChain.
- **Complexity:** Medium. **Demo potential:** High (paste a ticket → system flags duplicates + drafts reply). **Innovation:** Medium-high. **Feasibility:** Good (1 day) — needs a synthetic-but-realistic ticket corpus (must be clearly labelled synthetic). ⚠️

## Concept 3 — "AskMyData": Guardrailed text-to-SQL analytics copilot

- **Real problem:** Non-technical users can't query business databases; analysts are bottlenecks.
- **Intended users:** Managers, operations staff, students learning SQL.
- **Why Db2 is essential:** Db2 is both the **target** (schema introspection via catalog views, generated SQL executed in Db2) and the audit trail (every generation logged). No other store needed.
- **AI functionality:** NL→SQL with schema-in-prompt, self-checking (dry-run/EXPLAIN validation), answer rendering. Uses Db2 system catalog for schema grounding.
- **Approved Db2 package:** `langchain-db2` (for any semantic metadata) + `ibm_db`; could use `db2-sqlglot-dialect` to validate/parse generated SQL before execution — a nice IBM-toolkit touch.
- **AI framework:** LangChain (SQLChain-style) .
- **Complexity:** Medium-high (SQL-injection/prompt-injection guardrails are the hard part — also a **judged** Security dimension). **Demo potential:** Very high (natural language → real SQL → chart). **Innovation:** Medium (text-to-SQL is common) but guardrails + Db2 catalog depth differentiate. **Feasibility:** Medium (1–1.5 days incl. safety work). ⚠️ Risk: text-to-SQL on a small demo schema can feel thin; needs a rich schema (Db2 SAMPLE/GOSALES helps).

## Concept 4 — "SkillMatch": Course & resource recommender with availability filters

- **Real problem:** Students can't discover the right courses/certificates/projects among hundreds; recommendations ignore real constraints (seats, schedule, eligibility).
- **Intended users:** Students, training & placement cells, L&D teams.
- **Why Db2 is essential:** Mirrors the official cookbook module 06 pattern — item attribute vectors + `VECTOR_DISTANCE` ranking **filtered by live relational constraints** (seats available, time slot, eligibility) in one SQL statement: "a recommendation nobody can get is worthless" (✅ cookbook wording).
- **AI functionality:** Item-to-item semantic recommendation; optional LLM-generated natural-language rationale per recommendation.
- **Approved Db2 package:** `langchain-db2` DB2VS.
- **AI framework:** LangChain.
- **Complexity:** Low-medium. **Demo potential:** High (click a course → get filtered similar-course list + rationale). **Innovation:** Medium. **Feasibility:** Excellent. ⚠️ Risks: closest to a direct cookbook clone (plagiarism-similarity penalty risk if code is copied — must build original UX/logic); dataset acquisition needed.

## Concept 5 — ⭐ RECOMMENDED: "Db2 Ops Copilot" — hybrid RAG + guardrailed text-to-SQL over IBM Db2

- **Real problem:** Newcomers to Db2 (students, junior devs, ops staff) don't know Db2 SQL dialect, catalog views, or where their data lives; answering "how do I…" requires both **documentation** and **their actual database**. The summit audience *is* this population — and IBM's own resources push Db2-for-AI education.
- **Intended users:** Db2 learners & developers (the exact hackathon audience), DBAs, anyone adopting Db2 with AI.
- **Why Db2 is essential (doubly):** (1) Db2 is the **vector store** for the documentation/case-knowledge RAG corpus (`VECTOR` column + `VECTOR_DISTANCE`, filtered by product/version metadata in one SQL); (2) Db2 is the **query target** — the copilot introspects the live Db2 catalog (tables, columns, indexes via `SYSCAT`), generates *validated* Db2-dialect SQL (parsed with the official `db2-sqlglot-dialect` before execution, read-only role), runs it, and explains results. Both halves are genuine, non-cosmetic Db2 integration — maximum coverage of the 25–30% Db2-depth criterion, and structurally incapable of the "generic chatbot" verdict.
- **Actual DB interactions:** create schema + ingest docs into DB2VS; similarity search with metadata filter; catalog introspection SELECTs; generated-SQL execution under a least-privilege read-only user; query audit log INSERTs; hybrid routing decision logged.
- **AI functionality:** **Router** (docs question vs. data question vs. both), **RAG** (granite4.2:3b grounded answers from Db2 docs/case notes with citations), **Text-to-SQL** (schema-aware generation, sqlglot Db2-dialect validation, EXPLAIN dry-run, execution, LLM-written summary), optional **agentic retry** (grade retrieval → rewrite query → retry, cookbook module 05 pattern) if time permits.
- **Approved Db2 packages:** `langchain-db2` (core), `db2-sqlglot-dialect` (SQL safety), `ibm_db` (driver) — three of the nine, all Python-3.14-compatible. ✅
- **AI framework:** LangChain (primary), per `TECH_STACK_DECISION.md`.
- **Technical complexity:** Medium-high but **layered** — a working RAG-only core ships on day one; SQL pipeline and agentic grading are additive. All local (Ollama) → fully reproducible demo, no API keys needed.
- **Demo potential:** Excellent and *visibly* Db2: show the same UI answering "Does Db2 support vector columns and since which version?" (RAG, shows retrieved chunks + SQL that fetched them) and "Which tables in this database have more than 10k rows and who queries them?" (text-to-SQL, shows generated SQL → EXPLAIN → result table). Live SQL pane proves real Db2 connectivity — a judge-convincing "zero cosmetic Db2" story.
- **Innovation:** High *in context* — hybrid routing + Db2-dialect validation via the official SQLGlot plugin + fully local IBM Granite stack is not the standard chatbot demo; it directly extends IBM's own cookbook directions (04-rag, 05-agentic-rag, 08-language-model-integration) into a coherent product.
- **Timeline feasibility:** Good. Core (RAG over Db2) ≈ half a day; SQL half ≈ half a day; docs/tests/video ≈ half a day. Dataset: official Db2 documentation excerpts + cookbook READMEs (Apache-2.0 — attribution preserved to avoid plagiarism flags) + a seeded demo schema in Db2 SAMPLE.

## Concept 6 — "PolicyGuard": Agentic compliance-policy checker (rejected variant)

Evaluated briefly: self-grading agentic RAG over regulatory PDFs with structured findings written back to Db2. Strong innovation, but ⚠️ requires substantial curated domain corpus (hard to do credibly in the window), domain-expertise claims we can't validate, and higher hallucination liability in demo. **Rejected** in favor of Concept 5's verifiable outputs (SQL results are checkable by judges).

---

## Ranking (weighted against the union rubric)

| Rank | Concept | Db2 depth | Innovation | Arch/AI | Security | Repro | Docs | **Weighted /100** |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | **5 — Db2 Ops Copilot (hybrid RAG + text-to-SQL)** | 10 | 8 | 9 | 8 | 8 | 8 | **⭐ 89** |
| 2 | 3 — AskMyData text-to-SQL copilot | 8 | 7 | 8 | 8 | 7 | 7 | 76 |
| 3 | 2 — Ticket Twin | 8 | 7 | 7 | 7 | 7 | 7 | 73 |
| 4 | 1 — CampusDocs Q&A RAG | 7 | 5 | 6 | 6 | 9 | 8 | 68 |
| 5 | 4 — SkillMatch recommender | 7 | 5 | 6 | 6 | 8 | 7 | 65 |
| 6 | 6 — PolicyGuard agentic compliance | 7 | 8 | 8 | 6 | 4 | 5 | 64 |

*Security column reflects how much judged security engineering the design forces (Concept 5/3 force parameterized SQL, least-privilege roles, prompt-injection defenses). Repro reflects dataset + environment reproducibility on a judge's machine.*

## Final Recommendation

**Build Concept 5 — "Db2 Ops Copilot"** (working title; slug candidate `db2-ops-copilot`, alternatives: `db2-rag-sql-copilot`). It maximizes the heaviest-weighted criterion (genuine, deep Db2 integration — as vector store *and* query engine), is differentiated from generic chatbots by construction, uses three of the nine official toolkit packages, runs fully local on IBM Granite via Ollama (great "IBM story" on an IBM stage), and has a safe staged build path where every stage is independently demoable.

**Do not start implementation until M1 is explicitly approved.**
