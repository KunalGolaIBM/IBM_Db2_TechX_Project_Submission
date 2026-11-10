<!-- Paste this as the body of the pull request. It follows .github/PULL_REQUEST_TEMPLATE.md (official main, 4d685c2).
     Title: [Submission] civiclens-ai: CivicLens AI, Db2-backed urban infrastructure investigations
     Base: KunalGolaIBM/IBM_Db2_TechX_Project_Submission : main   Head: tej-1916/IBM_Db2_TechX_Project_Submission : submission/civiclens-ai
     Tick only the boxes in section 6 that are true for you when you open it. -->

# IBM Db2 TechX Summit 2026 — Project Submission

## 1. Project Overview

- **Project Title:** CivicLens AI
- **Project Slug (must match folder name):** `submissions/civiclens-ai/`
- **Short Description (1–3 sentences):** An agentic investigation platform for city infrastructure complaints. IBM Db2 stores every complaint, finds duplicates and geographic hotspots with in-database SQL, keeps an append-only audit trail of every tool call and human decision, and a React dashboard shows who or what wrote each recommendation: a real LLM, a clearly labelled rule-based fallback, or an analyst.
- **Problem Solved & Target Audience:** Municipal engineers, ward officers and civic analysts receive floods of complaints (potholes, water leaks, streetlights, garbage). Many are duplicates, clusters are hard to see ticket by ticket, and AI assistants that write their own SQL are hard to trust or audit. CivicLens lets an investigator use only audited, read-only, parameterized Db2 tools, proposes evidence-backed recommendations, and requires a human to approve each one.

---

## 2. Team Information

- **Team Name:** CivicLens
- **Team Members:**

| Full Name | GitHub Username | Email / Role |
|---|---|---|
| Tej Sagar | @tej-1916 | Lead developer |

---

## 3. IBM Db2 Integration Summary

- **IBM Db2 Edition / Environment:** Db2 Community Edition 12.1.5 in Docker (image pinned by digest, port bound to `127.0.0.1`). A TLS path for Db2 on Cloud is coded (`DB2_SECURITY=SSL`) but has **not** been tested against a hosted instance.
- **How IBM Db2 is Used in the Solution:** Db2 is the only store and does real work: great-circle (haversine) distance for duplicate detection computed in SQL; hotspot detection with `GROUP BY` geo-cell × category `HAVING COUNT(*) >= ?`; every dashboard aggregate (counts, trends, provenance split) computed per request; composite foreign keys that make Db2 refuse evidence not attached to the same investigation; a unique index as a double-review backstop; compare-and-set status transitions; one atomic multi-statement review transaction with rollback; catalog-driven idempotent migrations; an append-only audit table.
- **Db2 Connector / Driver / Framework Integration Used:** native `ibm_db` 3.3.0 (`prepare`/`execute` with bound parameters only; no SQL is ever built from user or LLM input).
- **Schema & Data Stored / Processed:** schema `CIVICLENS`: `COMPLAINTS`, `INVESTIGATIONS`, `INVESTIGATION_EVIDENCE`, `RECOMMENDATIONS`, `RECOMMENDATION_EVIDENCE`, `REVIEW_DECISIONS`, `AUDIT_LOG` (DDL in `src/backend/civiclens/db/schema.sql`). Demo data: 52 **synthetic** complaints, flagged `IS_SYNTHETIC = 1` and labelled in the UI.
- **Steps to Verify Db2 Integration:**
  ```bash
  cd submissions/civiclens-ai && cp .env.example .env          # set DB2_PASSWORD and CIVICLENS_AUTH_TOKENS
  docker compose -f docker-compose.db2.yml up -d                # first start takes a few minutes
  pip install -r src/backend/requirements-dev.txt
  python src/backend/scripts/db2_migrate.py && python src/backend/scripts/seed_synthetic.py
  CIVICLENS_DB2_TESTS=1 pytest                                  # 149 passed, 1 skipped (opt-in real-LLM test) against live Db2, no mocks
  python src/backend/scripts/db2_smoke_test.py                  # real Db2 operations -> docs/evidence/
  ```
  Recorded output from real runs: `docs/evidence/`.

---

## 4. Technology Stack & AI / LLM Usage

