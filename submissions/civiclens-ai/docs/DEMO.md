# CivicLens AI: demonstration (about 4 minutes)

> **What you are shown is real:** the production build of the dashboard, the real FastAPI backend, a real IBM Db2 12.1 database and real OpenStreetMap tiles. All complaint data is **synthetic** and labelled as such.
> **What you are *not* shown, on purpose:** output from a language model. No LLM provider is configured, so every recommendation is either **"Rule-based · no LLM"** or **"Manual · analyst-written"**. Real-LLM verification is **BLOCKED** (no credentials); see [`PHASE_02_RELEASE_REPORT.md`](PHASE_02_RELEASE_REPORT.md).

## The recording

[`demo/civiclens-demo.mp4`](demo/civiclens-demo.mp4): a **silent, captioned screen recording** of the real application (1280×720, 3 min 46 s, 4.4 MB).

* The captions are text overlays added by the recording script (`src/frontend/e2e/demo.spec.ts`); they only describe what the app is doing at that moment.
* **No credential is ever on screen.** The browser session is signed in off camera (the sign-in screen never appears, nothing is typed or pasted), and the app never renders a token. The file contains pixels only.
* It is not edited or composited. Everything in it happened live: a new investigation is created, evidence is attached, the rule-based investigator runs, a second person approves the recommendation, and the audit trail is read back from Db2.
* To record it again (demo workflow seeded, API and preview running): `cd src/frontend && npm run demo`. Afterwards reset with `python src/backend/scripts/cleanup_test_data.py --workflow --yes`.
* For a voice-over, read the *Say* column below. It is written to be spoken over the same sequence.

## Walkthrough

| # | Topic | On screen (genuine screenshot) | Say |
|---|---|---|---|
| 1 | **The real-world problem** (0:00) | Intelligence overview ([02](screenshots/02-intelligence-overview.png)) | "A city receives thousands of infrastructure complaints: potholes, water leaks, broken streetlights. Many are duplicates of one underlying fault, and clusters stay invisible when you read ticket by ticket. Engineers need to see where the problems concentrate and why a crew should go there first. All data you will see is synthetic." |
| 2 | **The IBM Db2 architecture** (0:25) | Operational status panel ([02](screenshots/02-intelligence-overview.png)); `architecture.md` diagram | "IBM Db2 is the only store. The browser talks only to a FastAPI service; the service talks to Db2 through `ibm_db` with bound parameters. Db2 does real work: the great-circle distance for duplicate detection is computed in SQL, hotspots are a `GROUP BY` over grid cell and category, the review is one atomic transaction, evidence integrity is enforced by a composite foreign key, a unique index stops double decisions, and every action lands in an append-only audit table." |
| 3 | **Geographic hotspot detection** (1:00) | Map ([03](screenshots/03-geographic-intelligence.png), [04](screenshots/04-geographic-hotspot-selected.png)) | "Each marker is a complaint; a dashed ring means synthetic. The rectangles are the grid cells Db2 aggregated: three or more complaints of one category in one cell within the last 30 days. Filtering to water leaks and selecting the hotspot centres the map on exactly the cell Db2 counted." |
| 4 | **Investigation and evidence retrieval** (1:35) | Workspace ([08](screenshots/08-investigation-results.png), [18](screenshots/18-new-investigation.png), [19](screenshots/19-attach-evidence.png), [09](screenshots/09-investigation-run-options.png)) | "An investigation is a question, the evidence gathered from Db2, and an audit trail. The investigator can only use four read-only, allow-listed tools; each runs one fixed, parameterized query, and every call is logged with who issued it, the arguments and the row count. A recommendation may only cite evidence that is attached to the investigation: the application checks it, and Db2's foreign key checks it again." |
| 5 | **Recommendation generation and provenance** (2:30) | Run result ([20](screenshots/20-investigation-run-result.png)) | "No language model is configured, so *Auto* mode uses the rule-based fallback, and the result says so: 'NO LLM WAS USED', and why. The recommendation names its author, cites its evidence, starts as *Awaiting review*, and its score is a data-volume heuristic, not a model probability." |
| 6 | **Human review and audit history** (3:00) | Review ([10](screenshots/10-human-review-queue.png), [21](screenshots/21-review-confirm.png), [22](screenshots/22-review-approved.png)); errors ([23](screenshots/23-error-409-already-decided.png), [24](screenshots/24-error-403-forbidden.png)) | "The system can only propose. A different person, signed in as a reviewer, reads the explanation and the evidence and approves or rejects, after a confirmation that names who the decision will be recorded as. Db2 records the decision, the reviewer, the time and an audit entry in one transaction. If two reviewers race, the second gets a clear 409 and nothing changes; an analyst token is refused with a 403." |
| 7 | **Real LLM output versus deterministic fallback** (3:35) | Agent transparency ([13](screenshots/13-agent-transparency.png)) | "This page counts every recommendation by its stored author. Here, none was written by a language model, and I will not pretend otherwise: real-LLM verification is blocked because no provider credentials exist. If a real model had run, its output would appear as 'AI model (LLM)' with provider and model, and the agent loop would still have to ground every cited complaint in a tool result. Rule-based and analyst-written output can never be shown as AI." |

