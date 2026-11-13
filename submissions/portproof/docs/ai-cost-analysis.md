# What the AI in PortProof costs, and why that cost does not grow with the database

The question this answers was put to every team: running a model against a very
large database is cost ineffective, so what is the plan.

The short answer is that PortProof never runs a model against the database. The
model reads SQL text, a schema, and a handful of synthetic rows. The size of the
source tables is not an input to any prompt, and the experiment in section 3
shows the prompts are byte for byte identical when the source goes from a
thousand rows to a million.

Every number here was measured on Db2 Community Edition 12.1.5.0 with
`gemini-flash-latest` as the model, and is read back from `PORTPROOF.LLM_CALL`,
a ledger in Db2 that the application can write only through a stored procedure.
Reproduce the totals with `python -m src.main --cost`.

## 1. What the model is sent

There are three places a model can be called. Each is the last tier of a
ladder, reached only when the free tiers above it produced nothing.

| Stage | Reached only when | What the prompt contains | What it never contains |
|---|---|---|---|
| Compile repair | Db2 rejected the statement, the fix memory has no verified repair of it, and the fifteen rules did not fix it | The failing SQL, Db2's SQLCODE and message, up to three similar past repairs | Any row of any table |
| Meaning repair | Both engines ran the statement and returned different rows, and neither a remembered rewrite nor a measured rule closed it | The source SQL, the Db2 SQL, one sentence on what the disagreeing dataset provokes, at most five rows from each side of the counterexample | Source data. The rows are PortProof's own synthetic dataset. The one dataset shaped by real source statistics is withheld |
| Dataset | A proof is still vacuous or weak after the generated and query aware datasets, and no model dataset is cached for the schema | The schema of the tables the query touches, the query | Any row of any table |

So a prompt is made of three things: a statement, a schema, and a constant
number of synthetic rows. Its size depends on how long the statement is and how
wide the schema is. Nothing in it is proportional to how many rows the source
holds.

## 2. What a call costs

From the cold run in section 4, as the provider counted the tokens:

| Stage | Calls | Tokens in | Tokens out | Mean in per call | Mean out per call |
|---|---|---|---|---|---|
| Compile repair | 1 | 578 | 37 | 578 | 37 |
| Dataset | 4 | 1,452 | 1,600 | 363 | 400 |
| Meaning repair | 75 | 25,573 | 143,228 | 341 | 1,910 |
| **All** | **80** | **27,603** | **144,865** | **345** | **1,811** |

A prompt is a few hundred tokens. Output is larger than input because the
provider bills the model's reasoning as output, which is the honest number to
report and the reason `LLM_REASONING_EFFORT=low` and a 3,000 token ceiling are
set by default.

## 3. The experiment: same queries, larger database

`python -m src.cost_scaling --engine postgres` holds everything fixed except the
number of rows in the source tables. Same schema, same three queries, the model
tiers live, and no dataset cache, fix memory or dead end memory, so nothing is
answered for free the second time. For each size it records the model calls,
the tokens, and a SHA-256 over every prompt that was sent.

| Rows in the source tables | Source profile (SQL, no model) | Model calls | Tokens in | Largest prompt | SHA-256 of all prompts sent |
|---|---|---|---|---|---|
| 2,000 | 16 ms | 4 | 1,365 | 352 tokens | `3de1f49b3fdc` |
| 200,000 | 375 ms | 4 | 1,365 | 352 tokens | `3de1f49b3fdc` |
| 2,000,000 | 3,219 ms | 4 | 1,365 | 352 tokens | `3de1f49b3fdc` |

Measured on PostgreSQL 17. The source grew a thousandfold. The model was called
the same number of times, with the same number of input tokens, and the hash
shows it was sent exactly the same bytes. Output tokens were 3,154, 1,906 and
3,999: they vary from call to call because the model does, in no order related
to size, and each call is capped at 3,000.

The only step that reads the source's data is the profile: one aggregate query
per table (`COUNT`, `MIN`, `MAX`, null counts), executed by the source engine.
It is SQL, it costs no tokens, and it is the only column in that table that
grows. The proof itself runs on PortProof's synthetic datasets of at most a few
dozen rows, so its time does not grow with the source either.

## 4. What does drive the cost, and what brings it down

The cost follows the number of distinct statements that the free tiers cannot
settle, not the data. Four consecutive runs of the full workload (125
statements, four source engines), each starting from what the previous one left
in Db2:

