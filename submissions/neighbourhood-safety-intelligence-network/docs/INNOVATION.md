# What's new in NSIN

Neighbourhood safety apps usually stop at "send an alert". NSIN treats a neighbourhood emergency as **data that must be prioritised, grounded, measured and audited**. It does that inside IBM Db2, with AI that runs on the residents' own infrastructure.

## 1. Db2 is the engine, not just the storage
One Db2 database does the work that usually needs four systems: a relational store, a vector database, an analytics service and a document store.

| Job | Usually done by | In NSIN |
|---|---|---|
| Incidents, history, audit | Postgres / MySQL | Db2 tables, transactions, constraints |
| Semantic search | A separate vector DB | Db2 `VECTOR(768)` + `VECTOR_DISTANCE` |
| Metadata filtering | Document DB / app code | Db2 BSON + `JSON_VALUE` |
| Response-time analytics | Python / BI tool | Db2 `MEDIAN`, `PERCENTILE_CONT`, `RANK() OVER` |
| Access control for the app | App code | Db2 role `NSIN_APP` (data-only, append-only audit) |

**Why it matters:** one system to secure, back up and audit. Search, analytics and records can't drift apart, because they're the same rows.

## 2. Three IBM Db2 AI integrations working together
NSIN uses IBM's official Db2 integration for three agent frameworks, each for the job it suits:

- **Haystack, `ibm-db-haystack`:** hybrid protocol search. Db2 vector retrieval is fused with BM25 by `DocumentJoiner`, with metadata filters, and every answer cites the passage it came from.
- **CrewAI, `crewai-tools` `DB2VectorSearchTool`:** a Granite-powered *Protocol Advisor* agent searches Db2 on its own while writing a responder briefing.
- **LangChain, `langchain-db2` `DB2VS`:** a vector store for incident reports that finds duplicate and related reports before anyone dispatches.

## 3. AI you can trust in an emergency
Safety software can't hallucinate. NSIN layers its AI so the dependable part always wins:

1. **Deterministic first.** A CrewAI Flow with whole-word rules sets the priority. It has 10 regression cases for wording traps, for example that "person" must not match "son".
2. **Grounded second.** Retrieval only returns protocols that pass a **calibrated** distance cutoff. With Granite embeddings, relevant questions score ≤ 0.435 and off-topic ones ≥ 0.488. The cutoff is 0.46, measured on our data, not guessed.
3. **Generative last.** Granite agents explain and advise using the retrieved passages, and the answer is checked for a cited protocol (`grounded: true/false`).
4. **Fails safe.** If the model is down, the rule-based triage is still returned with a clear `briefing_error` (tested by making Ollama unreachable).

## 4. Measured, not claimed
"Average response time: 4.8 minutes" was a hard-coded number in the original prototype. NSIN now **measures** it in Db2 SQL:
- time to first acknowledgement per priority (median and 90th percentile);
- compared against SOP targets (P1 2 min, P2 15 min, P3 60 min);
- live SLA breaches for reports nobody has claimed;
- hotspots ranked with `RANK() OVER`.

A test fixes a timeline (acknowledgements after 2, 7 and 11 minutes) and asserts Db2 returns exactly median 7.0 and p90 10.2 (`test_db2_sql_analytics_compute_exact_median_and_p90`).

## 5. Duplicate-report detection
When three neighbours report the same dark street, responders see one incident with two related reports. They don't get three dispatches. Related reports at the **same address rank first**, because two "streetlight broken" reports on different lanes are similar in meaning but are not duplicates.

## 6. Privacy as an architecture decision
- **IBM Granite runs locally** through Ollama, and no resident text reaches a cloud AI.
- Library telemetry is disabled.
- Other residents see community alerts without the reporter's name or exact location.
- Responders' live GPS is never shown to residents.

## 7. Proven with real infrastructure
Every backend test runs against a **real IBM Db2 12.1** and a **real local Granite model**. Nothing is mocked and there is no SQLite. The whole suite also passes as the **least-privilege Db2 login**, which proves the app needs no DDL rights at runtime. See [TESTING.md](TESTING.md).

## 8. A live demo of the real system, not a recording
Most hackathon demos are videos or mock-ups. On our landing page the **real web app** runs inside a phone frame, a desktop browser frame and a full-screen view. It talks to the real backend (IBM Db2 12.1 + Granite) through a secure tunnel. A judge can sign in as a resident, report an incident and watch Granite triage it against Db2 in real time. When the machine is off, the page says so honestly and shows **recorded real responses**, each with the date and Db2 version it came from. See [LIVE_DEMO.md](LIVE_DEMO.md).

## 9. One address book for every client
The web app and the Android app both read the backend URL from one small file, `live.json`, when they start. Moving the backend means changing one line, not rebuilding two apps. The APK therefore works on a real phone out of the box, and a tester never has to type an IP address.

## 10. Designed for calm, not alarm
The interface uses a light "hope" theme: warm paper, a dawn accent and calm blue, with a full dark mode. Safety tools are used by frightened people. The design keeps the one action that matters (SOS) obvious, and keeps everything else quiet.

## Who benefits

| Person | Before | With NSIN |
|---|---|---|
| Woman walking home at night | Messages a group and hopes someone reads it | Two-taps an SOS: a P1 incident with location, routed to on-duty verified responders |
| Elderly person living alone | A missed call goes unnoticed | "Not answering since last night" is triaged P2 with the elder-care protocol cited |
| Parent | Calls around when a child is late | The journey is flagged `delayed` automatically, by a set-based Db2 `UPDATE` |
| Volunteer responder | Scrolls a chat to find what's urgent | A P1-first queue, related reports linked, and a cited briefing |
| RWA admin | No idea how fast help arrives | Median and p90 response times and hotspots, measured in Db2 |
