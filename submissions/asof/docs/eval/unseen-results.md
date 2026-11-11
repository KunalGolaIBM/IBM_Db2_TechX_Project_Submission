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

## What the first run shows

Run on 10 Nov 2026 at commit `d77d9ee`, OpenRouter `google/gemini-3.1-flash-lite` for both the plain judge and AsOf, 40 cases in 77 s, every grade below by hand against the governing version's text.

- **AsOf against the plain judge.** Both released 2 of 25 wrong drafts (8.0%, Wilson 2.2% to 25.0%), so on this set AsOf is not measurably safer than one LLM call with the current policy. The difference is in what happens to everything else: the plain judge held 9 of 15 correct drafts (60.0%) and corrected nothing, so it reached the ideal outcome in 6 of 40 cases (15.0%); AsOf held 2 of 15 correct drafts (13.3%), released 17 corrected answers that were all graded right, and reached the ideal outcome in 30 of 40 (75.0%, 59.8% to 85.8%).
- **Why the plain judge blocks so much.** It judges every booking by v3. It released 5 of the 6 correct v3 drafts but only 1 of the 9 correct v1 and v2 drafts, and many of its blocks of wrong drafts cite v3 figures for an older booking (R07: "INR 40" for a v1 ticket whose charge is INR 30; R26: "14 days" for a v1 claim window of 7). Its two releases of wrong drafts are both version errors: R22 applies v3's partial-cancellation rule to a v1 booking, and R37 applies v3's "no special medical exclusion for resale-broker tickets" to a v2 booking, where E3 excludes them.
- **AsOf cited only the booking date's version.** No claim in any case was checked against a clause row from another SPR version than the booking date's, including the 37 of 40 bookings made on the last or first day of a version (2026-04-30, 2026-05-01, 2026-08-31, 2026-09-01). Errors: 0. Latency p50 6.4 s, p90 8.3 s.

### Where AsOf failed

