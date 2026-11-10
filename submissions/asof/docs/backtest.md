# Backtest: what past answers put at stake

A company that already runs an assistant wants to know how often it was wrong before AsOf was in front of it. A backtest takes a CSV of past conversations, runs every row through the normal check for the date that mattered to that customer, records each decision in the hash-chained ledger, and has Db2 summarise the result as an exposure report: how many answers were wrong for their date, which clause versions they contradicted, and the dollar gap where the data has one.

The code is [`asof/backtest.py`](../src/asof/backtest.py); the tables, procedures and views are [`sql/11_backtest.sql`](../src/asof/sql/11_backtest.sql); the page is **Backtest** in the console.

## The file

UTF-8 CSV, a header row, then at most 500 rows (`ASOF_BACKTEST_MAX_ROWS`, which Db2's `CK_BACKTEST_RUN_ROWS` caps at 500 whatever it says) and at most 2 MB.

| Column | Required | What it holds |
|---|---|---|
| `question` | yes | What the customer asked: 1 to 2,000 bytes in UTF-8, no control characters |
| `draft` | yes | What the assistant answered: 1 to 4,000 bytes |
| `customer_date` | yes | The date that decides which policy applies (booking or travel date), `YYYY-MM-DD`, from 2020-01-01 to 2035-12-31 |
| `channel` | yes | Where the conversation happened: `chat`, `email`, `faq` or `api` |
| `doc_id` | no | `AURELIA-CSP`, `FERNHOLLOW-FEES` or `auto`; empty means the run's document |

Nothing runs unless every row is valid. A refused upload (HTTP 422) lists each problem with its data row number, the file line it ends on and the column, up to 50 of them, and the total count: an empty or oversized file, NUL bytes, bytes that are not UTF-8, a missing, unknown or repeated column, too many rows, a row with the wrong number of fields, and each bad cell. Column names are matched case-insensitively, a byte-order mark is dropped, and blank lines are not rows. Quoted cells may hold commas and line breaks. Cell text is only ever data: it goes to Db2 through bound parameters and to the model inside escaped blocks, like any check.

## How a row is checked

1. **The run opens.** `START_BACKTEST` stores the file's name, its SHA-256 and row count, the document for rows without one, the model and a deadline. No CSV text is stored in the backtest tables.
2. **Each row goes through the normal check** ([`checkgraph.py`](../src/asof/checkgraph.py)): extraction, the as-of plus vector retrieval for the row's `customer_date`, the judge with the verbatim-quote rule, the rule check on `RULE_JSON`, a rewrite from the clauses and its re-check when a claim is contradicted. The decision is appended through `APPEND_LEDGER` on channel `backtest`, with `{"run_id", "row", "source_channel"}` in its verdicts, so the link to the CSV row is part of the row hash `VERIFY_CHAIN` recomputes. The question and draft are redacted before they are stored, as for every check. A row on `auto` is routed by Db2's vote first ([routing](db2.md#routing-which-policy-a-draft-is-about)); a close call is held as `ROUTE_UNCERTAIN`, never guessed.
3. **Db2 records the outcome.** `ADD_BACKTEST_ITEM` takes the ledger row's ID and refuses it (75074) unless it is this run's check of this row: channel `backtest`, the same customer date and document, and the run, row and channel in its hashed verdicts. It then derives the outcome from that ledger row itself, so the application cannot report a wrong answer as right:

   | Outcome | When |
   |---|---|
   | `WRONG` | a first-pass claim was `CONTRADICTED` by the clause version in force on the customer's date |
   | `UNCONFIRMED` | nothing contradicted, but the policy in force does not confirm the answer: a claim no clause covers, a detail no claim stated, too many claims, or no clear document |
   | `OK` | every claim supported, or no policy claim at all |
   | `FAILED` | the check failed closed on an error (`ERROR_FAIL_CLOSED`), its decision could not be recorded, or routing failed |
   | `SKIPPED` | not checked: the run's deadline passed, or the before-check hook stopped the run |

4. **Money, for each contradicted claim of a wrong answer,** through `ADD_BACKTEST_COST` (below).

Backtest decisions meet Db2's [release rules](release-rules.md) like any other: a `PASS` or `CORRECTED` row whose released claims do not cite a clause version in force on the customer's date, with the quote in its text, is refused (75080 to 75083), and the gate records the row held instead (`RELEASE_REFUSED`). The outcome still comes from the first pass: an answer that contradicted the policy is `WRONG` even if its rewrite was refused; otherwise a refused release is `UNCONFIRMED`.
5. **The run closes.** `FINISH_BACKTEST` refuses to end a run as `DONE`, `DEADLINE` or `STOPPED` unless every row has an outcome (75078). `FAILED` is the one ending that may leave rows without one: the runner itself could not go on, because Db2 would not record an outcome.

## How the money is computed, and where it is not

For a contradicted claim, the application finds the dollar amounts the claim states (the rule checker's own parser) and the dollar amounts the cited clause version sets (`RULE_JSON` keys ending in `_usd`, limits such as `max_` and `min_` keys left out). When there is exactly one of each and they differ, it passes the key and the stated amount to `ADD_BACKTEST_COST`, which:

- reads the citation (clause, version, business start and the exact row Db2 held) from `CLAIM_CITATION`, never from the caller, and refuses a claim that is not a contradicted first-pass claim of that answer (75076);
- accepts only a plain lower-case key ending in `_usd`, not a limit, and a stated amount from 0 to 1,000,000 (75077), so nothing else can reach the JSON path;
- reads the policy's amount from that exact clause row, current or superseded since, with `JSON_VALUE(RULE_JSON, '$.' || key)`, and refuses a row that has no number there (75077);
- stores stated, policy and the difference (stated minus policy), and which way it cuts. **In the customer's favour:** the answer promised a lower fee or a larger payment than the policy, the kind of promise the company may be held to, as in *Moffatt*. **Against the customer:** it told them to pay more or expect less. A key naming a fee is a charge; any other amount (`compensation_usd`, `delayed_bag_daily_usd`) is a payment to the customer.

Every other contradicted claim gets a `NOT_COMPUTABLE` row with the reason: the claim states no dollar amount (eligibility, a deadline, a procedure, as in the Moffatt question itself), states only a dollar limit, the clause sets no amount, there is more than one amount on either side, or the amount agrees with the clause and the contradiction is about something else (a weight, a permission).

What the number is not: a liability estimate. Each difference is for one occurrence, because the data does not say how many bags, days, trips or items were involved, what the customer paid, or whether they acted on the answer. The Moffatt kind of mistake, a refund the policy did not allow, has no amount in a fare policy's rules at all, so it is counted, not priced. The report says all of this next to the numbers (`cost_method`).

## The report

`GET /api/backtests/{id}`, and the page, read SQL over Db2 ([`backtest.py`](../src/asof/backtest.py), `report`):

- **`run`**: from `V_BACKTEST_RUNS`, the counts per outcome and the state. A run still marked `RUNNING` with no progress for longer than two check deadlines plus a minute reads as `INTERRUPTED` (its process stopped; the rows left were never checked).
- **`by_clause`**: the wrong answers grouped by the clause version they contradicted, with that version's business period, from `V_BACKTEST_CONTRADICTIONS` (citations joined with the exact clause row through `FOR SYSTEM_TIME FROM ... TO ...`).
- **`money`**: priced claims, the total, the split by direction, and **`not_computable`**: how many claims were not priced, by reason.
- **`costliest`**: the five wrong answers with the largest priced difference, with the redacted question and draft, each contradicted claim against its clause version, and, when the check rewrote it (`CORRECTED`), what the policy in force supports. The text is read as the runtime user; the ledger's column masks show it to no one else.
- **`items`**: every row's outcome, reason code and ledger link.

## Kept apart from live numbers

A backtest decision is a finding about an answer a customer already got, not an answer AsOf released. So:

- **Analytics** ([`policy.analytics`](../src/asof/policy.py)) leaves channel `backtest` out of the decision, reason, area, rule-check and override numbers, and reports `backtest_decisions` so the page says how many it left out. Area and rule-check counts come from tables without a channel (`MQT_CLAIM_OUTCOMES`, `CLAIM_CITATION`), so the backtest share is read separately (through `IX_LEDGER_GROUP_CREATED`, which leads with `CHANNEL`) and subtracted.
- **The specialist inbox** (`V_REVIEW_QUEUE`) leaves backtest decisions out: nobody is waiting for those replies. `review.held_entry` and `RESOLVE_ESCALATION` (75070) refuse to answer one.
- **Change impact** (`CHANGE_IMPACT`) leaves them out: the customer got the original answer, not AsOf's decision, so a backtest's `CORRECTED` rewrite was never told to anyone.
- **The ledger page** labels each backtest row; `V_DECISION_STATS`, `V_AUDIT_DECISIONS` and the dbt mart already carry the channel.

## Enforced by Db2

- `CK_LEDGER_CHANNEL` admits `backtest` (01_tables.sql for new ledgers; 11_backtest.sql replaces the check on ledgers made before backtests, and the two lists are tested to match).
- The runtime user `asofapp` holds `EXECUTE` on the four procedures and `SELECT` on the tables and views, and no `INSERT`, `UPDATE` or `DELETE`.
- Triggers make items and costs append-only, and let a run change only while it runs, and then only its progress and its ending (75001, even for the owner).
- Check constraints: the row cap, the outcome, source channel and status enums, a hex SHA-256, a ledger row for every checked outcome and none for a skipped one, consistent amounts (`DIFF_USD = STATED_USD - POLICY_USD`), and one CSV row per ledger decision (a unique index).
- `schema.reset_ledger` (the demo-only `setup --reset-ledger`) drops the backtest tables with the ledger, since their items point at its rows.

## Limits and failure handling

- **Row cap:** 500 rows, in the application and in Db2.
- **Deadline:** `ASOF_BACKTEST_DEADLINE_S` (30 minutes by default). No row starts after it; the rows left are recorded `SKIPPED` and the run ends `DEADLINE`. A row already started may run to its own check deadline (`ASOF_CHECK_DEADLINE_S`).
- **One row at a time, failing closed:** a check that fails is recorded `FAILED` and the run goes on; a decision the ledger refused is `FAILED` with `LEDGER_UNAVAILABLE`.
- **One run at a time per server** (HTTP 409 for a second). The run goes on in a background thread after the upload is answered (HTTP 202); the page polls the report. A server restart mid-run leaves the run `INTERRUPTED`.
- **The spend-cap hook:** `Backtest(before_check=...)`, and `create_app(backtest_guard=...)` in the API, is called before each row's check. It raises `backtest.Stop("reason")` to end the run there: that row and the rest are recorded `SKIPPED` (`RUN_STOPPED`) and the run ends `STOPPED` with the reason as its note. The public demo's daily cap on live checks (`CLAIM_DEMO_CHECK` on `DEMO_SPEND`, [public demo](public-demo.md)) is the cap such a hook would claim against; backtest runs stay disabled on the public demo, so nothing calls it today, and nothing in the backtest meters spend itself.
- **Time:** in replay mode the sample's 20 rows took 34 seconds through the API, against Db2 on a remote VM reached over an SSH tunnel. With a hosted model, add the model's time for each row (a check takes about 6 s; a wrong answer also gets a rewrite and its re-check).
- **Replay mode** checks only inputs it has recordings for: the sample's rows. Any other row fails closed, one at a time, and is recorded `FAILED`. A live provider checks any row.

## The sample

[`fictional-backtest-sample.csv`](../src/asof/data/samples/fictional-backtest-sample.csv): 20 made-up past answers over both fictional policies, in all four channels, with customer dates on both sides of policy changes (the Moffatt question for March and June bookings, around `BRV-002` v2 from 1 May; the first bag fee in July after `BAG-001` v2; the overdraft fee in August after `OVD-001` v2; fee refunds before and after `FRV-001` v2). Every row is an input the shipped replay recording covers: the built-in checks, the inbox's two recorded replies, and one recorded rewrite (the July bag fee answer). So it runs with no key; a test (`tests/test_backtest.py`) holds every row to the recording. No new model outputs were recorded for it.

In replay mode, through Db2, it reaches these numbers (`tests/test_db2_backtest.py` asserts them exactly):

- 7 wrong for their date, 5 not confirmed, 8 right, none failed or skipped;
- 12 contradicted claims; 2 priced, $15.00 in all: the July answer that said the first bag costs $35 when `BAG-001` v2 charged $40 ($5.00 in the customer's favour), and the August answer that said the overdraft fee is $35 when `OVD-001` v2 charged $25 ($10.00 against the customer); the other 10 not computable (8 state no dollar amount, 1 cites a clause that sets none, 1 states the clause's own amount and is wrong about something else);
- wrong answers by version: `BRV-002` v1 2, then `OVD-001` v2, `BAG-001` v2, `CHG-004` v1, `FRV-001` v1 and `PET-001` v1 1 each.

`python -m asof.demo` runs the sample last, so the Backtest page has a report on a fresh install.

## Running one

- **Console:** **Backtest**, then choose a file or **Run the sample**.
- **API:** `curl -X POST -H 'Content-Type: text/csv' --data-binary @answers.csv 'http://127.0.0.1:8000/api/backtests?doc_id=auto&name=answers.csv'` answers 202 with `run_id`; then `GET /api/backtests/{run_id}`. `GET /api/backtests` lists runs; `GET /api/backtests/sample` downloads the sample. With `ASOF_AUTH=users`, starting a run needs the `checker` role and reading reports the `auditor` role.
- **Command line:** `python -m asof.backtest run answers.csv`, `python -m asof.backtest sample`, `python -m asof.backtest report 3`.

## In the public demo

With `ASOF_PUBLIC_DEMO=true`, uploads and runs are refused (HTTP 403, "Disabled in the public demo: uploading and running a backtest ..."). The page shows the sample's run, which the demo seeding (`python -m asof.demo`) made, read-only, and the sample stays downloadable.

## Not done

- A backtest finds wrong past answers but does not draft correction notices for them; the change-impact agent's notices cover answers AsOf released.
- The live path (a hosted model checking rows the recording does not cover) is exercised here through the same check graph as every live check and through scripted-model tests of the runner, not by a recorded run with a hosted key in this lane.
