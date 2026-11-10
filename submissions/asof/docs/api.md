# API walkthrough

The API is JSON over HTTP on http://127.0.0.1:8000, the same server as the web UI. Every route is listed [below](#the-api); FastAPI also serves an interactive schema at `/docs` and the OpenAPI document at `/openapi.json`. Without `ASOF_AUTH=users` the API answers on localhost only; with it, every `/api/` call needs a personal token with the route's role ([per-user API access](setup.md#per-user-api-access)).

## Running it

```bash
python -m asof.db2check      # verify the Db2 features AsOf needs (owner account)
python -m asof.setup         # schema, users, seed data, grants, self-check
python src/main.py           # web UI at http://127.0.0.1:8000, API docs at /docs (same as python -m asof.api)
python -m asof.demo          # optional: thirteen sample decisions (seven airline, three bank, three held for the inbox), then the 20-row backtest sample, so every screen has history
```

- **The customer's side:** http://127.0.0.1:8000/chat is a fictional airline's help page with a chat widget. Pick a booking (its date is what the booking system sends as the as-of date) and ask. Each reply shows whether AsOf released the draft as written, corrected it from the clause (with the clause versions as sources), or passed it to a specialist; **Behind the scenes** shows the assistant's draft, the claim verdicts and the ledger receipt. Every suggested question replays without a key; the five bookings cover all three outcomes.
- **Policy intake:** in the console, **Policy intake**, then **Use the sample**: a fictional Aurelia Air revision that raises the first bag fee from 1 February 2027, adds a sports equipment clause, extends travel credits from 1 March 2027 and restates one clause unchanged. Preview its impact, approve it, and see the new versions on the timeline.
- **Agents:** [mcp_server/README.md](../mcp_server/README.md) runs AsOf as an MCP server for any agent that speaks the Model Context Protocol.

### The API

Every route, below, is JSON over HTTP; [docs/api.md](api.md) walks through the Moffatt scenario with `curl` (the March and June bookings, with the decisions a real run returned) and shows how to reset the demo ledger. FastAPI serves the interactive schema at `/docs`.

**API**

