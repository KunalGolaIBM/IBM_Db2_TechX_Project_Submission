# REQUIREMENTS MATRIX — IBM Db2 TechX Summit 2026 / Db2Hack

**Verified on:** 30 October 2026 (IST)
**Sources:** Official summit website (SPA — content extracted from its production JS bundle), official GitHub submission repository (read in full), IBM Db2 AI Cookbook.

Verification legend:
- ✅ **Officially verified** — read directly from the official website or the official GitHub repository on 2026-10-30.
- ⚠️ **Technical finding** — verified technical fact (PyPI metadata, vendor docs) or engineering judgement.
- ❓ **Unresolved** — conflicting, placeholder, or inaccessible; needs organizer confirmation.

---

## 1. Participation

| Requirement | Verified detail | Source | Status |
|---|---|---|---|
| Who can participate | "Open to everyone — no restrictions. Students, developers and anyone curious can build a solution with IBM Db2, solo or as a team." Individual participation is explicitly allowed. | Website `/submit` (open-call section) + website FAQ | ✅ |
| Team size | No limit stated; every team member must be listed in `submission.json`, project README and PR description | Website FAQ + repo `docs/faq.md` | ✅ |
| Registration | Summit registration on Luma (free, approval-based). Hackathon participation itself is tied to the WhatsApp community, not Luma. | Website FAQ | ✅ |
| WhatsApp community | **Mandatory for every participant** — "all live updates, the Google Form link and any timing changes are shared there first" | Website FAQ | ✅ |

## 2. Technical Requirements

| Requirement | Verified detail | Source | Status |
|---|---|---|---|
| IBM Db2 usage | Code must **actually talk to IBM Db2** (Community Edition via Docker or the VS Code extension, Db2 on Cloud, or watsonx.data). "Mentioning Db2 only in the docs is ineligible." | Website `/submit` requirements + repo README + `docs/judging-criteria.md` | ✅ |
| AI framework | **At least one of LangChain, Haystack, CrewAI, LlamaIndex, Langflow is mandatory.** "Every project must use at least one… One is enough; combining several is also allowed." | Website FAQ + `/submit` requirement card 2 | ✅ |
| AI/LLM itself | Optional but encouraged: RAG, text-to-SQL, agents. Approved model providers: **watsonx.ai, OpenAI, Gemini, OpenRouter, Ollama** | Website `/submit` requirement card 3 + repo README | ✅ |
| Language | Any: Python, TypeScript/Node.js, Java, Go, Rust… as long as it interfaces with Db2 with clear build/run instructions | Website `/submit` + repo `docs/faq.md` | ✅ |
| Required files | Exactly four mandatory files per submission: `README.md`, `architecture.md`, `submission.json`, `.env.example` (plus `src/` per `submissions/README.md`; optional `tests/`, `docs/screenshots/`) | Repo `submissions/README.md` + validator script | ✅ |
| Secrets | Zero-secrets policy: `.env.example` with placeholders only; committing `.env`, keys, `.pem` etc. fails CI and is a disqualification trigger | Repo validator + `CONTRIBUTING.md` + website judging section | ✅ |

## 3. The Nine Official Db2 Packages / Toolkit

The website's Resources page "Toolkit — IBM Db2 packages" section lists **exactly nine** packages (the page itself computes "hj.length Db2 packages"). Five are tagged "Db2Hack framework" (core); four are supporting tooling. All names, install commands and doc URLs below are copied verbatim from the official website bundle — no invented names.