## Real LLM output versus deterministic fallback (what a reviewer should take away)

| | **Real LLM output** | **Deterministic fallback** | **Manual** |
|---|---|---|---|
| Stored as | `generator_type = LLM`, `model_name = provider:model` | `DETERMINISTIC_FALLBACK`, rule set `hotspot-rules-v1` | `MANUAL` |
| Shown as | **AI model (LLM)** | **Rule-based · no LLM** | **Manual · analyst-written** |
| Who decides what to look at | The model, through the four audited tools | Fixed rules over Db2 aggregates | An analyst |
| Score means | The model's own confidence | A data-volume heuristic (not a probability) | The analyst's estimate |
| Evidence | Must have been *returned by a tool in the same run* | Same | Must be attached to the investigation |
| Status in this build | **Never produced** (BLOCKED: no credentials) | Every automated recommendation | One demo proposal |

If the provider call itself fails (wrong key, unknown model, rate limit, network), *Auto* mode now degrades to the labelled fallback and states the exception class as the reason; *LLM only* mode reports a 502 and the investigation can be retried. Nothing from a failed model call is ever stored as LLM output.

## Likely questions, honestly answered

* **Is any recommendation written by an AI model?** No. No provider is configured. Everything is rule-based or manual, and the UI says so on every card and on the transparency page.
* **Where is IBM Db2 used, and is it more than storage?** Duplicate detection (haversine in SQL), hotspot aggregation (`GROUP BY … HAVING`), dashboard aggregates, composite foreign keys, a unique-index backstop, compare-and-set status transitions, atomic multi-statement review transactions with rollback, catalog-driven migrations and an append-only audit log. 149 backend tests run against a live Db2 with no mocks.
* **How is fabricated evidence prevented?** The orchestrator accepts a cited complaint only if a tool returned it in the same run; the API checks that evidence is attached; and Db2 refuses a recommendation–evidence link that is not attached to the same investigation.
* **Can a model write SQL or approve anything?** No. There is no SQL tool and no write tool; recommendations are persisted by the orchestrator, always as `PROPOSED`; approval exists only on the reviewer endpoint.
* **Can someone review their own investigation?** No: analysts and reviewers are different roles, the four-eyes rule is also enforced inside the transaction, and the reviewer identity comes from the token, never from the request body.
* **What is not finished?** Real-LLM verification; protection of the read-only complaint and hotspot endpoints, rate limiting and real identity (OIDC) before any public deployment; a hosted demo. See [`PHASE_02_RELEASE_REPORT.md`](PHASE_02_RELEASE_REPORT.md).

## Slide outline (if slides are wanted)

1. **Problem:** complaint floods, duplicates, invisible clusters. 2. **Solution:** investigate with audited tools, propose, a human decides. 3. **IBM Db2 architecture:** diagram + the six Db2 features above. 4. **Live flow:** map → investigation → recommendation → review (screenshots 03, 20, 22). 5. **Trust:** provenance labels, evidence grounding, audit log, error states (13, 23). 6. **Status and honesty:** what is verified (149 + 245 + 8 + 63 tests), what is blocked (real LLM), what comes next.
