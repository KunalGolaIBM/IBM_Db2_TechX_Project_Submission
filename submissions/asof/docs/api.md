# API walkthrough

The API is JSON over HTTP on http://127.0.0.1:8000, the same server as the web UI. Every route is listed in the [README](../README.md#the-api); FastAPI also serves an interactive schema at `/docs` and the OpenAPI document at `/openapi.json`. Without `ASOF_AUTH=users` the API answers on localhost only; with it, every `/api/` call needs a personal token with the route's role ([per-user API access](../README.md#per-user-api-access)).

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