| # | Package | Install command (official) | Capability (official wording) | Doc URL | Local Python 3.14 compatibility (⚠️ verified on PyPI 2026-10-30) |
|---|---|---|---|---|---|
| 1 | **LangChain** `langchain-db2` | `pip install -U langchain-db2` | "Db2 vector store for RAG and retrieval" (`DB2VS`) | https://docs.langchain.com/oss/python/integrations/vectorstores/db2 | ✅ v1.0.0, requires `>=3.10,<4.0`; deps `langchain-core>=1.0`, `langchain-community>=0.4`, `ibm-db>=3.2.6,<4` |
| 2 | **Langflow** `lfx-ibm` | `pip install lfx-ibm` | "No-code IBM bundle with a Db2 vector store component" | https://pypi.org/project/lfx-ibm/ | ✅ v0.3.1, requires `>=3.10,<3.16` |
| 3 | **Haystack** `ibm-db-haystack` | `pip install ibm-db-haystack` | "Db2 document store for pipelines" | https://pypi.org/project/ibm-db-haystack/ | ✅ v1.0.0, requires `>=3.11` |
| 4 | **CrewAI** `crewai-tools` + `ibm_db` | `pip install crewai-tools ibm_db` | "Db2 vector search tool for agents" (`DB2SearchTool`) | https://docs.crewai.com/edge/en/tools/database-data/db2searchtool | ❌ `crewai-tools 1.15.33` requires `>=3.10,<3.14` — needs a Python ≤3.13 venv on this machine |
| 5 | **LlamaIndex** `llama-index-vector-stores-db2` | `pip install llama-index-vector-stores-db2` | "Db2 vector store" | https://developers.llamaindex.ai/python/framework/integrations/vector_stores/db2llamavs/ | ❌ v0.1.0 requires `>=3.9,<3.13` — needs a Python ≤3.12 venv on this machine |
| 6 | **dbt** `ibm-dbt-db2` | `pip install ibm-dbt-db2` | "Db2 adapter for data transformation" | https://pypi.org/p/ibm-dbt-db2 | ❌ v1.0.0 requires `>=3.10,<3.13` |
| 7 | **SQLGlot** `db2-sqlglot-dialect` | `pip install db2-sqlglot-dialect` | "Db2 SQL dialect" (IBM plugin) | https://github.com/IBM/db2-sqlglot-plugin | ✅ v1.1.0, requires `>=3.10` |
| 8 | **Python driver** `ibm_db` | `pip install ibm_db` | "Core Python driver for IBM Db2" | https://pypi.org/project/ibm_db/ | ✅ v3.3.0 ships `cp314-cp314-win_amd64.whl` (uploaded 2026-08-11) |
| 9 | **VS Code** IBM Db2 Developer Extension | `code --install-extension IBM.db2-for-luw` | "IBM Db2 Developer Extension" | https://marketplace.visualstudio.com/items?itemName=IBM.db2-for-luw | ✅ Already installed locally (v1.2.1). **Note: a development tool, not a standalone DB server** — its "Create Db2 instance" feature provisions a Db2 Community Edition container and requires Docker + Java 17+ + VS Code 1.103+ + ~4 GB free RAM |

Additional approved-but-not-one-of-the-nine connectors acknowledged by the repo: `ibm_db_sa` / SQLAlchemy (`db2+ibm_db://` URI), Node.js `ibm_db`, Java JCC JDBC (`com.ibm.db2:jcc:11.5.8.0`). Source: repo `docs/db2-setup-guide.md` ✅.

## 4. Submission & GitHub Requirements

| Requirement | Verified detail | Source | Status |
|---|---|---|---|
| Submission repo | `https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission` (fork → branch → template → PR) | Repo README | ✅ |
| Branch | `submission/<project-slug>` created from `upstream/main` | Repo README + CONTRIBUTING | ✅ |
| Directory | `submissions/<project-slug>/` copied from `submissions/_template/`; slug `^[a-z0-9]+(-[a-z0-9]+)*$` | Repo CONTRIBUTING + validator | ✅ |
| PR title | `[Submission] <project-slug>: <Short Project Title>` | Repo README + PR template | ✅ |
| Commit convention | Conventional commits scoped to slug: `feat(<project-slug>): …` | Repo CONTRIBUTING | ✅ |
| Scope isolation | PR must only add/modify files inside `submissions/<project-slug>/` — touching root files/CI/other submissions fails CI | Repo CONTRIBUTING + CI workflow | ✅ |
| Validation | `python scripts/validate_submission.py submissions/<project-slug>` locally; CI (GitHub Actions, Python 3.11, `scripts/validate_submission.py`) runs automatically on PRs touching `submissions/**` | Repo `scripts/validate_submission.py` + `.github/workflows/validate-submission.yml` | ✅ |
| `submission.json` schema | Required keys: `project.title` (≠ placeholder), `project.slug` (must equal folder name), `team.name` (≠ placeholder), `team.members` (≥1), `ibm_db2.edition`, `ibm_db2.connector`. Optional: `project.demo_url`, `video_url`, `repo_url`, `ibm_db2.features_used`, `tech_stack.*` | Repo `submissions/_template/submission.json` + validator | ✅ |
| Google Form | **PR alone does NOT complete the submission.** PR URL must be pasted into the official Google Form. ⚠️ The repo still shows the placeholder `[GOOGLE_FORM_LINK_TO_BE_ADDED]`; the website says the link is shared on WhatsApp and by email. | Repo README/PR template/FAQ + website FAQ | ✅ requirement / ❓ link itself inaccessible |
| LinkedIn post | **Mandatory**: "post your use case on LinkedIn, explain it clearly and tag the organising team. The best posts get appreciation from IBM experts." | Website FAQ + `/submit` step 8 | ✅ |
| YouTube demo | Not strictly mandatory as YouTube specifically; judging rewards "screenshots, demo URL **or** video walkthrough", and the PR template + `submission.json` provide `video_url` / demo URL fields. ⚠️ Strongly recommended for the Documentation & presentation criterion. | Repo `docs/judging-criteria.md` + PR template | ✅ fields / ⚠️ strategic recommendation |

