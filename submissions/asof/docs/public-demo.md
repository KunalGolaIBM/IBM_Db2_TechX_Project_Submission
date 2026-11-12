# The public demo, and live checks on it

The public demo is AsOf on one VM behind its own Caddy, with `ASOF_PUBLIC_DEMO=true` ([api.py](../src/asof/api.py)). It refuses everything that changes policy or sends something, rate-limits every request per address, and runs in replay mode: the built-in scenarios replay recorded model outputs while Db2 runs live. With `ASOF_DEMO_LIVE=true` as well, what a visitor types is checked by a real model too, inside limits that Db2 and the app enforce ([demolive.py](../src/asof/demolive.py)). Every write stays disabled either way.

## Routing

Each request to `POST /api/gate` (the Playground's "Check my own draft") and `POST /api/assistant/ask` (the Playground's demo assistant and the customer chat) goes one of three ways:

| Input | What happens | Cost |
|---|---|---|
| Exactly a recorded built-in scenario: the same document, question, date and draft (or the same question and date, for the demo assistant), character for character | Replay, from `src/asof/data/replay.json` | Nothing; instant |
| Anything else, and a live check can start | A live check by OpenRouter, the full check graph, recorded in the ledger like any other decision (`MODEL_INFO` names the live model) | About four to eight model calls |
| Anything else, and a live check cannot start | Refused with the reason (below). Nothing is checked, recorded or sent | Nothing |

The recorded inputs are read from the recording's own list of checks (`scenarios.checks`), so the routing and the replay keys agree; a test checks that every one of them routes to replay. The specialist inbox's reply check, Ask the ledger and policy intake stay replay-only, and for `doc_id: "auto"` Db2's vote decides clear cases while a close call on new input is looked at again by the routing agent on the live model (the measured one), inside the same capped, metered live check, so it counts toward the day's cap and the visitor's limits.

## The layers, in the order a live check meets them

1. **Explicit opt-in.** `ASOF_DEMO_LIVE=true` is refused without `ASOF_PUBLIC_DEMO=true`, and the demo still requires `LLM_PROVIDER=replay`. The only model key it accepts is `OPENROUTER_API_KEY`, and only from the process environment: a key that came from `.env` is refused at startup ([config.py](../src/asof/config.py)). Every other demo restriction is unchanged.
2. **Input limits.** Pydantic (`LiveGateIn`, `LiveAskIn`) refuses a question over 500 characters or a draft over 1,500 with a 422, before anything else runs. Every recorded input fits, so the built-in scenarios are never refused for length.
3. **Pauses.** After 3 live checks in a row in which the provider failed (an error, a timeout or output that does not fit the schema), live checks pause for 5 minutes. Once Db2 has said today's cap is spent, the app stops asking it until 00:00 UTC.
4. **Per-visitor limits.** `ASOF_DEMO_LIVE_PER_MINUTE` (sliding, default 3) and `ASOF_DEMO_LIVE_PER_DAY` (per UTC day, default 20), separate from the existing read and POST limiters. They are keyed on the address the demo already derives, the last `X-Forwarded-For` entry, which Caddy sets; an IPv6 address counts by its /64. A slot a later layer refuses is given back, so a visitor's count is what was admitted.
5. **Concurrency.** At most 3 live checks run at once; a fourth is refused as busy.
6. **Db2's daily cap.** `ASOF.CLAIM_DEMO_CHECK` ([10_demo_spend.sql](../src/asof/sql/10_demo_spend.sql)) admits the check or `SIGNAL`s SQLSTATE `75097`, and the app never starts a check it refused. The cap is `ASOF_DEMO_LIVE_DAILY_CAP` (default 400), for the whole demo.

Then the check runs with a 120-second budget and no local fallback model. Afterwards `ASOF.RECORD_DEMO_SPEND` adds its model calls and the tokens the provider reported to the day's row.

## How Db2 enforces the cap

