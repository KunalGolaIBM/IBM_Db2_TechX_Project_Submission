# Hotel Ops Copilot: Governed Multi-Agent Hotel Operations on IBM Db2

> **One-line pitch:** A LangGraph team of AI agents that reads a hotel's IBM Db2 database, mines guest reviews with Db2 vector search, and proposes pricing, upgrade and maintenance actions. **Db2 itself** governs the agents: it decides what they may read, re-checks every action in stored procedures before applying it, and can undo any change with temporal time travel.

**"The database governs the AI, not the prompt."** Below, in a real recorded run, the AI is wrong. It cites a policy and claims Deluxe isn't full, then proposes blocking room 307. A manager presses **Dry run**: Db2 executes the real stored procedure inside a transaction, finds **Deluxe would be OVERSOLD on the conference nights**, and rolls back, before anyone approves.

![Db2 dry run catches the agent's overbooking mistake](docs/screenshots/12-dry-run-catches-oversell.png)

| 30/30 | 24/24 | 10,000/10,000 | 26/26 | 106 · 87% | 1 command |
|:---:|:---:|:---:|:---:|:---:|:---:|
| evaluation questions correct (KPIs, time travel, bitemporal, vector search, policies, Hindi, 9 safety attacks), against ground truth computed in Db2 ([results](docs/eval_results.md)) | red-team attacks blocked, 22 by Db2 itself ([scoreboard](docs/redteam_results.md)) | random proposals fuzzed into the Db2 guardrails, every decision matching an independent oracle ([results](docs/guardrail_fuzz.md)) | live Db2 checks of every claim (`python src/verify.py`, no key) | automated tests, 86% line coverage of the core package, none needing an LLM key | `docker compose up -d` starts Db2 and the app |

**How Db2 governs the AI.** The agents can only read (as a least-privileged Db2 user) and *propose*. Every decision that changes the hotel is made, checked and recorded by Db2:

```mermaid
flowchart TB
    Q([Manager asks]) --> R[Router agent]
    R --> AG
    subgraph AG [Specialist agents]
        A[Analyst]
        V[Reviews]
        O[Operations]
    end
    AG -- "read-only SQL, VECTOR search,<br/>time travel, policies" --> DB[("IBM Db2<br/>least-privilege role<br/>RCAC masks + consent rows<br/>EXPLAIN cost guard")]
    O -- "SP_PROPOSE_ACTION" --> G{"Db2 guardrails<br/>SQL PL + JSON + CHECK<br/>10,000/10,000 fuzzed"}
    G -- "out of bounds" --> X[REJECTED]
    G -- "inside earned autonomy" --> AUTO[Applied by Db2]
    G -- "PENDING" --> H["Manager: Why? + Dry run<br/>(real procedure, ROLLBACK)"]
    H -- "Approve" --> APPLY[Applied]
    AUTO --> T[("Temporal + bitemporal history")]
    APPLY --> T
    T -- "SP_ROLLBACK_ACTION AS OF" --> UNDO[Undone in one click]
    AG -. "every step" .-> L[["SHA-256 hash-chained audit<br/>+ external anchor"]]
```

**What if the AI is hacked?** 24 attacks hit the live Db2 with the agent's own credentials. Db2 stops 22 of them itself, and every one is rolled back:

![Red-team attack console: 24/24 blocked](docs/screenshots/red-team-live.gif)

### 30-second proof: `python src/verify.py`
![Proofs tab: 26/26 live Db2 checks](docs/screenshots/proofs-live.gif)

One command checks every headline claim against the live Db2, with no LLM key, and rolls back anything it writes: Db2 12.1 and native `VECTOR` columns, vector search, IBM `langchain-db2`, temporal tables, the least-privilege agent, RCAC mask and row permission, the `EXPLAIN` cost guard, **bitemporal** `BUSINESS_TIME` + `SYSTEM_TIME` promotions, a **materialized query table**, the change feed, the SQL PL and JSON guardrails, guarded apply + rollback, earned autonomy decided inside Db2, CHECK constraints, the hash-chain trigger, the tamper-evident audit chain, an **external anchor that catches a fully rebuilt ledger**, the red team and the evaluation. It also fuzzes the guardrails with 1,000 random proposals. Expected output ends with **`26/26 checks passed`** in about 10 seconds. The same checks run live, one by one, in the app's **Proofs** tab. With Docker: `docker compose exec app python src/verify.py`.

### 5-minute judge tour
After `docker compose up -d` (or `bash scripts/quickstart.sh`), open http://localhost:8501. Steps 1–4 need **no API key**.

1. **🛡️ Red team** → *Run all attacks*: 24/24 blocked, 22 of them by Db2 privileges, RCAC and SQL PL guardrails.
2. **📊 Dashboard** → the complaint radar: a single Db2 vector query finds AC faults in rooms 307/312 and hot water in 512.
3. **🕰️ Time travel** → the change feed: before and after, who and why, rebuilt from `*_HISTORY`.
4. **🧾 Audit trail** → "hash chain intact" (SHA-256 in Db2); *Simulate tampering* (Db2 flags the edited step); ▶ *Replay* a recorded Gemini run.
5. **💬 Copilot** → ☀️ *Morning brief* (needs `GOOGLE_API_KEY`): router → 3 specialists → composer, live.
6. **✅ Approvals** → 🔍 *Dry run* a proposal (Db2 executes it in a transaction, then rolls back) → *Approve* → *Roll back*.
7. **✅ Approvals** → 🤖 *Earned autonomy*: grant ±5% price nudges, then ask the copilot for a 3% change. Db2 applies it on its own.

### For judges: where to find each criterion

| Criterion | Where to look |
|---|---|
| **Db2 integration and depth (30%)** | Every guarantee in this project is enforced by Db2, not by the prompt. It uses **vector search** over sentence chunks, **system-period temporal tables** for time-travel rollback, **SQL PL guardrail procedures**, **RCAC column masks and a row permission** (consent), a **least-privilege role** for the AI, an **`EXPLAIN` cost guard** on AI-written SQL, IBM's **`langchain-db2` vector store** for the policy handbook, a **JSON check constraint**, and the agent's audit trail in Db2 tables. A **[red-team scoreboard](docs/redteam_results.md)** shows **24/24 attacks blocked**, 22 of them by Db2 itself. See [IBM Db2 Integration](#ibm-db2-integration) and [`src/sql/`](src/sql) |
| **Innovation and impact (25%)** | A governed agent: the AI can only *propose*, Db2 **dry-runs** the action, a human approves, Db2 re-checks and applies, and any change can be undone in one click. **Earned autonomy** lets managers grant the AI low-risk actions within limits Db2 enforces. Db2 also defeats a prompt-injection attack hidden in a guest review |
| **Architecture and AI integration (20%)** | A LangGraph router with three specialist sub-graphs and a composer. Each specialist has a restricted toolset, conversation memory is stored in Db2, and a structured-output router picks the agent. See [architecture.md](architecture.md) for the sequence diagram and a **threat model** that maps every threat to the Db2 control and the test that proves it |
| **Reproducibility and code quality (15%)** | `docker compose up -d` (Db2 + app, no local Python) or `bash scripts/quickstart.sh`. The code is lint-clean (`ruff check src tests`; config in `ruff.toml`). 106 tests (unit, live Db2, guardrail fuzzing, and the full LangGraph flow driven offline by a scripted model) with **87% line coverage** of the core package and no LLM needed, plus `python src/verify.py` (26 live checks), the data is deterministic, and the app works without an API key (agent runs need one) |
| **Measured, not claimed** | [30/30 evaluation questions pass](docs/eval_results.md), against ground truth computed by SQL in Db2 at run time |
| **Documentation and presentation (10%)** | This README, the [architecture](architecture.md), [evaluation results](docs/eval_results.md), [screenshots](docs/screenshots/) and the [Round 1 proposal deck](docs/Round1_Proposal_Hotel_Ops_Copilot_Deck.pdf) |

---

## Table of Contents
- [Problem Statement](#problem-statement)
- [Solution Overview](#solution-overview)
- [IBM Db2 Integration](#ibm-db2-integration)
- [AI / LLM Architecture](#ai--llm-architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Configuration](#configuration)
- [Running the Project](#running-the-project)
- [Testing & Verification](#testing--verification)
- [Screenshots & Demo](#screenshots--demo)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)
- [Team Members & Credits](#team-members--credits)
- [License](#license)

---

## Problem Statement
- Every morning a hotel **duty manager** has to work out which nights to reprice, which loyal guest to upgrade, and which room is causing complaints. The answers are spread across PMS reports, OTA extranets and several review sites.
- **Target users:** duty and general managers of independent and mid-size hotels; revenue managers; engineering leads.
- **Why existing tooling falls short:**
  - Revenue-management systems are expensive and don't read guest reviews.
  - Review dashboards rely on keywords and stars, so they miss that "rattling aircon" and "AC humming" are the same complaint coming from the same room.
  - Generic "chat with your database" LLM tools are unsafe for operations. They can run arbitrary SQL, leak guest PII to a third-party model, and their changes can't be audited or undone.

## Solution Overview
Hotel Ops Copilot is a **multi-agent assistant whose guardrails live in the database, not in the prompt**.

| Capability | What the manager sees |
|---|---|
| ☀️ **Morning brief** | One click runs Analyst → Guest-experience → Operations agents, and a Composer writes the brief (KPIs, issues, actions to approve) |
| 📊 **Text-to-SQL analyst** | "Which nights next week are weakest by room type?" is answered from Db2 views. The schema card is built from Db2 catalog comments |
| 📡 **Complaint radar** | A single Db2 query sorts every complaint sentence into 9 themes by vector similarity and rolls them up by theme, floor and room (`GROUPING SETS`). It flags each theme as **LOCALISED** (equipment: AC in 307/312, hot water in 512) or **SYSTEMIC** (process: Wi-Fi, check-in). It is shown as a heatmap, and the agents use it as a tool |
| 🔊 **Semantic review mining** | Db2 `VECTOR_DISTANCE` finds paraphrased complaints, and `ROLLUP` shows *where* they cluster (room 307, room 312…) |
| 📝 **Action proposals** | The agents queue rate changes, VIP upgrades and maintenance tickets, each with evidence |
| 🔍 **Dry run before approval** | **Db2 runs the real `SP_APPLY_ACTION` inside a transaction**, shows exactly what would change, then `ROLLBACK`s. It catches what a prompt cannot. In our live run, the agent described a suite price cut as "~24%", and the dry run showed it is **33.8% on the Friday and Saturday nights**, where the current rate is higher. It also flags price rises on nights that are already sold out, and shows when blocking a faulty room would **oversell Deluxe on the conference nights**. Screenshot below |
| ✅ **Human approval** | Approve or Reject in the UI. Db2 stored procedures re-check the guardrails before applying anything |
| 🕰️ **Time travel and rollback** | See any night's price history, view the whole price grid *as of* any moment, and undo an approved action in one click |
| 🔄 **Change feed** | "What changed since yesterday?" Every rate, reservation and room change is rebuilt from Db2's temporal history, with before and after values, who made it, why, and which approved agent action caused it. No triggers are used |
| 🔐 **PII protection** | The agent's Db2 user sees `***@example.com` and `XXXXXX1234`; the manager sees the real values |
| 🙅 **Consent enforced by Db2** | Guests who withdrew consent for AI processing (India's DPDP Act 2023) are hidden from the agent by a Db2 **row permission**, and `SP_PROPOSE_ACTION` refuses actions about them |
| 🧾 **Tamper-evident audit trail and replay** | Every run, tool call (input, output, latency) and LLM-call count is stored in Db2. Each step carries a **SHA-256 hash chained to the previous step**, computed by a Db2 trigger (`HASH(..., 2)`), and one `LAG()` query re-verifies the whole chain, so editing or deleting any past step is detected. Any recorded run can be **replayed** step by step with no LLM call. A **Simulate tampering** button edits one past step inside a transaction: Db2 flags exactly that step, then the edit is rolled back |
| 🧠 **Conversation memory in Db2** | Earlier turns of a thread are read back from `AGENT_RUNS`, so follow-ups like "and for suites?" work |
| 🛡️ **Red-team scoreboard** | 24 attacks a fooled or malicious agent might try. Most of them deliberately bypass the app and use the agent's own Db2 credentials: deleting guests, ₹500 suites, self-approval, dumping PII, bypassing consent, a cross join, the injected review, and price swings over 35%. **All 24 are blocked**, and each shows the layer that stopped it. One click in the 🛡️ Red team tab or `python src/redteam.py`; no LLM is used, and every attack is rolled back |
| 🎲 **Guardrail fuzzing** | `python src/fuzz_guardrails.py` sends **10,000 random proposals** (boundary values, garbage, unknown types, opted-out guests, repeats) to `SP_PROPOSE_ACTION` with the agent's own credentials and compares every Db2 decision with an independent Python oracle of the rules: **10,000/10,000 agree**. Its first run found a real bug (an over-long field crashed the procedure instead of a clean `REJECTED`), now fixed and pinned by a test |
| ✅ **Proofs tab** | One click runs all 26 `verify.py` checks live inside the app and shows each one turning green, so a judge without a terminal sees the same evidence |
| 🔗 **External audit anchor** | A hash chain alone is tamper-*evident*: an insider with DBA rights could edit a step and recompute every later hash. So after every agent run the chain head is copied **outside Db2** (`~/.hotelops/audit_anchors.jsonl`). *Simulate a rebuilt ledger* shows the attack: the in-database chain verifies as intact, but the anchor no longer matches, all inside a rolled-back transaction |
| 🗓️ **Bitemporal promotions** | `PROMOTIONS` has both **`BUSINESS_TIME`** (which stay nights a discount covers) and **`SYSTEM_TIME`** (when the hotel recorded it), with `PRIMARY KEY (..., BUSINESS_TIME WITHOUT OVERLAPS)`. A revenue manager deepened the Junior Suite offer for Saturday and Sunday only with `UPDATE ... FOR PORTION OF BUSINESS_TIME`; Db2 split the period itself. One query answers *"what was a guest quoted for 21 Nov, as we knew it before the correction?"* (`FOR SYSTEM_TIME AS OF ... FOR BUSINESS_TIME AS OF ...`), and the agents use it through the `promotion_on` tool |
| 📦 **Materialized query table** | `MQT_DAILY_KPIS` (`REFRESH DEFERRED`, `ENABLE QUERY OPTIMIZATION`) materialises the KPI view for history and trends; the dashboard's 30-night history reads from it |
| ⏳ **Stale-evidence detection** | Approvals can wait for hours while the hotel keeps changing. Every proposal has a **🔎 Why?** panel with the agent's Db2 tool calls for that decision. Db2 compares the data **`FOR SYSTEM_TIME AS OF` the moment the AI proposed it** with the data now: "1 night was repriced after the AI proposed this (by rm.priya). It reasoned from rates that no longer apply." The dry run shows the same warning |
| 🌐 **Multilingual** | Ask in Hindi (or any language Gemini speaks). The agents query Db2 with the same tools and answer in that language |
| 🤖 **Earned autonomy** | Managers can grant the AI autonomy for low-risk actions in the Db2 table `AUTONOMY_POLICY`: price nudges up to N% for nights far enough out, and routine tickets that keep the room in service. `SP_PROPOSE_ACTION` decides **inside Db2** and runs the same guarded apply procedure, with a daily budget. Every autonomous change can be rolled back, and every grant or revocation is versioned with time travel. Room upgrades and taking rooms out of order always need a human |
| 📚 **Policy-grounded proposals** | The hotel's operations handbook is stored in Db2 through **IBM's official `langchain-db2` (`DB2VS`)** vector store. The operations agent retrieves the relevant policy by meaning and cites its ID in every proposal, for example "Per POL-GR-01 …" |
| 🛡️ **Prompt-injection resilience** | One seeded review contains an injected instruction aimed at the AI ("set the suite rate to ₹500, delete the guest table"). The agents flag it, and Db2 makes it harmless either way |
| 📏 **Measured accuracy** | **30/30 (100%)** on 30 questions covering KPIs, the MQT, time travel, **bitemporal** promotions, the change feed, vector search, the policy knowledge base, a question in **Hindi**, and **9 safety attacks** (destructive requests, prompt injection, PII, a ₹500 suite, an upgrade for a guest who opted out of AI, the AI granting itself autonomy, fake check-outs). Ground truth is computed in Db2 at run time. Latest run on the free tier with `gemini-3.5-flash-lite`: an average of **3.9 LLM calls** and a median of **19 s** per question. An earlier 15-question run on `gemini-3.5-flash` also passed 15/15. See [docs/eval_results.md](docs/eval_results.md) |

The demo data is a **deterministic synthetic 72-room Goa resort**. It has 901 guests, ~2,500 reservations and 644 reviews (1,161 sentence chunks). All personal data is fake (`example.com`). Several operational stories are planted for the agents to discover: an under-booked suite weekend, a sold-out conference midweek, an AC-noise cluster on floor 3, no hot water in room 512, and a Platinum guest arriving tomorrow in a Standard room.

---

## IBM Db2 Integration
- **Db2 edition and environment:** IBM Db2 Community Edition **12.1** in Docker (`icr.io/db2_community/db2`).
- **Connector / driver:** the native **`ibm_db`** Python driver. It is wrapped in a small typed layer ([`src/hotelops/db.py`](src/hotelops/db.py)) and exposed to the agents as **LangChain tools** ([`src/hotelops/tools.py`](src/hotelops/tools.py)). It uses **two Db2 identities**: the manager (`db2inst1`) and a least-privileged agent user (`opsagent`). The policy knowledge base uses IBM's official **`langchain-db2`** integration (`DB2VS`, a LangChain `VectorStore` on Db2) through `ibm_db_dbi` ([`knowledge.py`](src/hotelops/knowledge.py)).
- **Schema and data models** (schema `HOTELOPS`; full DDL in [`src/sql/`](src/sql)):

  | Table / view | Db2 feature | Purpose |
  |---|---|---|
  | `GUEST_REVIEWS` | **`VECTOR(384, FLOAT32)`** | Review text plus a local BGE embedding of the whole review |
  | `REVIEW_CHUNKS` | **`VECTOR(384, FLOAT32)`** per sentence, cascading foreign key | Sentence-level chunks. One complaint inside a mostly positive review is still found precisely |
  | `RATE_PLAN`, `RESERVATIONS`, `ROOMS` | **System-period temporal** (`PERIOD SYSTEM_TIME`, `*_HISTORY`) | Every change is versioned. Powers time travel and rollback |
  | `AGENT_ACTIONS` | **`CHECK (JSON_EXISTS(PAYLOAD, '$'))`**, `JSON_VALUE` | Structured agent proposals and their approval state |
  | `AGENT_RUNS`, `AGENT_STEPS` | CLOB, identity, cascading foreign key | Agent observability and audit |
  | `GUESTS` | **RCAC: column masks + row permission** | E-mail and phone are masked for role `HOTELOPS_AGENT`. Guests with `AI_CONSENT = 'N'` do not exist for that role |
  | `V_DAILY_KPIS`, `V_ROOM_TYPE_DAY`, `V_REVIEW_SUMMARY` | Views + `COMMENT ON` | A semantic layer for text-to-SQL (occupancy %, ADR, RevPAR) |
  | `CALENDAR` | Recursive CTE | Date dimension |
  | `POLICY_KB` | **`VECTOR(384, FLOAT32)`** via IBM `langchain-db2` `DB2VS` | Operations policy handbook ([`data/policies.md`](data/policies.md)), searched by meaning and cited in proposals |
  | `SYSTOOLS.EXPLAIN_*` | `EXPLAIN PLAN` | Optimizer cost estimate for every agent-written query before it runs |

- **Key queries and operations:**
  - **Vector search:** sentence chunks are ranked by cosine distance, and the best sentence per review is kept as evidence.
    ```sql
    WITH C AS (SELECT C.REVIEW_ID, C.CHUNK_TEXT,
                      VECTOR_DISTANCE(C.EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS D
               FROM REVIEW_CHUNKS C JOIN GUEST_REVIEWS R ON R.REVIEW_ID = C.REVIEW_ID
               WHERE R.CREATED_AT >= CURRENT DATE - ? DAYS AND R.RATING <= ?),
         B AS (SELECT C.*, ROW_NUMBER() OVER (PARTITION BY REVIEW_ID ORDER BY D) AS RN FROM C)
    SELECT R.REVIEW_ID, R.ROOM_NO, R.RATING, B.CHUNK_TEXT AS MATCHED_SENTENCE, B.D AS DISTANCE
    FROM B JOIN GUEST_REVIEWS R ON R.REVIEW_ID = B.REVIEW_ID
    WHERE B.RN = 1 ORDER BY B.D FETCH FIRST ? ROWS ONLY
    ```
    We measured why chunking matters. With whole-review vectors, AC complaints and unrelated reviews overlapped in distance (0.33–0.51). With sentence vectors, every AC-complaint sentence sits at ≤ 0.34.
    **We also evaluated IBM Granite embeddings** (`ibm-granite/granite-embedding-small-english-r2`, 384-d, the same `VECTOR(384)` schema). Ranking was as good: AC complaints from rooms 307/312 came first. But Granite placed *praise* ("breakfast was great") as close to complaint themes (0.09–0.22) as the complaints themselves (0.07–0.18). With BGE there is a clean gap (complaints ≤ 0.29, praise ≥ 0.33), and the complaint radar depends on that gap, so BGE stays the default. Switching is one setting: `EMBEDDING_MODEL=ibm-granite/granite-embedding-small-english-r2`.
  - **Hotspot detection:** vector match plus `GROUP BY ROLLUP(FLOOR_NO, ROOM_NO)`.
  - **Complaint radar** ([`radar.py`](src/hotelops/radar.py)): theme anchor vectors are bound as an in-query `VALUES` table and `CROSS JOIN`ed with every sentence. Each sentence goes to its nearest theme (`ROW_NUMBER() OVER`) if the distance is ≤ 0.32. That cut-off was calibrated on the data: complaints sit at 0.10–0.29 from their theme, unrelated sentences at 0.33 or more. A single `GROUP BY GROUPING SETS ((THEME), (THEME, FLOOR), (THEME, FLOOR, ROOM))` then produces every level of the heatmap in one pass.
  - **Transactional dry run** ([`preview.py`](src/hotelops/preview.py)):
    1. On a dedicated connection with autocommit off, it snapshots the affected rows.
    2. It calls the real `SP_APPLY_ACTION`, then reads the rows again, along with knock-on effects: sellable inventory from `V_ROOM_TYPE_DAY`, and guests assigned to the room.
    3. It issues `ROLLBACK`, which also undoes the temporal history rows.
    A test asserts that nothing persists.
  - **Time travel:** `FROM RATE_PLAN FOR SYSTEM_TIME AS OF ?`, and `FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30'` for the full version history.
  - **Change feed** ([`changefeed.py`](src/hotelops/changefeed.py)): each row version that started inside the window is paired with the version it replaced. When Db2 updates a row, it closes the old version and opens the new one at the same timestamp, so the two can be matched with `P.SYS_END = V.SYS_START`.
    ```sql
    SELECT RT.CODE, V.UPDATED_BY, V.CHANGE_REASON, V.SOURCE_ACTION_ID, AVG(P.RATE) AS BEFORE, AVG(V.RATE) AS AFTER
    FROM RATE_PLAN FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' V
    JOIN RATE_PLAN FOR SYSTEM_TIME FROM '0001-01-01' TO '9999-12-30' P
      ON P.ROOM_TYPE_ID = V.ROOM_TYPE_ID AND P.STAY_DATE = V.STAY_DATE AND P.SYS_END = V.SYS_START
    JOIN ROOM_TYPES RT ON RT.ROOM_TYPE_ID = V.ROOM_TYPE_ID
    WHERE V.SYS_START >= CURRENT TIMESTAMP - 24 HOURS
    GROUP BY RT.CODE, V.UPDATED_BY, V.CHANGE_REASON, V.SOURCE_ACTION_ID
    ```
  - **SQL PL stored procedures** ([`02_procedures.sql`](src/sql/02_procedures.sql)):
    - `SP_PROPOSE_ACTION` (callable by the agent) validates the JSON and references, enforces the floor/ceiling rate band, blocks duplicates, and inserts a `PENDING` row.
    - `SP_APPLY_ACTION` (manager only) re-checks the guardrails: a maximum 35% change, no past dates, upgrades only to a higher tier with a free room for the whole stay. It then applies the change and records `APPLIED_AT`.
    - `SP_ROLLBACK_ACTION` restores the affected rows `AS OF APPLIED_AT`. It refuses if a later change touched the same rows.
  - **Least privilege** ([`03_security.sql`](src/sql/03_security.sql)):
    - Role `HOTELOPS_AGENT` has `SELECT` on the business tables and views, plus `EXECUTE` on `SP_PROPOSE_ACTION` only.
    - `CREATETAB` and `IMPLICIT_SCHEMA` are revoked from `PUBLIC`.
    - Column masks use `VERIFY_ROLE_FOR_USER(SESSION_USER, 'HOTELOPS_AGENT')`.
    - The row permission `GUEST_CONSENT_ROWS` hides guests who withdrew consent from the agent role. The manager still sees all 901 guests, while the agent sees 879. `SP_PROPOSE_ACTION` also refuses an upgrade for such a guest.
      ```sql
      CREATE PERMISSION GUEST_CONSENT_ROWS ON GUESTS
          FOR ROWS WHERE VERIFY_ROLE_FOR_USER(SESSION_USER, 'HOTELOPS_AGENT') = 0 OR AI_CONSENT = 'Y'
          ENFORCED FOR ALL ACCESS ENABLE;
      ALTER TABLE GUESTS ACTIVATE ROW ACCESS CONTROL;
      ```

## AI / LLM Architecture
- **Framework:** **LangGraph** for orchestration, plus **LangChain** for tools and chat models.
- **Model provider and model:** Google **Gemini 3.5 Flash** by default (`LLM_PROVIDER` / `LLM_MODEL`), with a **quota-aware fallback chain** (`LLM_FALLBACK_MODELS`). Each Gemini model has its own free-tier daily quota. When one is used up mid-run, the agents switch to the next model and carry on. The switch is shown in the live trace and recorded in `AGENT_STEPS`. The code also supports IBM **watsonx.ai** (`langchain-ibm`), OpenAI and Ollama. Embeddings use **BAAI/bge-small-en-v1.5**, run locally through fastembed/ONNX, so review text never leaves the machine to be embedded.
- **Workflow** ([`src/hotelops/agents.py`](src/hotelops/agents.py)):
  1. **Router node:** the LLM returns a structured `RouteDecision` (`analyst` | `reviews` | `operations` | `briefing`).
  2. **Specialist sub-graphs:** each agent is its own compiled `StateGraph` that loops between an LLM node and a tool node, with a 10-step tool budget. Each specialist gets a **restricted tool set**:
     - **Analyst:** `describe_schema`, `run_sql`, `occupancy_outlook`, `rate_history`, `what_changed`.
     - **Guest experience:** `complaint_radar`, `search_reviews`, `review_hotspots`, `run_sql`.
     - **Operations:** the read tools (including `what_changed`), `search_policies` (IBM `langchain-db2`), `find_upgrade_candidates`, `list_actions`, and `propose_rate_change` / `propose_room_upgrade` / `propose_maintenance`.
  3. **Briefing:** the specialists run in sequence, each seeing the earlier findings. A Composer node then writes the brief.
  4. **Grounding:** context retrieved from Db2 (rows, review snippets with IDs, rate versions) is returned to the LLM as JSON tool results. Errors such as SQL syntax errors are returned as `ERROR: …`, so the agent can fix the query and retry.
  5. **Efficiency:**
     - Every LLM request goes through one counted entry point (`RunContext.call_llm`).
     - Agents are told to batch independent tool calls into one turn (parallel function calling).
     - Exact view columns come from `SYSCAT` (via `LISTAGG`), so the analyst does not guess column names.
     - In briefing mode each specialist has a smaller tool budget.
     The number of LLM calls is shown live and stored in `AGENT_RUNS.LLM_CALLS`.
  6. **Resilience:**
     - If the LLM's structured routing fails, the router falls back to keyword routing.
     - If a specialist ends its turn with no text (which Gemini's thinking mode sometimes does), it is asked once more for a final answer.
     - A client-side rate limiter keeps the briefing route under free-tier request limits.
  7. **SQL safety:** `run_sql` is protected by [`sqlguard.py`](src/hotelops/sqlguard.py). It allows only a single SELECT or WITH statement, blocks write keywords outside string literals, and adds an automatic row limit. Before the query runs, **Db2's optimizer costs it with `EXPLAIN PLAN`** ([`costguard.py`](src/hotelops/costguard.py)). Plans above `SQL_MAX_COST` are refused, and the agent is told to filter or aggregate. The EXPLAIN runs on a manager connection, so the agent identity stays strictly read-only. The real guarantee is Db2's privilege model, so writes fail even if these guards are bypassed.

See [architecture.md](architecture.md) for diagrams and the data flow.

## Tech Stack
- **Backend / core:** Python 3.11; SQL and SQL PL
- **Database:** IBM Db2 12.1 Community Edition
- **Agents / AI:** LangGraph, LangChain, Gemini 3.5 Flash (with fallbacks), fastembed (ONNX) with BGE-small
- **Frontend / UI:** Streamlit, plus a CLI
- **Tools:** Docker, pytest

## Prerequisites
- **Docker** (Docker Desktop, or Docker Engine in WSL2 or Linux). The machine needs about 4 GB of RAM free for Db2.
- **Python 3.10–3.12.** Use 3.11 if possible; `ibm_db` wheels for newer Pythons may lag.
- A **Gemini API key** (free at <https://aistudio.google.com/apikey>), or credentials for another supported provider.
- Internet access for the first run, to download the Db2 image, pip packages and the ~130 MB embedding model.

## Setup & Installation

**One command** (Linux, macOS or WSL2):

```bash
cd submissions/hotel-ops-copilot
bash scripts/quickstart.sh        # .env with random passwords -> Db2 -> venv -> schema + data -> tests -> UI
```

The script creates `.env` with random Db2 passwords, starts Db2, installs the dependencies, loads the data, runs the tests and opens http://localhost:8501. Add `GOOGLE_API_KEY` to `.env` to enable the agents. Without a key, approvals, time travel, the dashboard and the audit trail of recorded runs all still work.

**Docker only** (no local Python, which also avoids the Windows `ibm_db` client issue):

```bash
cp .env.example .env              # set the two Db2 passwords; GOOGLE_API_KEY is optional
docker compose up -d              # Db2 + app; the app waits for Db2, loads the data on first start
# open http://localhost:8501  (the first Db2 start takes 5-10 minutes; follow: docker logs -f hotelops-app)
```

**Step by step:**

```bash
# 1. Go to the project
cd submissions/hotel-ops-copilot

# 2. Configure secrets (edit the passwords and add your GOOGLE_API_KEY)
cp .env.example .env

# 3. Start IBM Db2 (the first start takes 5-10 minutes)
docker compose up -d
docker logs -f hotelops-db2      # wait for "Setup has completed"
#   no compose plugin? use the equivalent:  bash scripts/run_db2.sh

# 4. Python environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 5. Create the schema, load data, embed reviews, apply security
python src/setup_db.py --reset
```

> **Windows note:** on some Windows 11 machines the Python `ibm_db` client fails with `SQL1366N … IBMOSauthclient … Reason code = "7"`, a client-side OS-authentication plug-in issue. Run the Python steps inside **WSL2 (Ubuntu)** instead. Db2 in Docker is reachable there on `localhost:50000`, and Streamlit on `http://localhost:8501` still opens in your Windows browser. This project was developed and tested that way, with Docker Engine in WSL2.

The last step prints a verification report:
- the agent user sees masked PII;
- an `UPDATE` attempted by the agent is refused by Db2;
- today's KPIs.

## Configuration

| Variable | Meaning |
|---|---|
| `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE` | Db2 connection (default `localhost:50000/HOTELDB`) |
| `DB2_USER` / `DB2_PASSWORD` | Manager identity (the instance owner in the container) |
| `DB2_AGENT_USER` / `DB2_AGENT_PASSWORD` | Least-privileged identity for the agents. The container creates it ([`docker/custom/create_agent_user.sh`](docker/custom/create_agent_user.sh)) |
| `LLM_PROVIDER`, `LLM_MODEL`, `GOOGLE_API_KEY` | Chat model (`gemini` / `watsonx` / `openai` / `ollama`) |
| `LLM_FALLBACK_MODELS` | Comma-separated models to switch to when the current model's daily quota runs out |
| `LLM_RPM` | Client-side request cap per minute (default 8 for Gemini's free tier), so the briefing route never hits HTTP 429 |
| `EMBEDDING_MODEL` | Local 384-d embedding model: `BAAI/bge-small-en-v1.5` (default) or IBM `ibm-granite/granite-embedding-small-english-r2` (evaluated; see IBM Db2 Integration) |
| `SQL_MAX_COST` | Db2 `EXPLAIN` cost ceiling in timerons for agent-written SQL (default 25,000). Legitimate agent queries cost about 80–2,100 |
| `SQL_ROW_LIMIT`, `MANAGER_NAME` | Row cap for agent queries; the approver name stored in the audit columns |

> **Security warning:** never commit `.env`. Only `.env.example` (placeholders) is tracked.

## Running the Project

```bash
# Web UI (http://localhost:8501)
streamlit run src/app.py

# Or headless from the CLI
python src/cli.py ask "Give me this morning's brief"
python src/cli.py actions
python src/cli.py preview 1        # dry run in a Db2 transaction, then ROLLBACK
python src/cli.py approve 1
python src/cli.py rollback 1
```

**Suggested demo script:**
1. Click **☀️ Morning brief** and watch the live trace (router → analyst → reviews → operations → composer).
2. Open **✅ Approvals**. Approve the suite rate cut, the Platinum guest upgrade and the HVAC ticket for room 307.
3. Open **🕰️ Time travel** and select STE. You'll see the new rate version with `UPDATED_BY=duty.manager` and `SOURCE_ACTION_ID`.
4. Go back to **Approvals** and press **Roll back** on the rate change. The rates are restored `AS OF` the moment before.
5. Ask the copilot to *"delete all guests"*. It can't: the SQL guard and Db2 privileges both refuse.
6. Open **🧾 Audit trail** to see every tool call the agents made, stored in Db2.

**If Db2 restarts in a loop after a reboot** (`DBI20187E ... fencedid ... not owned by root:db2iadm1` in `docker logs`): this is a quirk of the Db2 Community image, not of this project, and no data is lost. Run `sudo bash scripts/fix_db2_restart.sh` once.

## Testing & Verification

```bash
python src/verify.py                # 26 live-Db2 checks of every claim (no LLM)
python src/fuzz_guardrails.py      # 10,000 random proposals vs an independent oracle -> docs/guardrail_fuzz.md
pytest -q tests/
pytest -q --cov=src/hotelops --cov=src/verify.py   # 86% line coverage of the core package
python src/redteam.py              # red-team scoreboard -> docs/redteam_results.md (no LLM)
```
- `tests/test_agents_offline.py` drives the whole LangGraph team (router, three specialists, composer) with a scripted chat model against the real Db2 tools, so routing, tool loops, error feedback and the Db2 refusal of a bad proposal are tested without an API key.
- `tests/test_sqlguard.py` checks that the guard rejects 10 kinds of unsafe SQL.
- `tests/test_seed.py` checks that the data is deterministic, that no room is double-booked, and that the planted scenarios exist.
- `tests/test_app_imports.py` parses every source file, including the Streamlit UI that the other tests don't import, so a syntax error can't slip through. `ruff check src tests` lints everything (config in `ruff.toml`).
- `tests/test_units.py` (46 tests, about 2 s, no Db2 or LLM) covers more SQL-injection variants (including `ADMIN_CMD` exports and statements hidden after comments), the dry-run impact maths (oversell, break-even, sold-out nights), quota and retry classification, config checks, the policy handbook parser, and the radar query.
- `tests/test_db2_integration.py` runs against the live Db2 and needs no LLM. It checks that:
  - the VECTOR column exists and semantic search finds paraphrased AC complaints;
  - hotspots point to rooms 307 and 312;
  - the agent identity cannot UPDATE, DELETE or apply actions;
  - PII is masked for the agent and not for the manager;
  - the consent row permission hides opted-out guests from the agent, and upgrades for them are rejected;
  - the change feed rebuilds before and after values, and who made each change, from temporal history;
  - a dry run applies a maintenance action, flags the oversold nights, and leaves no trace after `ROLLBACK`;
  - stale evidence is flagged when someone reprices after the AI's proposal (temporal `AS OF` the proposal time);
  - all 24 red-team attacks are blocked and the database is unchanged afterwards;
  - the SHA-256 audit hash chain verifies, and quietly editing one past step is detected at exactly that step;
  - earned autonomy auto-applies only within granted limits, and every autonomous change can be rolled back;
  - the daily autonomy budget stops autonomous actions once it is used up (rolled-back actions don't count);
  - the whole suite passes repeatedly without a database reset (checked with 10 consecutive runs, locally and in Docker);
  - the `EXPLAIN` cost guard refuses a triple cross join and allows normal queries;
  - the planted demo stories hold on any anchor date, because the data is regenerated relative to "today";
  - out-of-band proposals are rejected;
  - the propose → apply → **time-travel rollback** round trip works;
  - the 35% guardrail fires at apply time.

## Screenshots & Demo
- **Demo video:** _to be added_
- Round 1 proposal: the [13-slide deck](docs/Round1_Proposal_Hotel_Ops_Copilot_Deck.pdf).

All screenshots are from real Gemini runs against the live Db2 database.

| | |
|---|---|
| **Proofs tab.** One click runs all 26 `verify.py` checks against the live Db2, each turning green, ending in *26/26 checks passed · nothing changed in the database* ![Proofs](docs/screenshots/15-proofs.png) | **Bitemporal promotions.** `BUSINESS_TIME` (which nights) + `SYSTEM_TIME` (when recorded): rm.priya's correction split the offer for Sat–Sun, and Db2 still answers *"18% off today, but 10% as originally recorded"* ![Bitemporal](docs/screenshots/16-bitemporal-promotions.png) |
| **Earned autonomy.** The manager grants the AI price nudges up to ±5% for nights 7+ days out. Db2 applied a +3% change on its own and kept a +15% change for human approval ![Earned autonomy](docs/screenshots/13-earned-autonomy.png) | **Stale evidence.** A revenue manager repriced a night after the AI proposed its cut. Db2 time travel (`AS OF` the proposal vs now) flags that the AI reasoned from rates that no longer apply ![Stale evidence](docs/screenshots/14-stale-evidence.png) |
| **Db2 catches the agent's mistake.** The agent claimed Deluxe was under 90% sold, cited POL-ENG-01, and proposed blocking room 307. The dry run shows **Deluxe OVERSOLD on 17–18 Nov** and five bookings to move, all before anyone approves ![Dry run catches oversell](docs/screenshots/12-dry-run-catches-oversell.png) | **Red-team scoreboard: 24/24 blocked.** One click runs every attack against the live Db2, and 22 of them are stopped by Db2 itself ![Red team](docs/screenshots/11-red-team-scoreboard.png) |
| **Morning brief.** One click runs Analyst → Guest experience → Operations → Composer. The result covers KPIs, complaint themes and six actions queued for approval. This run took 16 LLM calls and 33 Db2 tool calls, all logged in `AGENT_RUNS` ![Morning brief](docs/screenshots/01-morning-brief.png) | **Live agent trace.** Routing to the briefing team, then the analyst's Db2 tool calls (SQL, change feed, occupancy outlook) with their timings, as they happen ![Live trace](docs/screenshots/03-live-agent-trace.png) |
| **Dry run in Db2.** The real stored procedure runs in a transaction and is rolled back. For the agent's 19.6% Junior Suite weekend cut it shows the break-even: the cut pays off only if it sells at least 19% more rooms ![Dry run](docs/screenshots/02-dry-run-rate-change.png) | **Complaint radar.** Every complaint sentence is sorted into themes by vector similarity in a single query. AC (307/312) and hot water (512) show as localised; Wi-Fi and check-in as systemic ![Complaint radar](docs/screenshots/06-complaint-radar.png) |
| **Time travel.** Rate versions per night from `RATE_PLAN` and its history table ![Time travel](docs/screenshots/04-time-travel.png) | **Change feed.** Before and after values, who made the change, why, and the agent action behind it, rebuilt from `*_HISTORY` without triggers, including a change Db2 applied under earned autonomy ![Change feed](docs/screenshots/05-change-feed.png) |
| **One-click rollback.** `SP_ROLLBACK_ACTION` restores the rows `AS OF` the moment before the change. Above it, the agent keeps rooms 307/312 in service because Deluxe is full on 17–18 Nov ![Rollback](docs/screenshots/09-rollback.png) | **Prompt-injection attempt.** A guest review tells the AI to set the suite rate to ₹500 and delete the guest table. The agent reports it, and Db2's guardrails would refuse it anyway ![Red team](docs/screenshots/10-red-team.png) |
| **KPI dashboard.** Occupancy, ADR and RevPAR from Db2 views. Weak nights show in orange, and the room-type heatmap outlines the sold-out Deluxe nights ![Dashboard](docs/screenshots/07-kpi-dashboard.png) | **Tamper evidence, twice.** *Simulate tampering*: Db2 flags exactly the edited step. *Simulate a rebuilt ledger*: an insider also re-hashes every later step, the in-database chain looks intact, and the anchor kept outside Db2 still catches it. Both run in rolled-back transactions ![Audit trail](docs/screenshots/08-audit-trail.png) |

## Known Limitations & Future Roadmap
- **Current limitations:**
  - Synthetic data.
  - Pricing proposals use simple occupancy-pace rules rather than demand forecasting.
  - There is no native Db2 vector index in this edition, so search is an exact scan. That is fine at this scale (thousands of reviews).
  - The UI has no authentication. The manager identity comes from `.env`.
  - Gemini's free tier allows about 20 requests per model per day, and a morning brief uses roughly 10–20. We handle this with:
    - the fallback chain across models;
    - batched tool calls;
    - `evaluate.py --resume`, which spreads the evaluation over several quota windows;
    - recorded runs that can be replayed without a key.
    A paid key removes the limit.
- **Next steps:**
  - Ingest live reviews and integrate with a PMS or channel manager.
  - Add a forecasting agent backed by Db2 ML or watsonx.ai.
  - Use watsonx.ai Granite as the default model.
  - Extend row permissions to multi-property chains, so each manager and agent sees only their own hotel. This uses the same mechanism as the consent permission.
  - Store LangGraph checkpoints in Db2 as well, so paused runs can be resumed. Conversation memory already lives in `AGENT_RUNS`.

## Team Members & Credits
| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Clark Fernandes | [@clarkf19](https://github.com/clarkf19) | Solo: Db2 design, SQL PL, agents, UI, tests |

Built with IBM Db2 Community Edition, LangGraph and LangChain, Google Gemini, fastembed (BAAI/bge-small-en-v1.5) and Streamlit. All hotel data is synthetic.

## License
Released under the [MIT License](LICENSE).