## 5. Evaluation Criteria — ⚠️ CONFLICTING RUBRICS (UNRESOLVED)

Two different official rubrics exist, both summing to 100:

**A. Website `/submit` page (states "six dimensions — including security")** — ✅
| Dimension | Weight |
|---|---:|
| IBM Db2 integration & depth | 25% |
| Innovation & real-world impact | 20% |
| Technical architecture & AI | 15% |
| **Security** | **15%** |
| Reproducibility & code quality | 15% |
| Documentation & presentation | 10% |

**B. Repo `docs/judging-criteria.md`** — ✅
| Dimension | Weight |
|---|---:|
| IBM Db2 Integration & Depth | 30% |
| Innovation & Impact | 25% |
| Technical Architecture & AI Integration | 20% |
| Reproducibility & Code Quality | 15% |
| Documentation & Presentation | 10% |

❌ **Unresolved:** which rubric the judges actually use. **Mitigation (recommendation):** design to the *union* — maximal Db2 depth, strong innovation story, clean architecture, and explicit security engineering (parameterized SQL, least-privilege DB user, prompt-injection defenses, zero secrets). This scores well under either. Confirm with organizers via WhatsApp or a Submission Help issue.

**Disqualification/penalty triggers (both sources agree):** cosmetic Db2 mention without real integration; committed secrets; plagiarism; tampering with repo root/CI/other participants' folders. ✅

## 6. Dates & Deadlines — ⚠️ SUPERSEDED / UNRESOLVED

| Milestone | Official value | Source | Status |
|---|---|---|---|
| Kick-off | 28 Oct 2026, 7:00 PM IST — submissions open | Website + repo README | ✅ |
| Repo README "hard deadline" | 29 Oct 2026, 7:00 PM IST | Repo README "Important Dates" table | ⚠️ **Superseded by the live website** (see below) |
| Current submission status (website) | "**There is no deadline today.**" / "Submissions are open now and **not strict** — the closing time will be announced, so submit early." On-campus build window 30 Oct 14:00–15:00 with submissions welcome; closing time "announced on WhatsApp". | Website `/submit` dates section, open-call banner, FAQ | ✅ (as published 2026-10-30) |
| Finale | 30 Oct 2026 — Top 10 pitch 16:00–16:30 IST at GL Bajaj, Mathura | Website schedule | ✅ |
| Exact closing time | **Unknown** — "will be announced" (WhatsApp) | Website | ❓ |

⚠️ **Flag per audit brief:** the Oct 29 repo deadline vs Oct 30 event-day instructions are an unresolved issue **unless** an official extension is verified. The live website (checked on event day, 30 Oct) explicitly states submissions remain open and not strict — treat this as the current official position, but the precise closing hour remains unknown until announced on the (mandatory) WhatsApp community.

## 7. Rewards / Incentives (context, not requirements)

Top 10: Db2 goodies + live pitch. Top 3: on-stage recognition. Everyone: certificates + opportunity to contribute to IBM Db2 AI open-source use cases with IBM team guidance. Best LinkedIn posts: appreciation from IBM experts. ✅ (Website rewards section)

## 8. Organizer-Supplied Support

- Event SPOC: Dhruv Chaturvedi (Db2 Software Engineer, IBM Lucknow); submission repo maintained by Kunal Gola (IBM). ✅
- GitHub "Submission Help" issue templates for setup/PR/validation questions. ✅
- **IBM Bob** (IBM's AI dev partner): free trial offer of 50 Bobcoins/30 days advertised for scaffolding/debugging/documentation. Optional tool, not a requirement. ✅ (advertised on website `/submit`) — ⚠️ our own agent tooling is sufficient; not planned for use.
- Official IBM tutorial videos (YouTube, channel `@IBMProductHub`): Langflow `NRo4ePT2MEE`, Haystack `T3it5_2JwIw`, CrewAI `qZnhCnwGttg`. ✅