`ASOF.DEMO_SPEND` holds one row per UTC day: checks admitted, the cap in force at the latest admission, model calls, input and output tokens. `CLAIM_DEMO_CHECK` takes the day from Db2's own clock (`DATE(CURRENT TIMESTAMP - CURRENT TIMEZONE)`), never from the caller, creates the row if it is missing (a second first caller's duplicate insert is ignored), then updates the row before reading its count. That update takes the row's exclusive lock, so concurrent callers queue on it and each reads the count the previous one committed. Twelve sessions racing with five checks left admit exactly five (tested), and a session that finds the row locked waits for the first to commit, then sees its claim (tested). `CK_DEMO_SPEND_UNDER_CAP` (`CHECKS_USED <= DAILY_CAP`) holds every day to its cap, even for the owner. The runtime user holds `SELECT` on the table and `EXECUTE` on the two procedures; nobody holds `INSERT`, `UPDATE` or `DELETE` (tested against `SYSCAT.TABAUTH` and `SYSCAT.ROUTINEAUTH`). A restart of the app resets the per-visitor counts, not the cap.

## Failing closed

Two cases, and neither releases a draft unchecked:

- **A live check that cannot start is refused** (HTTP 429 for a visitor's limit, 503 otherwise) with `error` in plain words, `reason` (`cap`, `visitor_minute`, `visitor_day`, `provider`, `busy`, `spend_counter` or `unavailable`), `live_checks: "paused"` and a `Retry-After` header. Refusing was chosen over holding because a hold writes an `ESCALATED` row to the ledger and the specialist inbox: once the cap is spent, every request would add one, so anyone could flood the inbox, and each would promise the customer a specialist who is not coming. A refusal records nothing, costs nothing, and says why.
- **A live check that fails after it started is held**, as every failed check is: decision `ESCALATED`, reason `ERROR_FAIL_CLOSED`, the holding reply instead of the draft, and a ledger row. By then Db2 has admitted the check and the model has been called, so the ledger records it.

The built-in scenarios keep replaying throughout. `/healthz` reports `live_checks` (`on`, `paused` or `unavailable`) and `live_model`, and its `public_demo_notice`, the banner app.js and chat.js show, says in plain words whether live checks run, today's count, or that they are paused and why. The Playground refreshes the banner after each check.

## The key

The key is read from the environment only, kept as a `SecretStr`, and never logged or returned: `/healthz` says live or replay and names the model, nothing about the key (tested, with the log captured). It never reaches Db2 either: in the public demo `EMBEDDING_API_KEY` is refused, and the live key is not used as the fallback for in-database embeddings, so setup never puts it into `CREATE EXTERNAL MODEL`.

## Cost, measured

One live check of a new draft (the Moffatt question for a March booking, worded differently from the built-in one) ran end to end on 10 Nov 2026 with `google/gemini-3.1-flash-lite`: `CORRECTED` in 11.1 s, 8 model calls, 8,060 input and 794 output tokens. At OpenRouter's listed prices that day ($0.25 per million input tokens, $1.50 per million output) that is $0.0032, and the key's usage went up by $0.0032. At that rate the default cap of 400 checks a day bounds the demo at about $1.30 a day; a question to the demo assistant adds one call, for its draft. A spending limit on the OpenRouter key itself is the backstop outside AsOf.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `ASOF_DEMO_LIVE` | `false` | Turns live checks on; needs `ASOF_PUBLIC_DEMO=true`, `LLM_PROVIDER=replay` and `OPENROUTER_API_KEY` in the environment |
| `ASOF_DEMO_LIVE_DAILY_CAP` | `400` | Live checks a UTC day for the whole demo, held by Db2 (1 to 100,000) |
| `ASOF_DEMO_LIVE_PER_MINUTE` | `3` | Live checks a minute per visitor (1 to 60) |
| `ASOF_DEMO_LIVE_PER_DAY` | `20` | Live checks a UTC day per visitor (1 to 1,000) |
| `OPENROUTER_MODEL` | `google/gemini-3.1-flash-lite` | The live model |

Without a key in the environment the demo runs as before, in replay mode, and `/healthz` reports live checks `unavailable`.