| Run | Model calls | Tokens in | Tokens out | Calls avoided as known dead ends | Compile repairs: memory / rules / model | Meaning repairs: memory / rules / model | Wall time |
|---|---|---|---|---|---|---|---|
| 1, nothing remembered | 80 | 27,603 | 144,865 | 0 | 0 / 16 / 1 | 0 / 13 / 37 | 1,365 s |
| 2 | 32 | 11,368 | 69,026 | 0 | 13 / 4 / 0 | 45 / 1 / 5 | 682 s |
| 3 | 24 | 8,143 | 44,959 | 0 | 14 / 3 / 0 | 49 / 1 / 0 | 485 s |
| 4 | 2 | 833 | 5,903 | 11 | 14 / 3 / 0 | 49 / 1 / 0 | 146 s |

The verdicts did not get worse as the calls fell: 106 statements proven
equivalent on run 1, 111 on runs 2, 3 and 4. Runs 2 and 3 were still paying the
model to retry statements it had already failed on. Run 3 is the first run made
with the dead end memory, so it recorded them, and run 4 skipped them. The two
calls left on run 4 are one statement that had not been recorded as a dead
end: a question is recorded only when every attempt came back with SQL, so one
cut short by a timeout stays open. From first run to
fourth the model's bill fell by 96 percent and the wall time by 89 percent, on
the same workload with the same answers.

Three stores in Db2 do that:

| Store | What it remembers | Effect on the next run |
|---|---|---|
| `FIX_MEMORY` | Every repair Db2 accepted and the proof confirmed, including the ones a model proposed | The same statement is repaired from memory. It is proved again, but nobody is asked |
| `DATASET` | Every dataset both engines loaded, including the ones a model wrote, keyed by schema fingerprint | A weak proof on that schema reuses the model's dataset. The cold run answered 17 of 21 escalations this way within the same run, and the warm run answered 21 of 21 |
| `MODEL_DEAD_END` | Every question the model was asked in full and failed | The model is not paid to fail again. A timeout or an exhausted budget is not recorded, because it proves nothing |

A model's answer is therefore bought once. A repair the model found on Monday is
a Db2 lookup on Tuesday.

## 5. The bound

For a workload of `S` statements, of which `c` fail to compile after memory and
rules, `d` return wrong rows after memory and rules, and `w` have a proof too
weak after the free datasets:

```
model calls  <=  min( LLM_CALL_BUDGET,  c * MAX_REPAIR_ATTEMPTS  +  d * 2  +  w )
tokens out   <=  model calls * LLM_MAX_OUTPUT_TOKENS
```

Every term counts statements. None counts rows, tables' sizes or bytes. On the
cold run that was 1 + 75 + 4 = 80 calls for 125 statements, or 0.64 calls and
about 1,380 tokens a statement, on a workload written to be hard.

The controls, all enforced in the one function every model call passes through
(`HttpRepairLLM.ask`):

| Control | Default | What it stops |
|---|---|---|
| `LLM_CALL_BUDGET` | 200 calls a run | A run that would otherwise keep paying. Past it the model tiers stop answering and statements fall back to the rules and to review |
| `LLM_MAX_OUTPUT_TOKENS` | 3,000 | One runaway answer, reasoning included |
| `LLM_REASONING_EFFORT` | low | The largest single share of the bill |
| Attempts | 3 compile, 2 meaning, 1 dataset | A model arguing with the database |
| Timeout | 45 s | A hung call holding a run |

## 6. In money

Prices change, so the ledger stores tokens and the arithmetic is left visible.
At an illustrative 0.30 dollars per million input tokens and 2.50 per million
output tokens (substitute your provider's rates):

| | Tokens in | Tokens out | Cost |
|---|---|---|---|
| Cold run, 125 statements | 27,603 | 144,865 | about 0.37 dollars |
| Per statement, cold | 221 | 1,159 | about 0.003 dollars |
| 10,000 statements at the same rate, cold | 2.2 million | 11.6 million | about 30 dollars |

The last row is the same whether those 10,000 statements run against one
gigabyte or ten terabytes, and it is paid once.

## 7. What this does not claim

- The first run is not free, and it scales with the number of statements. A
  workload ten times larger costs about ten times more the first time.
- Memory is exact. A statement that differs by one literal from a repaired one
  is a new question and pays again. Most of the model's accepted rewrites in the
  cold run were one pattern, Db2's `=` ignoring trailing blanks where the source
  engine's does not, rediscovered per statement. Promoting a recurring model
  rewrite into a rule would make the pattern free and is not done yet.
- The model is not deterministic. Between the first two runs it repaired a few
  statements it had failed before. The dead end memory trades that chance away
  for a predictable bill, and `LLM_RETRY_DEAD_ENDS=1` takes it back.
- A rewrite the model proposed is accepted because every dataset agrees, which
  is a strong test and not a derivation. It is labelled as a model rewrite.
- The profile does read the source tables, once per table, as SQL on the source.
  On a very large table that is a scan the source's administrator should know
  about.