- **R05 and R10, released wrong (the two false allows).** Both turn on which row of the fare table a cancellation time falls in, with the time just at a boundary. R05 (v2, 1A cancelled 2 h 59 min before departure) is under 3 h, so no refund; the draft's "50% charge" was judged SUPPORTED, and the rule check agreed, since 50% is one of the table's values. R10 (v2, 2A cancelled exactly 3 h before) is inside the 3 to 10 h band ("at least" includes the threshold, P-02); the draft's "no refund" was judged SUPPORTED.
- **R06, a correct draft held.** The same boundary in the other direction: a v3 1A ticket cancelled exactly 2 h before departure is in the 60% band, and the judge marked the right answer CONTRADICTED; the rewrite then failed its re-check and the answer was held.
- **R36, a correct draft held.** A v3 PQ medical claim: base fare INR 3,000 less the INR 200 PQ deduction is INR 2,800, and the fee is kept. The judge marked both amounts CONTRADICTED, and its rewrite was not covered on re-check.
- **Six wrong drafts held instead of corrected** (R07, R12, R14, R22, R26, R38). In four of them (R14, R22, R26, R38) the right answer is "you do not qualify" (a non-refundable PQ ticket, a PNR too small for partial cancellation, a late E1 claim, a duplicate flagged after 15 minutes). The rewrite stated the rule correctly, and on re-check the judge marked that rule CONTRADICTED next to the customer's own situation, so the correction was held. In R07 the rewrite gave the INR 30 charge as the 4 to 12 h band's (in v1 it is the 12 to 48 h band's); in R12 the extracted claims dropped "Premium QuickBook", so no clause covered them.

### Systematic weaknesses (described, not fixed)

1. **Band boundaries are left to the judge.** Which fare-table row a time like "2 h 59 min" or "exactly 3 hours" falls in decides four of the misses: both false allows (R05, R10), one held correct draft (R06) and one held correction (R07). The rule checker has no tiered parameters for SPR (its `applies_when` handles only delay hours), and it reads no rupee amounts, so a wrong amount from another row, or a percentage that exists elsewhere in the table, passes it.
2. **A rewrite that says "you do not qualify" tends to fail its re-check.** The judge reads a correctly stated rule, next to a customer who fails it, as a contradiction. The draft is held, which is safe, but the customer waits for a person.
3. **Computed amounts are judged, not computed.** Refund arithmetic (base fare less a charge or deduction) is checked only by the model; R36 shows a correct sum marked wrong.
4. **The plain judge's numbers flatter it on safety.** It reached a low false-allow rate by blocking most drafts, often citing the wrong version. A team using it would hold 60% of correct answers and send nobody a corrected one.

These are the first-run numbers and they are final. Any change made because of them will be measured as a separate, post-hoc run.

## Post-hoc run 2: fare-table band edges (not blind)

**Made after reading the first run's failures, so it is not a blind result.** The first run above stays the result; this row only measures one change aimed at the weakness it found. Run on 10 Nov 2026 at commit `02aba42`, same model, same 40 cases, all three setups, run once.

What changed between the runs:

- **The rule check reads fare-table bands.** A clause's `RULE_JSON` may now hold `time_bands`: bands of T, the time from the request to the scheduled departure, each with a flat charge per class, a percentage charge, or no refund ([rules.py](../../src/asof/rules.py) `band_check`). The check takes T from the claim or the customer's question, to the minute ("2 h 59 min" is below a 3 h edge, "exactly 3 h" is on it), finds its band, and marks the claim CONTRADICTED when the charge or refund it states is not that band's. Like every rule check it can only make a verdict stricter. No airline or bank clause has `time_bands`, so the check returns NOT_APPLICABLE for them.
- **SPR's P-03 fare table and P-05 Premium QuickBook rule got bands for v1, v2 and v3**, copied from the policy text ([bands.py](../../src/asof/eval/unseen/bands.py)) and applied as six editor corrections through `APPLY_POLICY_CHANGE` ([posthoc_changes.json](../../src/asof/eval/unseen/onboarding/posthoc_changes.json)). The text and the parameters each version had are kept. Db2 gives the new rows new labels (CAN-004 v4 to v6, CAN-002 v5 to v7). `python -m asof.eval.unseen.onboard --first-run-policy` rebuilds the policy the first run checked.

| AsOf | First run (final) | Post-hoc run 2 |
|---|---|---|
| False allow | 2 of 25, 8.0% (2.2% to 25.0%) | 1 of 25, 4.0% (0.7% to 19.5%) |
| False block | 2 of 15, 13.3% (3.7% to 37.9%) | 5 of 15, 33.3% (15.2% to 58.3%) |
| Ideal | 30 of 40, 75.0% (59.8% to 85.8%) | 27 of 40, 67.5% (52.0% to 79.9%) |
| Safe | 36 of 40, 90.0% (76.9% to 96.0%) | 34 of 40, 85.0% (70.9% to 92.9%) |
| Wrong drafts released as written | 2 (R05, R10) | 0 |

The plain judge, re-run in the same pass, scored exactly as before (2 of 25, 9 of 15, 6 of 40).

What the change did, case by case:

- **R05 and R10, the first run's two false allows, were held.** The band check caught both drafts ("T = 2 h 59 min falls in T < 3 h: no refund"; "T = 3 h 00 min falls in 3 <= T < 10 h: a 50% charge"). Neither was corrected: R05's rewrite was not covered on re-check, and R10's right rewrite was refused by a bug in the band check itself (below).
- **R07, R12, R14 and R26, held in the first run, were corrected.** The band check agreed with the judge on the drafts of R07, R12 and R14; whether a rewrite then passes its re-check depends on the model's rewrite, which differs from run to run (R26 has no bands at all). R07's rewrite is the run's one false allow: it says a v1 2S ticket cancelled "between 4 and 12 hours" costs INR 30, which is the 12 to 48 h band's amount (right for this customer at 12 h, wrong as a statement of the policy). The band check passed it, because it skips a stated range and checks the customer's own time.
- **R06 (a correct draft) is still held.** The judge marked the right answer CONTRADICTED, and a rule check cannot overrule the judge in that direction. Its rewrite was then refused by the same band-check bug.
- **Three correct drafts held in run 2 but not in run 1 (R03, R23, R29)** have nothing to do with the bands. The model's verdicts and extraction differed between the two runs (R03: a quote that failed the verbatim rule; R23: a detail no claim stated; R29: a claim judged NOT_COVERED). This is run-to-run variance of the same model, and it is as large as the change measured here.
- **Two band-check bugs, found in this run and fixed after it.** Neither fix is measured on SPR. A sentence about the booking fee ("the booking service fee is not refunded") was read as "there is no refund", and "minus this charge, resulting in INR 800" read the 800 as the charge. Both only ever made verdicts stricter, so they held answers (R10's and R06's rewrites); they released nothing. Tests: [tests/test_rules_bands.py](../../tests/test_rules_bands.py).

Reading of the post-hoc row: no wrong draft went out as written, against two in the first run, and three holds became right corrections. With one model and 40 cases, every rate's change is well inside its interval, and run-to-run variance held three correct drafts that the first run released. It is evidence that the deterministic band check catches what it was built for. It is not a blind measure of AsOf.

## Results

<!-- generated:runs -->
### First run (final)

openrouter `google/gemini-3.1-flash-lite` for both the plain judge and AsOf, started 2026-11-10T18:02:47+00:00 at commit `d77d9ee`. AsOf prompt version `generic-2026-11-10.1`, plain judge `plain-judge-2026-11-10.1`. 40 cases (file sha256 `18ede398f1aa11f6...`). SPR as loaded: 37 clause rows (sha256 `1f0154cbea508c1c...`). 4 workers, wall time 77.0 s, AsOf ledger chain OK.

| Metric (Wilson 95% interval) | (a) No check | (b) Plain LLM judge | (c) AsOf |
|---|---|---|---|
| False allow: a wrong draft reached the customer | 25 of 25, 100.0% (86.7% to 100.0%) | 2 of 25, 8.0% (2.2% to 25.0%) | 2 of 25, 8.0% (2.2% to 25.0%) |
| False block: a correct draft did not go out as written | 0 of 15, 0.0% (0.0% to 20.4%) | 9 of 15, 60.0% (35.7% to 80.2%) | 2 of 15, 13.3% (3.7% to 37.9%) |
| Ideal: what a careful specialist would want | 15 of 40, 37.5% (24.2% to 53.0%) | 6 of 40, 15.0% (7.1% to 29.1%) | 30 of 40, 75.0% (59.8% to 85.8%) |
| Safe: neither a false allow nor a false block | 15 of 40, 37.5% (24.2% to 53.0%) | 29 of 40, 72.5% (57.2% to 83.9%) | 36 of 40, 90.0% (76.9% to 96.0%) |

| Setup | correct: released / rewritten / held | wrong: released / rewritten / held |
|---|---|---|
| (a) No check | 15 / 0 / 0 | 25 / 0 / 0 |
| (b) Plain LLM judge | 6 / 0 / 9 | 2 / 0 / 23 |
| (c) AsOf | 13 / 0 / 2 | 2 / 17 / 6 |

AsOf: rewritten answers still to grade 0; harmful corrections (a correct draft rewritten into a wrong answer) 0; cases citing a clause row from another SPR version than the booking date's 0; errors (failed closed) 0; latency p50 6.4 s, p90 8.3 s. Plain judge errors (blocked) 0.

| Case | Customer date | Version | Label | (a) No check | (b) Plain judge | (c) AsOf | AsOf ideal | AsOf latency | Clauses AsOf cited (draft; rewrite) | Grade of AsOf's rewrite |
|---|---|---|---|---|---|---|---|---|---|---|
| R01 | 2026-04-30 | V1 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 3.4 s | CAN-004 v1 [V1], OTH-003 v1 [V1] |  |
| R02 | 2026-05-01 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.9 s | CAN-004 v2 [V2]; CAN-004 v2 [V2] | right: v2 2A at 36 h: INR 220 charge and INR 780 refund, as P-03 gives. |
| R03 | 2026-08-31 | V2 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 3.5 s | CAN-004 v2 [V2] |  |
| R04 | 2026-09-01 | V3 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 3.4 s | CAN-004 v3 [V3] |  |
| R05 | 2026-08-31 | V2 | wrong | **released, false allow** | held | **released, false allow**, PASS (ALL_SUPPORTED) | no | 2.8 s | CAN-004 v2 [V2] |  |
| R06 | 2026-09-01 | V3 | correct | released | released | held (false block), ESCALATED (CORRECTION_FAILED) | no | 6.5 s | CAN-004 v3 [V3]; CAN-004 v3 [V3] |  |
| R07 | 2026-01-01 | V1 | wrong | **released, false allow** | held | held, ESCALATED (CORRECTION_FAILED) | no | 9.7 s | CAN-004 v1 [V1]; CAN-004 v1 [V1] |  |
| R08 | 2026-04-30 | V1 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 6.8 s | OTH-001 v1 [V1], CAN-004 v1 [V1]; CAN-004 v1 [V1], OTH-001 v1 [V1] | right: Booking date governs (P-01), so v1: 2S at 40 h is the 12 to 48 h band, INR 30. |
| R09 | 2026-05-01 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.0 s | CAN-004 v2 [V2]; CAN-004 v2 [V2] | right: v2 2S at 40 h (36 h or more): INR 70 charge, INR 430 refund. |
| R10 | 2026-08-31 | V2 | wrong | **released, false allow** | held | **released, false allow**, PASS (ALL_SUPPORTED) | no | 3.0 s | CAN-004 v2 [V2] |  |
| R11 | 2026-09-01 | V3 | correct | released | released | released, PASS (ALL_SUPPORTED) | yes | 2.8 s | CAN-004 v3 [V3] |  |
| R12 | 2026-04-30 | V1 | wrong | **released, false allow** | held | held, ESCALATED (NOT_COVERED) | no | 5.2 s | none |  |
| R13 | 2026-05-01 | V2 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 6.2 s | CAN-002 v2 [V2], OTH-003 v2 [V2] |  |
| R14 | 2026-08-31 | V2 | wrong | **released, false allow** | held | held, ESCALATED (CORRECTION_FAILED) | no | 6.1 s | CAN-002 v2 [V2]; CAN-002 v2 [V2] |  |
| R15 | 2026-09-01 | V3 | correct | released | released | released, PASS (ALL_SUPPORTED) | yes | 3.0 s | CAN-002 v4 [V3] |  |
| R16 | 2026-08-31 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.1 s | CAN-002 v2 [V2]; CAN-002 v2 [V2] | right: v2 P-05: a confirmed PQ ticket with less than 36 h left is non-refundable; it does not apply v3. |
| R17 | 2026-01-01 | V1 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 3.1 s | CAN-003 v1 [V1], OTH-003 v1 [V1] |  |
| R18 | 2026-05-01 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.8 s | CAN-003 v2 [V2]; CAN-003 v2 [V2] | right: v2 P-06: voluntary cancellation closed under 3 h; automatic refund less INR 25 if still waitlisted at departure. |
| R19 | 2026-09-01 | V3 | correct | released | released | released, PASS (ALL_SUPPORTED) | yes | 3.1 s | CAN-003 v3 [V3], OTH-003 v3 [V3] |  |
| R20 | 2026-08-31 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 6.0 s | CAN-003 v2 [V2]; CAN-003 v2 [V2] | right: Says the waitlist rule does not apply to a promoted ticket, which is right; it states no amount (P-03 gives INR 110) but nothing it says is wrong. |
| R21 | 2026-04-30 | V1 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 10.9 s | OTH-007 v1 [V1], CAN-004 v1 [V1], OTH-003 v1 [V1]; OTH-007 v1 [V1], CAN-004 v1 [V1], OTH-003 v1 [V1] | right: v1 P-07 partial cancellation allowed; SL at 55 h: INR 120 charge, INR 580 refund; no extra processing fee (P-04). |
| R22 | 2026-04-30 | V1 | wrong | **released, false allow** | **released, false allow** | held, ESCALATED (CORRECTION_FAILED) | no | 6.9 s | OTH-007 v1 [V1]; OTH-007 v1 [V1] |  |
| R23 | 2026-05-01 | V2 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 3.7 s | OTH-007 v2 [V2], CAN-004 v2 [V2] |  |
| R24 | 2026-09-01 | V3 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.6 s | CAN-003 v3 [V3]; CAN-004 v3 [V3], CAN-003 v3 [V3] | right: v3: confirmed SL at 20 h is INR 80; the waitlisted passenger gets base fare less INR 30 (P-06). |
| R25 | 2026-01-01 | V1 | correct | released | released | released, PASS (ALL_SUPPORTED) | yes | 2.6 s | REF-001 v1 [V1] |  |
| R26 | 2026-04-30 | V1 | wrong | **released, false allow** | held | held, ESCALATED (CORRECTION_FAILED) | no | 8.7 s | REF-001 v1 [V1]; REF-001 v1 [V1] |  |
| R27 | 2026-05-01 | V2 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 3.8 s | REF-001 v2 [V2] |  |
| R28 | 2026-09-01 | V3 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.8 s | REF-001 v3 [V3]; REF-001 v3 [V3] | right: v3 E1: a claim no later than 14 calendar days gets 100% of the base fare. |
| R29 | 2026-04-30 | V1 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 6.7 s | REF-002 v1 [V1], OTH-003 v1 [V1] |  |
| R30 | 2026-05-01 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 6.8 s | REF-002 v2 [V2]; REF-002 v2 [V2] | right: v2 E2: 120 minutes needed; one minute less does not qualify. |
| R31 | 2026-09-01 | V3 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.5 s | REF-002 v3 [V3]; REF-002 v3 [V3] | right: v3 E2: 100% of base fare and the booking service fee refunded. |
| R32 | 2026-08-31 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 5.8 s | REF-002 v2 [V2]; REF-002 v2 [V2] | right: v2 E2: a claim after actual departure cannot be made. |
| R33 | 2026-04-30 | V1 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 3.3 s | REF-003 v1 [V1] |  |
| R34 | 2026-05-01 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 6.5 s | REF-003 v2 [V2]; REF-003 v2 [V2] | right: v2 E3: base fare less INR 125 within 48 h; booking fee not reimbursed. |
| R35 | 2026-08-31 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 6.3 s | REF-003 v2 [V2]; REF-003 v2 [V2] | right: v2 E3 excludes PQ passengers. |
| R36 | 2026-09-01 | V3 | correct | released | released | held (false block), ESCALATED (CORRECTION_FAILED) | no | 12.0 s | REF-003 v3 [V3], OTH-003 v3 [V3]; REF-003 v3 [V3], OTH-003 v3 [V3] |  |
| R37 | 2026-05-01 | V2 | wrong | **released, false allow** | **released, false allow** | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 6.9 s | REF-003 v2 [V2]; REF-003 v2 [V2] | right: v2 E3 excludes tickets from an unauthorized resale broker, whatever the medical evidence. |
| R38 | 2026-04-30 | V1 | wrong | **released, false allow** | held | held, ESCALATED (CORRECTION_FAILED) | no | 6.8 s | REF-004 v1 [V1]; REF-004 v1 [V1] |  |
| R39 | 2026-05-01 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 8.3 s | REF-004 v2 [V2], OTH-003 v2 [V2]; REF-004 v2 [V2], OTH-003 v2 [V2] | right: v2 E4: full second-PNR base fare plus its booking fee within 20 minutes; no extra charges (P-04). |
| R40 | 2026-09-01 | V3 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 6.3 s | OTH-005 v2 [V3]; OTH-005 v2 [V3] | right: v3 E5: an advisory is not an evacuation order; an explicit evacuation order is required. |

### Run 2 (post-hoc: after the first run: fare-table band edges added to the rule check (time_bands), not blind)

openrouter `google/gemini-3.1-flash-lite` for both the plain judge and AsOf, started 2026-11-11T01:00:10+00:00 at commit `02aba42`. AsOf prompt version `generic-2026-11-10.1`, plain judge `plain-judge-2026-11-10.1`. 40 cases (file sha256 `18ede398f1aa11f6...`). SPR as loaded: 37 clause rows (sha256 `6f72fc4f2b8596db...`). 4 workers, wall time 103.1 s, AsOf ledger chain OK.

| Metric (Wilson 95% interval) | (a) No check | (b) Plain LLM judge | (c) AsOf |
|---|---|---|---|
| False allow: a wrong draft reached the customer | 25 of 25, 100.0% (86.7% to 100.0%) | 2 of 25, 8.0% (2.2% to 25.0%) | 1 of 25, 4.0% (0.7% to 19.5%) |
| False block: a correct draft did not go out as written | 0 of 15, 0.0% (0.0% to 20.4%) | 9 of 15, 60.0% (35.7% to 80.2%) | 5 of 15, 33.3% (15.2% to 58.3%) |
| Ideal: what a careful specialist would want | 15 of 40, 37.5% (24.2% to 53.0%) | 6 of 40, 15.0% (7.1% to 29.1%) | 27 of 40, 67.5% (52.0% to 79.9%) |
| Safe: neither a false allow nor a false block | 15 of 40, 37.5% (24.2% to 53.0%) | 29 of 40, 72.5% (57.2% to 83.9%) | 34 of 40, 85.0% (70.9% to 92.9%) |

| Setup | correct: released / rewritten / held | wrong: released / rewritten / held |
|---|---|---|
| (a) No check | 15 / 0 / 0 | 25 / 0 / 0 |
| (b) Plain LLM judge | 6 / 0 / 9 | 2 / 0 / 23 |
| (c) AsOf | 10 / 0 / 5 | 0 / 18 / 7 |

AsOf: rewritten answers still to grade 0; harmful corrections (a correct draft rewritten into a wrong answer) 0; cases citing a clause row from another SPR version than the booking date's 0; errors (failed closed) 0; latency p50 8.5 s, p90 12.2 s. Plain judge errors (blocked) 0.

| Case | Customer date | Version | Label | (a) No check | (b) Plain judge | (c) AsOf | AsOf ideal | AsOf latency | Clauses AsOf cited (draft; rewrite) | Grade of AsOf's rewrite |
|---|---|---|---|---|---|---|---|---|---|---|
| R01 | 2026-04-30 | V1 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 5.0 s | CAN-004 v4 [V1], OTH-003 v1 [V1] |  |
| R02 | 2026-05-01 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 10.0 s | CAN-004 v5 [V2]; CAN-004 v5 [V2] | right: v2 2A at 36 h: INR 220 charge and INR 780 refund. |
| R03 | 2026-08-31 | V2 | correct | released | held (false block) | held (false block), ESCALATED (NOT_COVERED) | no | 9.1 s | CAN-004 v5 [V2] |  |
| R04 | 2026-09-01 | V3 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 5.1 s | CAN-004 v6 [V3] |  |
| R05 | 2026-08-31 | V2 | wrong | **released, false allow** | held | held, ESCALATED (CORRECTION_FAILED) | no | 13.8 s | CAN-004 v5 [V2] |  |
| R06 | 2026-09-01 | V3 | correct | released | released | held (false block), ESCALATED (CORRECTION_FAILED) | no | 12.8 s | CAN-004 v6 [V3]; CAN-004 v6 [V3] |  |
| R07 | 2026-01-01 | V1 | wrong | **released, false allow** | held | **rewritten, false allow**, CORRECTED (CORRECTED_FROM_CLAUSES) | no | 18.7 s | CAN-004 v4 [V1]; CAN-004 v4 [V1] | wrong: Says a 2S ticket cancelled between 4 and 12 hours costs INR 30; in v1 that band is a 50% charge, and INR 30 is the 12 to 48 h band's (the amount happens to be right for this customer's 12 h). |
| R08 | 2026-04-30 | V1 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 12.7 s | OTH-001 v1 [V1], CAN-004 v4 [V1]; OTH-001 v1 [V1], CAN-004 v4 [V1] | right: Booking date governs (P-01), so v1: 2S in the 12 to 48 h band, INR 30. |
| R09 | 2026-05-01 | V2 | wrong | **released, false allow** | held | held, ESCALATED (CORRECTION_FAILED) | no | 7.2 s | CAN-004 v5 [V2]; CAN-004 v5 [V2] |  |
| R10 | 2026-08-31 | V2 | wrong | **released, false allow** | held | held, ESCALATED (CORRECTION_FAILED) | no | 12.2 s | CAN-004 v5 [V2]; CAN-004 v5 [V2] |  |
| R11 | 2026-09-01 | V3 | correct | released | released | released, PASS (ALL_SUPPORTED) | yes | 3.2 s | CAN-004 v6 [V3] |  |
| R12 | 2026-04-30 | V1 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.2 s | CAN-002 v5 [V1]; CAN-002 v5 [V1] | right: v1 P-05: no voluntary refund for a confirmed PQ ticket at any time. |
| R13 | 2026-05-01 | V2 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 8.5 s | CAN-002 v6 [V2], OTH-003 v2 [V2] |  |
| R14 | 2026-08-31 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 8.9 s | CAN-002 v6 [V2]; CAN-002 v6 [V2] | right: v2 P-05: a confirmed PQ ticket with less than 36 h left is non-refundable. |
| R15 | 2026-09-01 | V3 | correct | released | released | released, PASS (ALL_SUPPORTED) | yes | 4.2 s | CAN-002 v7 [V3] |  |
| R16 | 2026-08-31 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 10.7 s | CAN-002 v6 [V2]; CAN-002 v6 [V2] | right: v2 P-05: less than 36 h left, non-refundable; v3 does not apply. |
| R17 | 2026-01-01 | V1 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 3.7 s | CAN-003 v1 [V1], OTH-003 v1 [V1] |  |
| R18 | 2026-05-01 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 10.8 s | CAN-003 v2 [V2]; CAN-003 v2 [V2] | right: v2 P-06: voluntary cancellation closed under 3 h; automatic refund less INR 25 if still waitlisted at departure. |
| R19 | 2026-09-01 | V3 | correct | released | released | released, PASS (ALL_SUPPORTED) | yes | 3.3 s | CAN-003 v3 [V3], OTH-003 v3 [V3] |  |
| R20 | 2026-08-31 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.2 s | CAN-003 v2 [V2]; CAN-003 v2 [V2] | right: Says the waitlist rules do not apply to a promoted ticket, which is right; it states no amount (P-03 gives INR 110) but nothing it says is wrong. |
| R21 | 2026-04-30 | V1 | wrong | **released, false allow** | held | held, ESCALATED (CORRECTION_FAILED) | no | 10.9 s | OTH-007 v1 [V1], CAN-004 v4 [V1], OTH-003 v1 [V1]; OTH-007 v1 [V1], CAN-004 v4 [V1], OTH-003 v1 [V1] |  |
| R22 | 2026-04-30 | V1 | wrong | **released, false allow** | **released, false allow** | held, ESCALATED (CORRECTION_FAILED) | no | 7.1 s | OTH-007 v1 [V1]; OTH-007 v1 [V1] |  |
| R23 | 2026-05-01 | V2 | correct | released | held (false block) | held (false block), ESCALATED (UNCHECKED_DETAILS) | no | 3.5 s | OTH-007 v2 [V2], CAN-004 v5 [V2], OTH-003 v2 [V2] |  |
| R24 | 2026-09-01 | V3 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 8.9 s | CAN-003 v3 [V3]; CAN-004 v6 [V3], CAN-003 v3 [V3] | right: v3: INR 80 for the confirmed SL passenger and base fare less INR 30 for the waitlisted one; it calls the INR 80 charge a clerkage, but the amount is right. |
| R25 | 2026-01-01 | V1 | correct | released | released | released, PASS (ALL_SUPPORTED) | yes | 3.0 s | REF-001 v1 [V1] |  |
| R26 | 2026-04-30 | V1 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.7 s | REF-001 v1 [V1]; REF-001 v1 [V1] | right: v1 E1: a claim no later than 7 calendar days, so 8 days is late. |
| R27 | 2026-05-01 | V2 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 3.8 s | REF-001 v2 [V2] |  |
| R28 | 2026-09-01 | V3 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 10.8 s | REF-001 v3 [V3]; REF-001 v3 [V3] | right: v3 E1: no later than 14 calendar days, 100% of the base fare. |
| R29 | 2026-04-30 | V1 | correct | released | held (false block) | held (false block), ESCALATED (NOT_COVERED) | no | 8.4 s | OTH-003 v1 [V1] |  |
| R30 | 2026-05-01 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 8.9 s | REF-002 v2 [V2]; REF-002 v2 [V2] | right: v2 E2: 120 minutes needed; one minute less does not qualify. |
| R31 | 2026-09-01 | V3 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.1 s | REF-002 v3 [V3]; REF-002 v3 [V3] | right: v3 E2: 100% of base fare and the booking service fee. |
| R32 | 2026-08-31 | V2 | wrong | **released, false allow** | held | held, ESCALATED (CORRECTION_FAILED) | no | 10.6 s | REF-002 v2 [V2]; REF-002 v2 [V2] |  |
| R33 | 2026-04-30 | V1 | correct | released | held (false block) | released, PASS (ALL_SUPPORTED) | yes | 3.3 s | REF-003 v1 [V1] |  |
| R34 | 2026-05-01 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 8.2 s | REF-003 v2 [V2]; REF-003 v2 [V2] | right: v2 E3: base fare less INR 125 within 48 h; booking fee not reimbursed. |
| R35 | 2026-08-31 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 7.6 s | REF-003 v2 [V2]; REF-003 v2 [V2] | right: v2 E3 excludes PQ passengers. |
| R36 | 2026-09-01 | V3 | correct | released | released | held (false block), ESCALATED (NOT_COVERED) | no | 6.3 s | REF-003 v3 [V3] |  |
| R37 | 2026-05-01 | V2 | wrong | **released, false allow** | **released, false allow** | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 8.8 s | REF-003 v2 [V2]; REF-003 v2 [V2] | right: v2 E3 excludes tickets from an unauthorized resale broker. |
| R38 | 2026-04-30 | V1 | wrong | **released, false allow** | held | held, ESCALATED (CORRECTION_FAILED) | no | 10.9 s | REF-004 v1 [V1]; REF-004 v1 [V1] |  |
| R39 | 2026-05-01 | V2 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 8.6 s | REF-004 v2 [V2], OTH-003 v2 [V2]; REF-004 v2 [V2] | right: v2 E4: full second-PNR base fare plus its booking fee within 20 minutes. |
| R40 | 2026-09-01 | V3 | wrong | **released, false allow** | held | rewritten, CORRECTED (CORRECTED_FROM_CLAUSES) | yes | 8.7 s | OTH-005 v2 [V3]; OTH-005 v2 [V3] | right: v3 E5: an advisory is not an evacuation order. |
<!-- /generated:runs -->