- **Programming Languages:** Python, TypeScript, SQL
- **Frameworks & Libraries:** FastAPI, Pydantic, `ibm_db`, LangChain (`langchain-core` tools); React 19, Vite, Tailwind CSS, TanStack Query, zod, Leaflet + OpenStreetMap; pytest, Vitest, Playwright, axe-core
- **AI / LLM Framework (if applicable):** LangChain: a bounded tool-calling loop (allow-listed tools, step limit, timeout, evidence grounding) plus a deterministic rule-based fallback
- **Model Provider & Model Name (if applicable):** **None was used for any result in this submission.** The code supports OpenAI, Anthropic and IBM watsonx.ai, but **no provider credentials were available, so real-LLM verification is blocked** (`docs/evidence/llm_verification.txt`). Every recommendation shown is labelled "Rule-based · no LLM" or "Manual · analyst-written"; nothing is presented as AI output.
- **Where AI/LLM is Applied in the Workflow:** the investigator proposes recommendations from audited Db2 tool results; a person approves or rejects each one. With no model configured the labelled rule-based fallback produces the proposals. The agent loop is verified with a scripted test double (labelled as such), not with a real model.

---

## 5. Demonstration & Links

- **Live Demo URL (if hosted):** none (not deployed; it is not safe to expose publicly until the gaps listed below are closed)
- **Demo Video (YouTube / Loom / Drive):** in the repository: `submissions/civiclens-ai/docs/demo/civiclens-demo.mp4` (a silent, captioned screen recording of the real app; narration script in `docs/DEMO.md`) <!-- replace with a hosted link if you upload one -->
- **External Source Repo (if hosted separately):** n/a
- **Presentation / Slides URL (optional):** n/a (slide outline in `docs/DEMO.md`)
- **Screenshots:** 28 genuine captures from the running app: `submissions/civiclens-ai/docs/screenshots/README.md`

---

## 6. Submission Verification Checklist

- [x] **Folder Structure:** a single new directory under `submissions/civiclens-ai/` (template layout plus `tests/` and `docs/`).
- [x] **Naming Conventions:** slug `civiclens-ai` (lowercase, hyphens), matching branch `submission/civiclens-ai` and the PR title.
- [x] **Complete Documentation:** `README.md` and `architecture.md` are filled out (all template sections), no unfilled placeholder markers.
- [x] **Metadata File:** `submission.json` is complete and valid; `scripts/validate_submission.py` passes.
- [x] **No Secrets or Credentials:** the repository secret scan (which checks the literal values of the real secrets) and a built-bundle scan report 0 findings; `.env.example` contains placeholders only.
- [x] **Tested Setup Instructions:** run from a fresh clone (backend unit tests, frontend install/typecheck/lint/tests/build) and against a live Db2 (149 backend tests, 8 live API-contract tests, 63 browser tests).
- [x] **License Declared:** MIT, see `submissions/civiclens-ai/LICENSE`.
- [ ] **Code of Conduct:** all team members agree to the repository [Code of Conduct](https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission/blob/main/CODE_OF_CONDUCT.md). <!-- tick yourself -->
- [x] **Scope Isolation:** this PR only adds files inside `submissions/civiclens-ai/` and does not touch root files or other submissions.
- [ ] **Google Form Submission:** I understand that opening this PR is step 1, and I will submit this PR URL into the official Google Form. <!-- tick yourself once done -->

---

## 7. Additional Notes for Reviewers & Judges

- **Fastest check (no Db2 needed):** `cd submissions/civiclens-ai && pip install -r src/backend/requirements-dev.txt && pytest tests/unit` (111 tests; 108 pass and 3 skip until the optional provider packages of `requirements-llm.txt` are installed) and `cd src/frontend && npm ci && npm test` (245 tests). With Db2: the commands in section 3, then `cd src/frontend && npm run build && npm run preview` and sign in with a token from `CIVICLENS_AUTH_TOKENS`.
- **What is verified, against real services:** 149 backend tests on live Db2; 8 live API-contract tests; 63 Playwright tests on the production build (real backend and Db2: complaint browsing, investigation creation, evidence, the rule-based run, authenticated review with real 401/403/409/422/503 responses, axe-core accessibility, responsive checks); `pip-audit` and `npm audit --omit=dev` report no known vulnerabilities.
- **Honesty about the AI part:** no real LLM was run (no credentials). The UI labels every recommendation with its stored author, and the *Agent transparency* page counts them (0 from a language model). The agent loop's failure handling was hardened during release preparation: a failing provider call now degrades to the labelled fallback in Auto mode instead of ending in a generic error.
- **Known gaps:** the Phase 00 read endpoints (`GET /api/complaints`, `/api/hotspots`) are public; tokens are static and there is no rate limiting (do not expose publicly before real identity and rate limits); the TLS path to a hosted Db2 is untested.
- **How it was built:** developed with an AI coding assistant under the participant's direction; every behaviour claimed here was checked by running the tests listed above. The full audit is in `submissions/civiclens-ai/docs/PHASE_02_RELEASE_REPORT.md`.
