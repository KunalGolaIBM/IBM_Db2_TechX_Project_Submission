# Guardrail fuzz: Db2 against an independent oracle

**10,000 / 10,000 decisions agree** · seed 7 · 14.7 s · run 2026-11-10 05:08 UTC · no LLM · one transaction, rolled back.

Random agent proposals (valid ones, near-misses on every boundary: rate exactly at the floor and ceiling and one paisa outside, today, today+90 and today+91, end before start, unknown room types and rooms, over-long fields, opted-out guests, inactive reservations, bad priorities, malformed JSON, unknown action types and exact repeats) are sent to `SP_PROPOSE_ACTION` with the **agent's own Db2 credentials**. Each Db2 decision (PENDING, REJECTED or DUPLICATE) is compared with a Python oracle written from the business rules, not from the SQL.

| Outcome | Count |
|---|---|
| Rejected by Db2 | 7,035 |
| Accepted (queued for a human) | 1,665 |
| Duplicate detected | 1,300 |

| Category | Proposals |
|---|---|
| rate change | 4,944 |
| maintenance | 1,900 |
| room upgrade | 1,767 |
| malformed JSON | 493 |
| repeat | 490 |
| unknown type | 406 |

**What it found:** the first run crashed the procedure with `SQL0137N` on an over-long field (`"to_room_type_code": "PENTHOUSE"`). Db2 failed closed (nothing was created), but the agent got a raw error instead of a clean `REJECTED`. The procedure now reads fields into wide variables and validates them; `test_guardrail_rejects_over_long_fields_cleanly` keeps it fixed.

Reproduce with `python src/fuzz_guardrails.py` (or `python src/verify.py`, which runs 1,000).
