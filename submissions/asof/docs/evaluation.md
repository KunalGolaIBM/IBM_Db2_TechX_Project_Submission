# Evaluation

How AsOf's check is measured, with every run kept. The [README](../README.md#evaluation-the-frozen-test-split) has the latest numbers; this page has the method, the earlier runs and what changed between them. Every per-case decision is in [eval/](eval/), and [eval_results.md](eval_results.md) is rebuilt from those files after each run.

- [The frozen test splits](#the-frozen-test-splits): how the cases were written and frozen, every run of the nine splits, and the one run that released a wrong draft
- [On IBM watsonx.ai](#on-ibm-watsonxai): the airline split on `ibm/granite-4-h-small`
- [Lists: who counts as family, which documents count](#lists-who-counts-as-family-which-documents-count): the rule that came out of the watsonx.ai miss
- [Why the date matters, measured](#why-the-date-matters-measured): the same check, told every case is on 7 Nov 2026
- [Fewer needless holds, measured on new frozen splits](#fewer-needless-holds-measured-on-new-frozen-splits)
- [Evaluation: the bank fee schedule (second domain)](#evaluation-the-bank-fee-schedule-second-domain)

Routing and policy intake have evaluations of their own: [routing_eval.md](routing_eval.md) and [intake_eval.md](intake_eval.md).

## The frozen test splits

`python -m asof.eval --split test` runs the check on the 40 airline cases and writes [eval_results.md](eval_results.md), with every per-case decision recorded in [eval/](eval/). Dates on this page are Eastern time; the results file stamps each run in UTC, so a run late on 7 Nov appears there as 8 Nov. The 40 test cases are new scenarios, none used while building or choosing the model. They were committed (`81b5b69`) before the first run and are frozen: a unit test pins their SHA-256 and the runner refuses to run them if it changes. The 20-case dev split holds the scenarios used while debugging. Each case is labelled with the decision it should get and the clause version its key claim must be checked against.

**Latest run** (Sun 8 Nov, OpenRouter `google/gemini-3.1-flash-lite`, all nine frozen splits, commits `333f14b` to `8058e85`). Since `0be4f60` the check has not changed: the commits between added the specialist inbox, correction notices and routing, which run only when asked for, and type annotations. It measures the check as submitted:

| Frozen split | Cases | False allow | False block | Safe | Ideal | Citation | p50 |
|---|---|---|---|---|---|---|---|
| Airline `test` | 40 | **0 of 26** | 0 of 14 | 100% | 100% | 100% | 5.6 s |
| `escalation-test`: aimed at the known causes of needless holds, both domains | 33 | **0 of 22** | 3 of 11 | 90.9% | 87.9% | 96.7% | 5.9 s |
| `situation-test3`: premise drafts, pinned before the premise change | 20 | **0 of 12** | 0 of 8 | 100% | 90.0% | 95.0% | 6.0 s |
| `list-test`: relations and documents a clause's list leaves out, pinned before the list check | 16 | **0 of 9** | 1 of 7 | 93.8% | 81.2% | 100% | 5.8 s |
| `situation-test2`: drafts whose premise about the customer contradicts or restates the question | 12 | **0 of 7** | 0 of 5 | 100% | 91.7% | 91.7% | 5.8 s |
| `situation-test`: the same kind, not blind | 12 | **0 of 7** | 0 of 5 | 100% | 91.7% | 75.0% | 6.1 s |
| Bank `bank-test2`: blind on its first run | 22 | **0 of 14** | 0 of 8 | 100% | 100% | 100% | 6.0 s |
| Bank `bank-test` (not blind) | 26 | **0 of 16** | 0 of 10 | 100% | 100% | 100% | 5.7 s |
| `extractor-test`: drafts that try to talk the claim extractor out of a wrong claim | 10 | **0 of 8** | 0 of 2 | 100% | 90.0% | 90.0% | 5.9 s |

0 of 121 wrong drafts released; 4 of 70 correct drafts held or rewritten. L10 was held in every run (the extractor turns "you qualify" into a claim no clause states). ET09 (the rule check read the premise "the 24-hour free cancellation period has passed" as a mismatch), ET12 (the judge said supported, but its citation failed the check that the quote appears word for word in a clause in force, so the claim became not covered) and ET14 (the judge found the 8-hour condition not covered) passed at `0be4f60`; ET09 and ET12 have been decided both ways in earlier runs of this split. All four are frozen test cases, so nothing was tuned for them.

**Why 4 of 70 held and not 1: measured, not assumed.** The commits since `0be4f60` added code that ordinary checks do not run, so the rise could be the model's run-to-run variation, but that was tested rather than assumed. The four held cases were run 10 times each on the hosted model in four arms ([the 160 records](live-runs/held-correct-drafts-ab.json)):

| Case | The submitted check | The same, inbox rule replaced by a tripwire | The `0be4f60` code | The submitted check, premise rule off |
|---|---|---|---|---|
| ET09 | held 3 of 10 | 3 of 10 | 6 of 10 | 2 of 10 |
| ET12 | 0 of 10 | 0 of 10 | 0 of 10 | 0 of 10 |
| ET14 | 2 of 10 | 3 of 10 | 1 of 10 | 0 of 10 |
| L10 | 9 of 10 | 9 of 10 | 9 of 10 | 9 of 10 |
| All four | 14 of 40 | 15 of 40 | 16 of 40 | 11 of 40 |

- **The specialist inbox's uncovered-sentence rule (`7829f8f`) is not in the check.** It is called only from `review.py`, for a specialist's reply; replaced by functions that count their calls and raise, it was called 0 times in 40 checks, with the same holds.
- **The old code holds these drafts at least as often.** The `0be4f60` code held 16 of 40 against the submitted check's 14, by the same mechanisms. The frozen run at `0be4f60` happened to pass ET09, ET12 and ET14 together; the latest run happened to hold all three. ET12 was not held once in these 40 runs.
- **What holds each one.** L10: the judge finds the draft's conclusion, "you qualify for the bereavement fare", stated by no clause (9 of 10 in every arm; a person decides). ET09: two causes. Either the rule check reads "the 24-hour free cancellation period" as a $0 fee against CXL-003's $100 and overrules a correct judge (the false block described [below](#fewer-needless-holds-measured-on-new-frozen-splits), kept so as not to weaken a deterministic check; 1 or 2 of 10 in every arm), or the extractor's claim "the 24-hour free cancellation period has passed" gets a SUPPORTED verdict whose quote is not in the clause, so it is downgraded (1 to 4 of 10 in three arms, 0 in the fourth). ET14: the judge does not connect "flights of 8 hours or less" with PET-004's "not accepted on flights scheduled for more than 8 hours"; that claim comes from the extractor (the draft has no premise sentence), so the premise rule's 0 of 10 there is chance.
- **The premise rule (`822608e`), which is in the check**, was in place for both runs, and none of the four holds depends on it: with it off, ET09 was still held 2 of 10 and L10 9 of 10, and ET14's held claim is not one it adds. It stays, since it is what stopped the SU01 pattern of releasing a wrong draft.

**The run before, at `0be4f60`** (Sat 7 Nov, after the list check described [below](#lists-who-counts-as-family-which-documents-count)):

| Frozen split | Cases | False allow | False block | Safe | Ideal | Citation | p50 |
|---|---|---|---|---|---|---|---|
| Airline `test` | 40 | **0 of 26** | 0 of 14 | 100% | 100% | 100% | 6.0 s |
| `escalation-test`: aimed at the known causes of needless holds, both domains | 33 | **0 of 22** | 0 of 11 | 100% | 100% | 100% | 6.6 s |
| `situation-test3`: premise drafts, pinned before the premise change (its baseline is below) | 20 | **0 of 12** | 0 of 8 | 100% | 90.0% | 100% | 6.4 s |
| `list-test`: relations and documents a clause's list leaves out, pinned before the list check | 16 | **0 of 9** | 1 of 7 | 93.8% | 75.0% | 100% | 6.3 s |
| `situation-test2`: drafts whose premise about the customer contradicts or restates the question; blind until its `5861368` run | 12 | **0 of 7** | 0 of 5 | 100% | 83.3% | 91.7% | 6.5 s |
| `situation-test`: the same kind, not blind (its first run found the gap; see below) | 12 | **0 of 7** | 0 of 5 | 100% | 75.0% | 75.0% | 6.4 s |
| Bank `bank-test2`: blind on its first run (pinned in `bcce2f3`) | 22 | **0 of 14** | 0 of 8 | 100% | 100% | 100% | 6.3 s |
| Bank `bank-test` (not blind, see below) | 26 | **0 of 16** | 0 of 10 | 100% | 100% | 100% | 6.0 s |
| `extractor-test`: drafts that try to talk the claim extractor out of a wrong claim | 10 | **0 of 8** | 0 of 2 | 100% | 100% | 100% | 23.4 s |

Across the seven original splits, 0 of 100 wrong drafts were released and none of the 55 correct drafts was held; on `situation-test3`, 0 of 12 and 0 of 8; on `list-test`, 0 of 9 released and 1 of 7 held (L10, a correct "a grandparent counts" answer held for a person). The previous run, at `a4cb55f`, held T24, ET09 and SW20; none of them involves a list, so their passing this time is the model's run-to-run variation, not the list check. `extractor-test`'s median latency was a slow spell at the provider (an eval run has no fallback). With no false allows, the 95% upper bound on the false-allow rate is about 3/n (the rule of three): under 3% across the 100, about 11% on the airline split's 26.

**An earlier run released a wrong draft, and what changed.** At `5861368`, with the check unchanged since `512ee74`, SU01 on `situation-test2`, then blind, was released. The customer says the pilot reported a brake fault; the draft says the delay was caused by weather, so there is no compensation. The extractor restated the draft's premise as a general rule ("Delays caused by weather are outside our control and not eligible for compensation"), the judge rightly found that rule in DLY-004, and nothing compared the dropped premise with the question. The same case had been held at `512ee74`; SU01 was also released in the date ablation at `da7804d`, and SU02 in the `5861368` ablation, where the extractor wrote its claim from the question's 11 kg instead of the draft's "under 8 kg". Neither case depends on the date, so this was a gap, not noise. Before changing anything, 20 new premise cases were written in both domains and pinned (`situation-test3`, `0116ee5`); on the unchanged check they released **2 of 12** wrong drafts. Two deterministic checks then went in behind the extractor, developed on the dev splits only ([gate.py](../src/asof/gate.py)):

- a sentence holding a premise about this customer ("because", "since", "given that", "as you ...") that no claim keeps is judged as a claim of its own, copied from the draft, so the judge compares it with the question;
- a claim whose amount, duration or count differs from every number of that kind in the draft holds the answer as an unchecked detail. It can only hold.

An independent review of the first version found that an added sentence counted as stating its numbers, so a number the extractor dropped could escape the coverage hold, and that claims could exceed the ledger's limit. Both were fixed before the numbers below: only extracted claims count for coverage, and extracted plus added claims stay within 8.

On the same pinned split after the change (`822608e`): **0 of 12 released, 0 of 8 correct drafts stopped, ideal decisions 75% to 85%**; after the review fixes (`a4cb55f`): 0 of 12 released, 1 of 8 held, ideal 85%. The second check did not fire in any split; it is a backstop for the SU02 pattern. `situation-test2` stopped being blind with the run that motivated the change; `bank-test2` has never motivated one: 0 of 14 released. The other splits were run before and after changes their failures motivated, so they show the check holding up, not a blind estimate.

## On IBM watsonx.ai

Run on a real watsonx.ai account (Lite plan, us-south) on Sat 7 Nov at `ac86d09`, the same check as the OpenRouter runs above.

- **Model choice.** Four watsonx.ai chat models were tried on four airline dev cases (never test cases): `ibm/granite-4-h-small`, `meta-llama/llama-3-3-70b-instruct`, `mistralai/mistral-small-3-1-24b-instruct-2503` and `openai/gpt-oss-120b`. None released a wrong draft; Llama, Mistral and gpt-oss made the ideal decision in 4 of 4 and Granite in 3 of 4 (the fourth held for a person, which is safe). Granite was the fastest (median 5.1 s; gpt-oss took 53 s) and used the fewest tokens, and it is IBM's own model, so it ran the frozen split. The Lite plan's monthly token allowance covered one 40-case split, so the other eight are not run on watsonx.ai.
- **The airline `test` split on `ibm/granite-4-h-small`:**

| | watsonx.ai `ibm/granite-4-h-small` (`ac86d09`) | OpenRouter `gemini-3.1-flash-lite` (`a4cb55f`) | Ollama `qwen2.5:7b-instruct` (`a4cb55f`) |
|---|---|---|---|
| False allow (wrong drafts released) | **1 of 26** (3.8%) | **0 of 26** | **0 of 26** |
| False block (correct drafts held or rewritten) | 3 of 14 | 1 of 14 | 5 of 14 |
| Safe / ideal decisions | 90.0% / 85.0% | 97.5% / 97.5% | 87.5% / 67.5% |
| Citation accuracy | 97.1% | 100% | 91.4% |
| Latency per answer, p50 | 5.7 s | 7.2 s | 40.5 s |
| Model calls / tokens per check | 4.1 / about 4,200 | 4.0 / not recorded | 4.6 / local |

- **The miss that matters: T20.** The draft says a mother-in-law counts as immediate family; BRV-001's list does not include in-laws. Granite judged the claim supported and quoted BRV-001's real list sentence, so the verbatim-quote rule could not catch it, and at that commit the rule check did not read lists. It is the same misreading local Ollama made in its first run of this split. The default model got it right in every run. The [list check](#lists-who-counts-as-family-which-documents-count) added afterwards flags this claim; the split was not re-run on watsonx.ai, because the Lite plan's monthly tokens were spent.
- **The three holds:** T02 and T05 were held because Granite's claims left out a detail the draft stated (the coverage check); T33 because Granite judged a premise about the customer not covered. All three went to a person; nothing wrong was released.
- **Policy intake on Granite** (the frozen 11-item evaluation): 0 of 11 items came back right, and every wrong proposal was blocked (6), or missing (5). The checks kept anything wrong from being acceptable, but three proposals that matched no expected item passed them: Granite proposed the revised BRV-001 and CRD-002 as new clauses instead of changes to the existing ones. A second extraction of one document came back largely right, so Granite varies from run to run here. Use the default model for intake ([docs/intake_eval.md](intake_eval.md)).
- **What this shows:** AsOf runs end to end on IBM's stack (Db2 for the policy, the as-of retrieval and the ledger, watsonx.ai for the model and the embeddings), and the model matters: the deterministic layer caught most of a weaker model's mistakes but not a misread list, which led to the list check. The same check, same cases and same safeguards produced 0 false allows on the default model and 1 on Granite.

## Lists: who counts as family, which documents count

The watsonx.ai run released T20: the draft says a mother-in-law counts as immediate family, Granite judged that supported by BRV-001 and quoted its real list sentence, so the verbatim-quote rule could not catch it, and the rule check did not read lists. Local Ollama had made the same misreading in its first run. So the rule check now reads the two list parameters in the corpus ([rules.py](../src/asof/rules.py)): `eligible_relations` (BRV-001) and `accepted_documents` (BRV-003). It maps what a claim names onto the list's own terms (a stepfather is a step-parent; "your partner's mother" is an in-law), and a claim that something the list leaves out qualifies, or that something it names does not, is a mismatch, which forces CONTRADICTED like any other. It reads only a part of a claim that says the thing qualifies or is accepted, with that part's negation, so "cousins are not included" agrees with the list. Ambiguous words ("partner", "half-brother") are left to the judge.

Before the change, 16 new airline cases were written and pinned (`list-test`, `f4d19dd`): nine wrong drafts (an in-law, a cousin, an aunt, a fiancée, nieces, a friend, an obituary, a newspaper notice, a family member's note) and seven correct ones, two of which rightly exclude a relation. On the unchanged check, OpenRouter released 0 of 9 and held 1 of 7; local Ollama released **1 of 9** (L04, a fiancée) and held 1 of 7. After the change (`0be4f60`): OpenRouter 0 of 9 and 1 of 7; Ollama **0 of 9** (the rule overruled its judge on L04) and 1 of 7. The rule was developed on `list-dev` (8 cases) and unit tests with other wording, but the same author wrote the term lists and the test cases, so `list-test` shows the rule works on those phrasings, not how far it generalises. The rule flags T20's own claim; that was checked directly, not by a new watsonx.ai run (the Lite plan's tokens were spent). Every split was re-run with it: no wrong draft released, and the rule check now finds the mismatch itself in 66 of the 100 wrong drafts in the seven original splits (63 before).

## Why the date matters, measured

`python -m asof.eval --ablation current-policy` runs AsOf's own check with every case's date replaced by 7 Nov 2026: a stand-in for a checker that only knows the current policy, scored against the same labels. Both arms ran at the same commit (`a4cb55f`, the check before the list check was added), one run each. The comparison that matters is on the 25 of 155 frozen cases in the seven original splits whose key clause changed between the customer's date and 7 Nov 2026. That is a stress set, not a production rate: the splits were written around version changes, many on the last day of a version.

| | With the customer's date (AsOf) | As of 7 Nov 2026 instead |
|---|---|---|
| Wrong drafts released | **0 of 16** | **6 of 16** |
| Correct drafts rewritten or held | 1 of 9 | 8 of 9 |
| All seven splits: wrong drafts released | 0 of 100 | 6 of 100 |
| All seven splits: correct drafts rewritten or held | 2 of 55 | 8 of 55 |

All 8 correct drafts stopped among the 25 were rewritten to the policy in force on 7 Nov 2026, which did not apply on the customer's date: for that customer, a correct answer replaced by a wrong one. The paired differences all point one way (6 releases and 7 rewrites that only the date-blind arm made, none the other way), exact McNemar p ≈ 0.03 and 0.02. On the 130 cases whose key clause is the same on both dates, 6 decisions differed between the two runs, none of them a release: wrong drafts corrected in one run and held in the other, and one correct draft (ET09) held in one and passed in the other. That is the run-to-run noise in this comparison. The six date releases are the Moffatt pattern (T21, X01: a retroactive bereavement claim, wrong in March and right from May) and terms that only became true later, quoted for a date when the old terms applied (BN12: a 1% foreign transaction fee on a date when it was 3%; BT21: "there's never a fee to close an account" while a $25 early-closure fee applied). The per-case records are in [docs/eval/](eval/) (files named `*-ablation-current-policy*`). Earlier pairs of runs gave 7 of 16 and 8 of 9 (AsOf at `512ee74` with the ablation at `da7804d`, and both at `5861368`) and 6 of 16 and 8 of 9 (both at `822608e`).

<details>
<summary><b>Earlier runs of the same splits, and what moved</b></summary>

**The same cases across runs** (false allow, false block, ideal decisions; every run's per-case results are in [docs/eval/](eval/)):

| Frozen split | `a7bece1` (`bcce2f3` for `bank-test2`, its blind run) | `36291ab`, after the audit fixes | `397c920`, after the review fixes | `4e6687c`, fewer needless holds | `512ee74`, situation check | `5861368`, same check | `822608e`, premise checks | `a4cb55f`, review fixes |
|---|---|---|---|---|---|---|---|---|
| Airline `test` | 0 of 26, 1 of 14, 92.5% | 0 of 26, 1 of 14, 90.0% | 0 of 26, 2 of 14, 92.5% | 0 of 26, 0 of 14, 100% | 0 of 26, 1 of 14, 95.0% | 0 of 26, 1 of 14, 97.5% | 0 of 26, 1 of 14, 97.5% | 0 of 26, 1 of 14, 97.5% |
| Bank `bank-test` | 0 of 16, 0 of 10, 88.5% | 0 of 16, 0 of 10, 84.6% | 0 of 16, 0 of 10, 88.5% | 0 of 16, 0 of 10, 100% | 0 of 16, 0 of 10, 100% | 0 of 16, 0 of 10, 100% | 0 of 16, 0 of 10, 100% | 0 of 16, 0 of 10, 100% |
| `extractor-test` | 0 of 8, 0 of 2, 90.0% | 0 of 8, 0 of 2, 80.0% | 0 of 8, 0 of 2, 90.0% | 0 of 8, 0 of 2, 100% | 0 of 8, 0 of 2, 100% | 0 of 8, 0 of 2, 100% | 0 of 8, 0 of 2, 100% | 0 of 8, 0 of 2, 100% |
| Bank `bank-test2` | 0 of 14, 0 of 8, 95.5% | 0 of 14, 0 of 8, 95.5% | 0 of 14, 0 of 8, 95.5% | 0 of 14, 0 of 8, 100% | 0 of 14, 0 of 8, 100% | 0 of 14, 0 of 8, 95.5% | 0 of 14, 0 of 8, 100% | 0 of 14, 0 of 8, 100% |
| `escalation-test` | | | `8deb079` (baseline): 0 of 22, 2 of 11, 75.8% | 0 of 22, 3 of 11, 87.9% | 0 of 22, 2 of 11, 87.9% | 0 of 22, 1 of 11, 90.9% | 0 of 22, 1 of 11, 93.9% | 0 of 22, 1 of 11, 97.0% |
| `situation-test` | | | | | 0 of 7, 0 of 5, 66.7% | 0 of 7, 0 of 5, 75.0% | 0 of 7, 0 of 5, 91.7% | 0 of 7, 0 of 5, 75.0% |
| `situation-test2` (blind until `5861368`) | | | | | 0 of 7, 0 of 5, 83.3% | **1 of 7**, 0 of 5, 91.7% | 0 of 7, 0 of 5, 83.3% | 0 of 7, 0 of 5, 91.7% |
| `situation-test3` (pinned in `0116ee5`) | | | | | | `0116ee5`, unchanged check: **2 of 12**, 0 of 8, 75.0% | 0 of 12, 0 of 8, 85.0% | 0 of 12, 1 of 8, 85.0% |

In all eight runs of the first four splits, none of their 64 wrong drafts was released. What moved, and why (this list covers the runs up to `397c920`; the columns from `4e6687c` on are explained in [Fewer needless holds](#fewer-needless-holds-measured-on-new-frozen-splits)):

- **T06, held in both runs since the coverage check's fix:** the extractor dropped "after the first 24 hours" from its claim, so no claim stated the 24 hours and the deterministic coverage check held a correct draft. Twice in a row looks systematic for this draft, not chance. It is a frozen test case, so the check was not tuned for it; it stays a reported false block, the cost of the backstop.
- **T33** is the familiar one from earlier runs: the extractor turned the customer's own situation into a policy claim that no clause covers. **T24** (the earlier false block, a correct $75 fee called contradicted) passed in both later runs.
- **Everything else** is the hosted model's run-to-run variance (it is called without a fixed temperature) swapping between two safe outcomes, corrected or escalated, mostly when the judge paraphrased instead of quoting and the verbatim-quote rule downgraded the claim. No frozen draft contains a "-free" word, so the coverage-check fix in `d87a552` cannot have changed any of them.
- **Latency:** the airline split's median fell from 6.7 s to 4.6 s per answer, and the whole split from 78 s to 46 s. Most of that is the connection pool added in between (it removed about 3 s of connection setup and teardown per check on this machine); the hosted model's own latency also varies between runs.

</details>

## Fewer needless holds, measured on new frozen splits

Holding a draft for a specialist is safe, but every needless hold is a customer kept waiting. The runs up to `397c920` showed why AsOf held drafts it could have corrected or passed (T06, T12, T20, T31, T33, T36 and similar). Before changing anything, 33 new cases aimed at those causes were written in both domains and pinned (`8deb079`), and a 14-case dev split was written to tune on. The baseline run on the pinned split, with the check unchanged: **0 of 22 wrong drafts released, ideal 75.8%, and 5 of the 8 wrong amounts held instead of corrected.**

The causes, and what changed (in `11ef14c`, tuned on the dev splits only):

- **A contradiction with a short quote was thrown away.** On a wrong amount the judge often quotes only the number (`'$35'`, `'60 days'`). That is exact text from the clause, but shorter than the 12-character minimum, so the claim fell to NOT_COVERED and the draft was held. A CONTRADICTED verdict is now grounded by the clause sentence that holds its exact quote, or, if the quote is not in the clause at all, by the deterministic rule check finding the mismatch in `RULE_JSON`. A contradiction can only lead to a rewrite that must pass a full re-check, or to a hold, so this releases nothing new; a SUPPORTED verdict still needs a verbatim quote of 12 characters or more.
- **A rule key with its unit inside was not read.** `min_days_before_departure` was ignored, so "booked at least 7 days before departure" was compared, as 168 hours, with the 24-hour window and called a mismatch, which sank correct rewrites (X04). Unit words inside a key are now read.
- **Extraction lost qualifiers and conditions.** "Incoming wires, domestic or international, are free" became two wrong claims; "after the first 24 hours, $100" lost its condition (T06). The extraction prompt now keeps a rule's qualifiers and conditions in its claim.
- **Rewrites added advice the clauses do not state** ("you can avoid this fee by choosing electronic statements"), which the re-check could not support (ET27, T20). The rewrite prompt now forbids advice and conclusions the clauses do not state.

After the change (`4e6687c`): ideal decisions on the pinned split rose from **75.8% to 87.9%**, all 8 wrong amounts were corrected, and the four original frozen splits scored 100% ideal with 0 false allows.

**A gap the new work exposed: premises about the customer.** A draft can be right about the policy and wrong about the customer ("since your delay was within our control" when the customer said a snowstorm caused it). The judge had never seen the customer's question, so it could not notice. A 12-case `situation-test` split, written after the first fix and pinned before its first run, showed the size of it: **3 of 7 drafts with a false premise were released** (business class called Economy, an account's age, refunds already used). Put through the code from before that day's changes (a probe, not a recorded run), the same cases released 4 of 7, so the gap was old, not new. The fix (`12e8d93`), tuned on a 9-case `situation-dev` split:

- the judge now sees the customer's question, as delimited data like everything else, and must answer, for every claim, whether the claim assumes something about this customer that the question states differently (`situation_conflict`); a SUPPORTED claim with a conflict becomes CONTRADICTED, so the flag can only make a verdict stricter;
- a delay the claim states for the customer ("you arrived 10 hours late") is checked deterministically against the delay in the question ("2 hours late"), whatever the judge says;
- extraction keeps what a draft says about the customer as said about the customer, instead of turning it into a general rule.

A second split, `situation-test2`, was then written from scratch and pinned before its first run, as the blind measure: **0 of 7 false premises released, 0 of 5 correct drafts held** at `512ee74`. The next run of the same check, at `5861368`, released SU01: one blind run was not enough to show the premise gap closed. The premise checks that followed, and a new split pinned before them, are described with [the latest runs](#the-frozen-test-splits). What it costs: the judge sometimes flags a conflict the question does not support, which can hold or rewrite a correct draft; that is the side to err on.

What is still held, by design: a draft that classifies the customer's situation in a way no clause states ("a mechanical problem is within our control", ET16). The policy lists the causes outside the airline's control but does not say which others are inside it, so a person decides. In the `512ee74` run, `escalation-test` stopped two correct drafts. ET12 was held because the judge's quote on a SUPPORTED verdict was not verbatim; that rule was not relaxed. ET09 was rewritten because the rule check read "free" in "the 24-hour free cancellation period has passed" as a $0 fee against CXL-003's $100 and overruled a correct judge. ET09 is a frozen case, and narrowing what counts as "free" would weaken a deterministic check, so it stays a reported false block; it passed at `5861368` and `822608e`, and at `a4cb55f` it was held for another reason, a judge quote that was not verbatim.

The first bank split stopped being blind when its run found a gap in MTF-003's rule data that was then fixed, so `bank-test2`'s first run is the bank number to quote: written after the fix, pinned before its run. In the `a4cb55f` run the investigating agent ran in 6 of 40 airline checks and 3 of 26 bank checks, and found a clause the first retrieval missed in 3 and 2 of them; at `822608e` it ran in 6 and 3 and found one in all 9; at `512ee74` it ran in 5 and 3; in the `397c920` run it ran in 10 and 8, and found one in 5 and 6 (the per-case records keep `agent_tool_calls` and `agent_new_clauses`).

<details>
<summary><b>History of the airline split: both providers, every run, every miss</b></summary>

**History of the airline split** (40 cases: 14 correct drafts, 26 wrong for their date). Same cases in every run; every run's per-case results are in [docs/eval/](eval/):

| Metric | OpenRouter `gemini-3.1-flash-lite`, before the agent (`eefc50c`) | OpenRouter, LangGraph check with the agent, run 1 (`b49f60f`) | OpenRouter, agent, run 2 (`1ffe744`) | Ollama `qwen2.5:7b-instruct`, local, no key, before the agent (run at `4b103fd`, recorded in `a4207d8`) | Ollama, situation check (`da7804d`, 7 Nov) | Ollama, premise checks (`a4cb55f`, run at `14586b2`) |
|---|---|---|---|---|---|---|
| **False-allow rate** (wrong drafts released as PASS) | **0.0%** (0 of 26) | **0.0%** (0 of 26) | **0.0%** (0 of 26) | **3.8%** (1 of 26) | **0.0%** (0 of 26) | **0.0%** (0 of 26) |
| False-block rate (correct drafts rewritten or escalated) | 7.1% (1 of 14) | 7.1% (1 of 14) | 7.1% (1 of 14) | 21.4% (3 of 14) | 35.7% (5 of 14) | 35.7% (5 of 14) |
| Safe decisions | 97.5% | 97.5% | 97.5% | 90.0% | 87.5% | 87.5% |
| Ideal decisions | 92.5% | 90.0% | 90.0% | 82.5% | 67.5% | 67.5% |
| Citation accuracy (key claim checked against the right version) | 100% | 94.3% | 97.1% | 91.4% | 88.6% | 91.4% |
| Errors (failed closed) | 0 | 0 | 0 | 0 | 0 | 0 |
| Latency per answer, p50 | 5.9 s | 6.7 s | 6.4 s | 37.9 s | 51.6 s | 40.5 s |
| LLM calls per answer | 3.6 | 4.3 | 4.3 | 3.65 | 4.58 | 4.58 |
| Whole split | 66 s (4 workers) | 75 s | 73 s | 32 min (1 worker) | 41 min (1 worker) | 32 min (1 worker) |

**What the agent did, honestly.** On this split the LangGraph agent step left the safety numbers unchanged and did not improve the others: ideal decisions were 90.0% in both agent runs against 92.5% before, and each check costs about 0.7 more model calls. The two agent runs, with identical logic, missed different cases (run 1: T11, T12, T23, T33; run 2: T11, T20, T23, T33), which is the model's run-to-run variance at work: the hosted model is called without a fixed temperature, and misses such as a judge paraphrasing instead of quoting (T12, T23) come and go between runs. In run 2 the agent ran in 12 checks and surfaced clauses the first retrieval had not found in 6; in the four out-of-scope questions (lounge access, meals, sports equipment, seat selection) nothing it found survived the quote and rule checks, so they escalated, as labelled. On this corpus the first retrieval already finds the right clause version for every dev case (see the text-search decision in architecture.md), so there is little left for the agent to find; it is built for policy libraries large enough for retrieval to miss.

Categories: supported 8, contradicted numbers 6, contradicted eligibility 6, date boundaries (day before and day of a version change) 5, not covered 5, relative and implied counts against limits 4, multi-claim 3, prompt injection 3. Per-category numbers and every miss are in the [report](eval_results.md).

Ollama ran on the MacBook Air (M-series, 16 GB) while Db2 ran under Rosetta on the same machine. The Mac went to sleep for about 50 minutes partway through; the run's clock is monotonic and does not count sleep, and no call timed out.

What went wrong, from the recorded runs (left unfixed so the numbers stay honest):

- **OpenRouter T33 (false block, the three runs up to `397c920`):** the extractor turned the customer's own situation ("the delay was within our control") into a policy claim. No clause covers it, so a correct answer was escalated. It passed at `4e6687c` and `512ee74`, now that extraction keeps such conditions in the claim and the judge sees the question.
- **OpenRouter T31 and T36 (escalated instead of corrected, first run):** the rewrite was right, but in the re-check the judge paraphrased its quote, the verbatim-quote rule downgraded that claim to NOT_COVERED, and the correction was held back.
- **Ollama T20 (the false allow):** the draft says a mother-in-law counts as immediate family; the policy's list does not include in-laws. The local judge quoted the real list sentence ("Immediate family means a spouse or common-law partner, parent, ...") and reasoned that "parent" includes a mother-in-law. The quote was genuine, so the verbatim rule could not catch it, and the rule check did not read `eligible_relations`, the clause's list of who counts, until the list check was added at `0be4f60`. This is the limit of a 7B judge on a semantic question, and the reason the default is a hosted model.
- **Ollama T33, T38, T40 (false blocks):** the judge marked correct claims (a 1-year claim window, a family of four on one bereavement booking, one pet per passenger) as contradicted or not covered, so good answers were rewritten or escalated.
- **Ollama T18, T31, T39 (escalated instead of corrected):** the rewrite's re-check did not come back clean, so the answer went to a specialist instead. Safe, but slower for the customer.

**Ollama after the premise checks (7 Nov, `a4cb55f`, run at `14586b2`; the column before it is `da7804d`).** The local model released no wrong draft in either run (the first Ollama run released T20), but stopped 5 of 14 correct drafts against 3 (four held for a specialist, and T40 rewritten), and its ideal decisions fell from 82.5% to 67.5%. At `a4cb55f`, 8 of its 13 misses are corrections whose re-check did not come back clean, so the answer went to a specialist instead of out, and three correct drafts were held because a detail reached no extracted claim. The deterministic rule check earned its place: on T11, T28 and T30 (T28 and T30 also at `da7804d`) the local judge called a wrong claim SUPPORTED against an unrelated clause, the rule check found the mismatch in `RULE_JSON` and overruled it, and all three drafts were held instead of released. The number check added with the premise checks did not fire. The small model errs further on the safe side than the hosted one, which stays the default.

**About the Ollama numbers.** The first Ollama run of the test split was stopped after about 4 cases: the local model looped inside the quote field until the output cap, so every answer failed closed. Two fixes followed, diagnosed and checked on dev cases only: the decoding grammar now bounds every free-text field, and the judge may only quote a real sentence of a retrieved clause (details in [architecture.md](../architecture.md#design-decisions)). The test cases and the prompts were not changed; the hosted path was not changed. The first complete Ollama run is the first Ollama column above (`4b103fd`); the latest is the last (`a4cb55f`).

On the dev split, OpenRouter scored 0% false allow, 0% false block and 95% ideal decisions.

**After the rule-checker change for the bank (`6d928b7`),** the frozen airline split was run again on OpenRouter: 0 of 26 false allows, 1 of 14 false blocks (T33 again), 97.5% safe, 95.0% ideal, citation accuracy 100%, p50 4.8 s, 4.4 model calls per answer. The change: an amount that matches a rule parameter in one unit (a "12-month period" matching 12 months) is no longer also counted as a wrong number of days.

</details>

## Evaluation: the bank fee schedule (second domain)

`python -m asof.eval --split bank-test` runs 26 new cases against Fernhollow Bank (10 correct drafts, 16 wrong for their date). They were committed and their SHA-256 pinned in `6d928b7`, before the first run; the 12-case `bank-dev` split is the one used while building. Same model, check and settings as the airline.

| Metric | OpenRouter `gemini-3.1-flash-lite`, first run of the frozen bank split (`6d928b7`) |
|---|---|
| **False-allow rate** | **0.0%** (0 of 16) |
| False-block rate | 0.0% (0 of 10) |
| Safe decisions | 100% |
| Ideal decisions | 92.3% |
| Citation accuracy | 95.8% |
| Rule overrides | 2 |
| Latency per answer, p50 / p90 | 4.9 s / 5.6 s |
| Whole split | 30 s (4 workers) |

The two misses were both escalations instead of corrections. **BT10:** the judge called "a domestic wire costs $45" contradicted, but its citation did not survive the checks and the claim fell back to not covered. **BT26** is a finding about the data, not the model: clause MTF-003 says paper statements cost $2 and electronic statements are free, but its rule parameters only held the $2, so the rule check read "electronic statements are free" as $0 against $2 and overruled a correct judge (both of the run's rule overrides). The answer was held back, never released wrong. The parameter is now in the corpus with a test, and any later run of this split will be labelled as made after a fix that the frozen run found, not a blind one. On `bank-dev`, the same configuration scored 12 of 12 safe and 11 of 12 ideal.

---
