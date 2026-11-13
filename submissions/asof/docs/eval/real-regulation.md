# Real regulation: the US DOT airline refund rules

**A demonstration on real public-domain regulation, not a blind evaluation, and not legal advice.** The questions below were written after reading the rule, to show one thing: the same question about the same draft gets a different answer depending on the date, because the regulation in force on that date says something different.

## What was loaded

The US Department of Transportation's 2024 refund rule (89 FR 32832, 26 Apr 2024) created 14 CFR part 260 and rewrote the refund standard in 14 CFR 259.5(b)(5). The text comes from the official eCFR point-in-time API, as of two dates before the rule and two after it, kept byte for byte with its SHA-256 in [src/asof/eval/real/PROVENANCE.md](../../src/asof/eval/real/PROVENANCE.md).

| AsOf version | In force from | Text loaded | eCFR as of |
|---|---|---|---|
| v1 | 2020-01-01 (the eCFR shows this text from 2016-12-05; AsOf stores no earlier date) | 259.5(b)(5): "where ticket refunds are due, providing prompt refunds ... within 20 days after receiving a complete refund request for cash and check purchases" | 2023-01-03 (and 2024-06-24, the same paragraph) |
| v2 | 2024-06-25 | 259.5(b)(5) as amended: refunds in the original form of payment, no processing fee | 2024-07-01 |
| v3 | 2024-08-12 | the same 259.5(b)(5), plus 260.6, refunds for flights cancelled or significantly delayed or changed (as corrected on 2024-08-12, 89 FR 65537) | 2025-06-02 (259.5(b)(5) is unchanged through the 2026-07-02 amendment to 259.5's other paragraphs) |

It went in the way SPR did ([unseen-intake.md](unseen-intake.md)): text-layer PDFs, Policy intake, and the editor's decisions through the console's procedures (`DECIDE_POLICY_DRAFT`, `APPLY_DRAFT_ITEM`, `APPLY_POLICY_CHANGE`), recorded in [src/asof/eval/real/onboarding/](../../src/asof/eval/real/onboarding/) and replayable with `python -m asof.eval.real.onboard` (its own schema, `ASOF_REAL`; the domain `US-DOT-REFUNDS` is, like SPR, not offered by the API or the router). Four uploads put 7 clauses in force (259.5(b)(5), and 260.6(a)(1), (a)(2), (b), (c), (d) and (e)), with every rejection's reason in `decisions.json`.

What did not go in, and why:

- **Part 260 as first published (2024-06-25 to 2024-08-11).** The 2024-08-12 correction restructured 260.6, and AsOf has no editor procedure that ends a clause a later version drops; loading both texts paragraph by paragraph left 2024-06-25 paragraphs in force after 2024-08-12 (`onboarding/trial-part260-as-published/`). So part 260 is loaded from 2024-08-12. Between 2024-06-25 and 2024-08-11 only 259.5(b)(5) as amended is in force here.
- **260.10, prompt refunds** (260.9 before 2024-08-12). Both v3 uploads filed it as a new version of the 259.5(b)(5) clause; the editor rejected that and uploads each version at most twice. 259.5(b)(5) as amended states the same two rules (original form of payment, no processing fee).
- **260.2, the definitions,** which hold the day counts for a "prompt" refund after the rule. Not fetched, to keep the excerpt to the refund provisions.
- **Compliance dates.** The Federal Register notice gives carriers later compliance dates for some provisions. AsOf uses the CFR's effective dates only.

One editor correction: v2's 259.5(b)(5) came with a parameter saying fee refunds are no longer required, the opposite of the text; it was replaced with `processing_fee_allowed = false` through `APPLY_POLICY_CHANGE` (recorded with its reason).

## The questions

Each question is one full check, as `POST /api/gate` makes it, with as_of_date = the date the refund question arises (the cancellation or the refund request). The draft is the same on both dates. "What the excerpt says" is a plain reading of the loaded text for that date. Run once with `python -m asof.eval.real.run`.

## What the run shows

Ten checks, run once on 11 Nov 2026 (UTC) with OpenRouter `google/gemini-3.1-flash-lite`:

- **In 9 of the 10, AsOf did what the text in force on that date supports.** Before the rule (2023-03-15) it released the one draft the old text states (D2a, 20 days for a cash refund) and held the four whose rights the old text does not state (D1a, D3a, D4a, D5a). After it, it released the voucher and original-form-of-payment drafts (D4b, D5b), corrected the processing-fee draft from 259.5(b)(5) as amended (D3b), and held the 20-day draft, since the loaded text after the rule no longer gives a day count (D2b).
- **One miss: D1b, held although the 2025 text supports it.** The judge marked the automatic-refund claim SUPPORTED against 260.6(a)(2), but its quote was not in the clause word for word, so the verbatim-quote rule made the claim NOT_COVERED and the draft was held (ledger row 2 in `ASOF_REAL`). Safe, but a specialist would have had to answer it.
- **D1a was held for a reason that is a stretch:** the judge read the old 259.5(b)(5) as requiring a refund request and called the automatic-refund claim contradicted; the rewrite then failed its re-check. Holding was the right outcome, since the old text does not state the right.
- Every citation names the clause row in force on the question's date, and the ledger chain verified (OK).

<!-- generated:answers -->
Run 2026-11-11T03:24:05+00:00 at commit `767c892`, openrouter `google/gemini-3.1-flash-lite`, schema `ASOF_REAL`, ledger chain OK.

| Question | Date | Draft says | What the excerpt says on that date | AsOf | Cited (clause, version, in force) |
|---|---|---|---|---|---|
| D1a | 2023-03-15 | Yes. Because the airline cancelled your flight and you rejected the alternative it offered, a full refund of the airfare is due to you automatically. | Not stated: 259.5(b)(5) only says refunds that are due must be prompt; it does not say when a refund is due. | **ESCALATED** (CORRECTION_FAILED) | REF-001 v1 (from 2020-01-01): Refund timelines and scope |
| D1b | 2025-02-10 | Yes. Because the airline cancelled your flight and you rejected the alternative it offered, a full refund of the airfare is due to you automatically. | 260.6(a)(2)(ii): a full refund is due when the consumer rejects the significantly changed flight or the rebooking. | **ESCALATED** (NOT_COVERED) | none |
| D2a | 2023-03-15 | The airline must refund you within 20 days after it receives your complete refund request. | 259.5(b)(5): within 20 days after receiving a complete refund request, for cash and check purchases. | **PASS** (ALL_SUPPORTED) | REF-001 v1 (from 2020-01-01): Refund timelines and scope |
| D2b | 2025-02-10 | The airline must refund you within 20 days after it receives your complete refund request. | Not stated in the excerpt: 259.5(b)(5) as amended says prompt refunds in the original form of payment; the day counts are in 260.2's definitions, which were not loaded. | **ESCALATED** (NOT_COVERED) | none |
| D3a | 2023-03-15 | Yes. The airline may keep a small processing fee from the refund. | Not stated: 259.5(b)(5) says nothing about processing fees. | **ESCALATED** (NOT_COVERED) | none |
| D3b | 2025-02-10 | Yes. The airline may keep a small processing fee from the refund. | 259.5(b)(5) as amended: carriers may not retain a processing fee for issuing refunds that are due. | **CORRECTED** (CORRECTED_FROM_CLAUSES) | REF-001 v3 (from 2024-06-25): Refund timelines and scope |
| D4a | 2023-03-15 | A voucher offered instead of the refund must stay valid for at least five years from the date it is issued. | Not stated: there is no voucher rule before part 260. | **ESCALATED** (NOT_COVERED) | none |
| D4b | 2025-02-10 | A voucher offered instead of the refund must stay valid for at least five years from the date it is issued. | 260.6(c)(2): valid and redeemable for at least five years from issuance. | **PASS** (ALL_SUPPORTED) | REF-006 v1 (from 2024-08-12): Refund alternatives |
| D5a | 2023-03-15 | Not unless you agree. The refund must go back in your original form of payment, unless you accept a different form that is a cash equivalent. | Not stated: 259.5(b)(5) before the rule says nothing about the form of payment. | **ESCALATED** (NOT_COVERED) | none |
| D5b | 2024-07-15 | Not unless you agree. The refund must go back in your original form of payment, unless you accept a different form that is a cash equivalent. | 259.5(b)(5) as amended on 2024-06-25: the original form of payment, unless the consumer agrees to a cash-equivalent payment. | **PASS** (ALL_SUPPORTED) | REF-001 v3 (from 2024-06-25): Refund timelines and scope |

What AsOf sent the customer:

- **D1a** (2023-03-15): Thanks for your patience. A specialist will confirm what our policy says for your dates and get back to you shortly.
- **D1b** (2025-02-10): Thanks for your patience. A specialist will confirm what our policy says for your dates and get back to you shortly.
- **D2a** (2023-03-15): The airline must refund you within 20 days after it receives your complete refund request.
- **D2b** (2025-02-10): Thanks for your patience. A specialist will confirm what our policy says for your dates and get back to you shortly.
- **D3a** (2023-03-15): Thanks for your patience. A specialist will confirm what our policy says for your dates and get back to you shortly.
- **D3b** (2025-02-10): Carriers may not retain a processing fee for issuing refunds that are due.
- **D4a** (2023-03-15): Thanks for your patience. A specialist will confirm what our policy says for your dates and get back to you shortly.
- **D4b** (2025-02-10): A voucher offered instead of the refund must stay valid for at least five years from the date it is issued.
- **D5a** (2023-03-15): Thanks for your patience. A specialist will confirm what our policy says for your dates and get back to you shortly.
- **D5b** (2024-07-15): Not unless you agree. The refund must go back in your original form of payment, unless you accept a different form that is a cash equivalent.
<!-- /generated:answers -->
