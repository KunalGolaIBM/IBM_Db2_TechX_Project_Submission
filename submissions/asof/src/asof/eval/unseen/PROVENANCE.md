# Provenance: the unseen-domain test set (SPR)

These five files are an independent test set for AsOf, written by a different AI (OpenAI's GPT) on 10 Nov 2026. They describe a fictional railway company, "SPR", and its ticket cancellation and refund policy in three dated versions (effective 2026-01-01, 2026-05-01 and 2026-09-01; the booking date decides which version applies), plus 40 test cases.

GPT was asked to make AsOf fail. The prompt it was given, as Jay recorded it (the "..." elisions are his):

> "Write an independent test set for an AI answer-checking system... a FICTIONAL railway company's ticket cancellation and refund policy... three dated versions... 40 test cases... Make it hard. Your goal is to make an answer-checking system release a wrong answer."

## Rules for this set

- The files are byte-for-byte copies of what GPT produced, committed before any AsOf run touched them. Their SHA-256 sums are pinned in [tests/test_unseen_provenance.py](../../../../tests/test_unseen_provenance.py), so any edit fails the build.
- Nothing in AsOf (prompts, rules, retrieval, thresholds) is tuned on these cases. The first run is published as it comes out. Any fix made after it is reported as a separate, post-hoc row and never changes the first-run numbers.
- The policy text reaches Db2 the way any customer's policy would: the three versions are turned into text-layer PDFs without changing a word and loaded through Policy intake, and every clause correction goes through the editor approval path and is recorded.

## Files

| File | What it is | SHA-256 |
|---|---|---|
| `spr_policy_v1.txt` | Policy version 1, effective 2026-01-01 | `29de092dec57d16bc805154098743d063ed51d03f9a6bdbf526925290ef44a3b` |
| `spr_policy_v2.txt` | Policy version 2, effective 2026-05-01 | `787342ac7662d00b6038dce41a831d5e069b71da7bd02c67bc5f35d9a0acb78a` |
| `spr_policy_v3.txt` | Policy version 3, effective 2026-09-01 | `8634bab13d3c483f4497287dee2aac07cac58e2e27db2b717c71413ec6de1512` |
| `spr_policy_all_versions.txt` | All three versions in one file | `fd42aca851df7e2f2709eece4f843220ff60284bc789f397f0b84cfed7b5243b` |
| `spr_40_test_cases.json` | 40 cases: question, customer date, assistant draft, label, reason | `18ede398f1aa11f6de903bdce5ac662d84998c881728ee31485407f688c114f0` |

The text files keep GPT's punctuation, em dashes included; they are test data and are not edited to match this repository's style.

## Added afterwards, by AsOf

Nothing above was changed. Everything else in this folder was written for AsOf after the five files were pinned: `pdf/` holds the three policy versions as text-layer PDFs made by `pdfs.py` (tests/test_unseen_pdfs.py proves that intake's reader gets back every word of each .txt file), `onboarding/` holds the records of loading them through Policy intake, and the Python modules are the onboarding and the runner. See [docs/eval/unseen-intake.md](../../../../docs/eval/unseen-intake.md) and [docs/eval/unseen-results.md](../../../../docs/eval/unseen-results.md).