| Endpoint | Purpose |
|---|---|
| `POST /api/gate` | Check a draft: `question`, `draft_answer`, `as_of_date`, optional `doc_id` (`AURELIA-CSP`, the default, `FERNHOLLOW-FEES`, or `auto` to [route](db2.md#routing-which-policy-a-draft-is-about) it) and `channel`. Returns the decision, final answer, and per-claim verdicts with clause versions and quotes; with `auto`, also the route. |
| `POST /api/assistant/ask` | The demo console's endpoint: ask the naive demo assistant, then check its draft. Returns the raw draft too (`assistant.draft`); not for integrations (below) |
| `GET /api/ledger`, `GET /api/ledger/{id}` | Recorded decisions and their claim citations |
| `GET /api/ledger/{id}/replay` | The clause rows a decision used, what Db2 held at that moment, and what applies today |
| `POST /api/ledger/ask` | "Ask the ledger": a plain-English question about the audit trail, answered as the read-only analyst `asofread`. Returns the answer, the checked SQL that ran and the rows. Optional `scope` (a key from the route below) runs it as that domain's analyst instead, and `scope_applied` lists the policy documents Db2's row permissions let that user see ([row permissions](row-permissions.md)). |
| `POST /api/ledger/attack` | An attack chip on the Ask page: `attack` is `delete`, `messages`, `tables`, `update` or `heavy`. Sends that fixed SQL (what a manipulated model might write; no model is called) through the SQL check and Db2 as the analyst, and returns `stopped_by` (SQL check, Db2 column masks or Db2 workload threshold) and each layer's outcome in `layers`, including what Db2's privileges say to the refused writes. |
| `GET /api/ledger/attacks` | The attack chips: key, label and SQL. |
| `GET /api/ledger/ask/scopes` | The scopes Ask the ledger can run in: `all`, then one per policy domain with its own analyst user. |
| `GET /api/ledger/{id}/evidence` | An evidence pack for a dispute, as a JSON download: the decision with redacted question and draft, the released answer, every claim with its verdict and clause version, the replay of each clause, the chain check and the receipt hash (the **Evidence pack** button on a ledger entry) |
| `POST /api/ledger/receipt` | Check a receipt: `ledger_id` and the `row_hash` that the check's response carried. Answers `INTACT`, `MISMATCH` (the row with that ID is not the one issued: rewritten, as after an owner rebuilt the ledger consistently, which `VERIFY_CHAIN` alone cannot see, or reset, or the receipt is from another ledger), `MISSING` or `CHAIN_BROKEN` |
| `GET /api/chain/verify` | Run `VERIFY_CHAIN` over the whole ledger |
| `GET /api/whoami` | Which auth mode the server runs and, with `ASOF_AUTH=users`, the caller's user name and roles |
| `GET /api/chain/anchors` | Check every chain-head anchor kept outside Db2 against the ledger now: `OK` (with the last entry covered and any unanchored rows), `MISMATCH` or `MISSING_ROW` (the ledger was rebuilt or cut up to that anchor, even if `VERIFY_CHAIN` passes), `LOG_TAMPERED`, `CHAIN_BROKEN`, `NO_ANCHORS` or `OFF`. Also `python -m asof.anchor verify` |
| `POST /api/policy/change` | Apply a new clause version through `APPLY_POLICY_CHANGE` as the editor user. Accepted only from localhost, unless `ASOF_EDITOR_TOKEN` is set, in which case the `X-AsOf-Editor-Token` header must match. |
| `POST /api/policy/preview` | The same change as a preview: `APPLY_POLICY_CHANGE` and `CHANGE_IMPACT` run in one transaction that is then rolled back, so the response shows what would split, be flagged and go stale, and nothing is saved (editor action: localhost or token) |
| `GET /api/impact/{clause_id}` | `CHANGE_IMPACT`: stale and historically valid answers, help-centre answers to review |
| `POST /api/impact/{clause_id}/suggestions` | Run the change-impact agent: draft a correction for each help-centre answer that needs review, run the full check on it for the date it must hold from, store it as pending (editor action: localhost or token) |
| `GET /api/suggestions`, `POST /api/suggestions/{id}/decision` | List drafted corrections; approve (publish) or reject one as `asofedit` (`DECIDE_SUGGESTION`) |
| `GET /api/policy/timeline`, `GET /api/policy/clauses/{id}/history` | Business-time versions with rule parameters (optionally for one `doc_id`); every system-time row for a clause |
| `GET /api/policy/clauses/{id}/diff?a=&b=` | Two rows Db2 has held for a clause, current or in the history table, compared: the text word by word, `RULE_JSON` key by key, and the embedding distance between them |
| `POST /api/policy/drafts`, `GET /api/policy/drafts`, `GET /api/policy/drafts/{id}`, `GET /api/policy/drafts/{id}/source`, `POST /api/policy/drafts/{id}/decision`, `GET /api/policy/intake/sample` | [Policy intake](db2.md#policy-intake-a-pdf-into-the-bitemporal-table): upload a PDF as the editor, read the checked proposals and the stored file, approve, reject or preview; the built-in sample revision |
| `GET /api/reviews`, `GET /api/reviews/{id}`, `POST /api/reviews/{id}/check`, `POST /api/reviews/{id}/resolve` | [The specialist inbox](db2.md#the-specialist-inbox-and-correction-notices) (`reviewer` role): the queue, a held decision with its claims and the policy in force, a reply checked with nothing recorded, and a reply sent through `RESOLVE_ESCALATION` |
| `GET /api/notices`, `POST /api/notices/draft`, `POST /api/notices/{id}/decision` | Correction notices (`reviewer` role): list them, have the change-impact agent draft a checked notice for each answer a policy change made stale (`ADD_NOTICE`), approve or reject one (`DECIDE_NOTICE`) |
| `POST /api/backtests`, `GET /api/backtests`, `GET /api/backtests/{id}`, `GET /api/backtests/sample` | [Backtest](backtest.md) (`checker` role to start, `auditor` to read): the body is a CSV of past answers (`Content-Type: text/csv`, `question,draft,customer_date,channel[,doc_id]`, at most 500 rows and 2 MB), checked row by row in the background on ledger channel `backtest` (202 with the run ID); the runs; a run's exposure report; the fictional sample CSV |
| `GET /api/analytics` | Decision, area and override statistics from the Db2 views (backtest decisions left out and counted on their own) |
| `GET /healthz` | Db2 connectivity and the configured model; on the public demo, whether live checks run (`live_checks`: `on`, `paused` or `unavailable`), the live model and the banner text (`public_demo_notice`) |

**Integrations call `/api/gate`, not `/api/assistant/ask`.** `/api/assistant/ask` is the demo console's endpoint: it deliberately returns the demo assistant's raw draft (`assistant.draft`) next to the decision, so the Playground and the customer chat's Behind-the-scenes view can show that draft struck through. An integration sends its own draft to `/api/gate` and gets back the decision, `released`, `final_answer` and the per-claim verdicts (with ids, timing and the ledger receipt), never a copy of the draft. Show the customer `final_answer` and nothing else: the claim texts and `rewrite` are for audit, and `rewrite` can hold a rewrite that failed its re-check. `released` is false (HTTP 503) only when nothing checked can go out, because the router could not tell which policy applies or the ledger could not record the decision; `final_answer` is then only the generic holding reply, so show that or nothing.

**On the public demo with live checks** ([details](public-demo.md)), a recorded built-in scenario replays and anything else is a live check. One that cannot start (today's cap, a visitor's limit, a pause after provider failures) is refused before anything runs: HTTP 429 or 503 with `error` in plain words, `reason`, `live_checks: "paused"` and `Retry-After`, and no decision, because nothing was checked or recorded. A live check that fails after it started is held like any other: a 503 that carries the decision.

**Drop it into an existing LangChain app**

```python
from langchain_core.runnables import RunnablePassthrough
from asof import as_runnable

chain = RunnablePassthrough.assign(draft=assistant_prompt | llm | StrOutputParser()) | as_runnable()
answer = chain.invoke({"question": "Can I get a bereavement fare after I travel?", "as_of": booking_date})
```

One chain serves every customer: the assistant's draft joins the input, and the question and the customer's date travel with each call (the check tests the draft's premises against the question). A call with no date is refused, never guessed. The runnable returns the checked answer, and every decision lands in the Db2 ledger.

## The Moffatt scenario through the API

Ask the naive demo assistant (which answers from a stale FAQ) and let AsOf check its draft, once for a March booking and once for a June booking:

```bash
curl -s -X POST localhost:8000/api/assistant/ask -H 'content-type: application/json' \
  -d '{"question": "My grandmother just died. Can I get the bereavement fare after I travel?", "as_of_date": "2026-03-10"}'
```

A real run with `gemini-3.1-flash-lite` (abridged):

| | March booking (`2026-03-10`) | June booking (`2026-06-02`) |
|---|---|---|
| Assistant draft | "You can request a bereavement discount retroactively ... within 90 days of your ticket issuance." | same promise |
| Retroactive claim | CONTRADICTED by **BRV-002 v1** (judge and rule check agree) | SUPPORTED by **BRV-002 v2** |
| Decision | **CORRECTED**: "Bereavement fares must be requested before travel begins. A bereavement fare cannot be applied retroactively once any part of the journey has been flown, and no refund of the fare difference is available after travel. Policy references: BRV-002 v1 (in effect from 2026-01-01)." | **PASS** with **BRV-002 v2** references when the draft is accurate, **CORRECTED** when it overstates the refund |
| Naive-bot draft, 5 consecutive live runs (2 for March, 3 for June) | CORRECTED 2 of 2 | PASS 2 of 3, CORRECTED 1 of 3 |

Other stale FAQ entries are caught the same way: a July question about the first bag fee is corrected from $35 to $40 (BAG-001 v2), and "you can transfer your ticket for a $50 name change fee" is corrected from CHG-004.

## Resetting the ledger for a demo

**Demo only.** The ledger is append-only by design: no user, not even the owner, can update or delete its rows. To start a recording from ledger entry 1, setup can drop and recreate the ledger tables as the owner (and the change-impact agent's drafted corrections, which cite ledger rows), which deletes every recorded decision and starts a new hash chain. Policy clauses, their history and the help-centre answers are kept. Never do this outside a demo.

```bash
python -m asof.setup --reset-ledger      # asks you to type "reset"; add --yes to skip
```

`python -m asof.setup --reset` goes further and rebuilds the whole schema from the seed data, including undoing policy changes made in the demo.
