# Five-minute judge walkthrough

Use a dedicated local `ANNATEST` database or another explicitly designated QA database. Do not enter a real donation, address, or beneficiary. Prefix every test food/partner label with `SYNTHETIC QA |`. The seeded accounts are local development-only; use the account emails in the README and the private `DEMO_PASSWORD` set in `.env`. Keep passwords out of shared reports and screenshots, and do not use seeded accounts in a public deployment.

## Before the demo

1. Start Db2, FastAPI and Vite using the commands in the README and [Db2 setup](db2-setup.md).
2. Confirm `/api/health` reports IBM Db2 and vector readiness.
3. Use a dedicated QA database with demo seed accounts and a verified NGO profile. In a fresh seeded database, the NGO demo account owns Nayi Disha Foundation.
4. Prepare a QA batch with valid cold temperature/allergen evidence and future use-by time. For a negative safety example, use a separate QA batch with missing temperature or unconfirmed allergens.

## Live sequence (about five minutes)

| Time | Show | Judge takeaway |
|---|---|---|
| 0:00–0:40 | Overview cards and network activity | Metrics come from the live Db2 aggregate queries, not hard-coded frontend totals. |
| 0:40–1:30 | Open a `SYNTHETIC QA |` food passport. Show temperature, allergens, preparation/use-by, observation history and the deterministic decision. | Missing evidence returns `HOLD`; a passed expiry/ETA returns `INFEASIBLE`; only human review plus complete evidence can become logistics `FEASIBLE`. This is not certification. |
| 1:30–2:10 | Record human review and inspect NGO feasibility, distance, ETA and remaining declared time. | The estimate is transparent and time-bounded; ineligible food cannot be allocated. |
| 2:10–3:00 | Sign in as the NGO, allocate a small synthetic batch to its own verified profile, then show its capacity decrease. | Allocation is role-scoped and capacity is reserved in a Db2 transaction. Larger batches can be partially allocated across multiple eligible partners. |
| 3:00–4:20 | Relay the one-time QA codes out-of-band to the designated actors. Sign in as donor for pickup, assigned volunteer for delivery/handoff, and receiving NGO for distribution; enter the actual QA quantity received at distribution. | Each actor can confirm only their checkpoint; Db2 stores stage timestamps and the actual kg in the immutable audit event. Wrong actor, code, quantity, or sequence is rejected. |
| 4:20–5:00 | Ask the Policy Copilot a relevant question and open the retrieved source link; verify the audit chain as admin. | The answer is composed from retrieved Db2 policy passages with citations; it cannot change a safety decision. The audit chain verifies. |

For a demo on an existing dataset, do not change existing demo partner capacity or records. Use a newly designated QA database and clearly labelled records. The allocator sees each one-time code only once; the operator must relay the correct code to the stage actor without placing it in a screenshot, log or permanent note.
