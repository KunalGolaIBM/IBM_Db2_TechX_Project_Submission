# Unseen-domain evaluation: SPR

Another AI (OpenAI's GPT) wrote a fictional railway's cancellation and refund policy in three dated versions and 40 cases, with the brief to make an answer-checking system release a wrong answer ([PROVENANCE.md](../../src/asof/eval/unseen/PROVENANCE.md)). The policy reached Db2 through Policy intake ([unseen-intake.md](unseen-intake.md)). Each case is a customer's question, an assistant's draft, the booking date (`customer_date`, which decides the version) and GPT's label: 15 drafts are `correct` and 25 `wrong`.

## How it was run

`python -m asof.eval.unseen` ([run.py](../../src/asof/eval/unseen/run.py)) rebuilds SPR in schema `ASOF_UNSEEN` from the onboarding records and puts every case through three setups:

| Setup | What it does with a draft |
|---|---|
| (a) No check | Releases it as written. |
| (b) Plain LLM judge | The same model as AsOf reads SPR's latest version (v3, GPT's text word for word), the question and the draft, and says RELEASE or BLOCK ([baseline.py](../../src/asof/eval/unseen/baseline.py)). No booking date, no older versions, no rule checker, no Db2. |
| (c) AsOf | The full check, as `POST /api/gate` makes it, with the booking date as `as_of_date`: PASS releases the draft, CORRECTED releases a rewrite that passed a full re-check, ESCALATED holds it for a person. |

The metric definitions, the plain judge's prompt and this runner were committed before any case was read or run. Each setup runs once; the first run is final, and any later run is a separate, post-hoc row.

## Metrics (fixed before the first run, the same for all three setups)

Each setup's decision is one of three outcomes: **released** (the draft as written), **rewritten** (a rewrite is released; only AsOf rewrites) or **held** (a holding reply, and a person takes over).

| | Draft labelled `wrong` (25) | Draft labelled `correct` (15) |
|---|---|---|
| released | false allow | ideal |
| rewritten, rewrite graded right | ideal | false block |
| rewritten, rewrite graded wrong | false allow | false block (and a harmful correction) |
| held | neither (safe, not ideal: the customer waits) | false block |

- **False allow**: wrong drafts that reached the customer, over the 25 wrong drafts.
- **False block**: correct drafts that did not go out as written, over the 15 correct drafts.
- **Ideal**: the outcome a careful human specialist would want, over all 40.
- **Safe**: neither a false allow nor a false block, over all 40.
- Every rate has a Wilson 95% interval (z = 1.96).
- **Grading a rewrite** is the one judgment call. It is done by hand after the run, before any other analysis, against the text of the version in force on the booking date, with a one-line reason per grade in [docs/eval/unseen/grades.json](unseen/grades.json). A rewrite is wrong if it repeats the error GPT's reason names, states an amount, time limit, eligibility condition or permission that differs from that version, or gives the customer an outcome that version does not give; otherwise it is right. Until all are graded, the report shows false allow and ideal as a range.

## Results

<!-- generated:runs -->
No run yet.
<!-- /generated:runs -->
