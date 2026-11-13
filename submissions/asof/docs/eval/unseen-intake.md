# Onboarding SPR through Policy intake

SPR (Suryapath Railways) is a fictional railway's ticket cancellation and refund policy, written by another AI (OpenAI's GPT) together with 40 test cases meant to make AsOf release a wrong answer ([PROVENANCE.md](../../src/asof/eval/unseen/PROVENANCE.md)). This page is how SPR's policy got into Db2, what intake got right and wrong, and every decision the editor made. The results of the 40 cases are in [unseen-results.md](unseen-results.md).

Everything here was done from the three policy texts alone. The test cases were not read until the runner and its metrics were committed, and nothing below was changed because of them.

## What a new domain needed

| Piece | What was added | Why |
|---|---|---|
| Policy document | `POLICY_DOC` row `SPR-REFUNDS` | The parent of every clause and ledger row. |
| PDFs | `src/asof/eval/unseen/pdf/spr_policy_v{1,2,3}.pdf`, made by `pdfs.py` | Intake takes PDFs. Courier, WinAnsi text, no timestamps. [tests/test_unseen_pdfs.py](../../tests/test_unseen_pdfs.py) proves `intake.read_pdf` gets back the .txt file's exact word sequence (1,424, 1,460 and 1,519 words), and that the raw text layer keeps GPT's em dashes and curly apostrophe. |
| Domain | `domains.RAIL` | Checked like the airline and the bank, but kept out of the API's `DocId` and the router's two-document vote, so the existing domains behave exactly as before. |
| Check prompts | `prompts.GENERIC_*_SYSTEM`, version `generic-2026-11-10.1` | The airline prompts with only the role named neutrally ("an airline's customer-service assistant" becomes "a company's customer-service assistant"; four phrases in all, `prompts.NEUTRAL_WORDING`). Every rule and example is the airline's, word for word. |
| Claim areas | `schemas.RailArea`: cancellation, refund, delay, other | Four of the airline's areas, so Db2's area constraint (`CK_CLAUSE_AREA`) is unchanged and no existing database needs a migration. |
| Intake cap | 16 proposals instead of 12 | SPR has 14 numbered sections; 12 proposals can never hold it. |
| Intake prompt | `prompts.SPR_INTAKE_SYSTEM` | The shipped intake prompt plus four rules, below. |
| Rule checker | reads "48 h" and "7 calendar days" | Two forms of a duration that SPR's text uses and the checker did not read, so intake blocked every clause stating them. Below. |

### The four SPR intake rules

Written from the policy text, after the uploads described under "Trials" and before any case was read:

1. The document numbers its sections P-01 to P-09 and E1 to E5: one proposal for every numbered section, including the sections that define terms, say which version applies, list exclusions and say an exception is not in force.
2. A section's text includes its table.
3. `effective_to` is null for every section. Loading the next version is what ends this one: `APPLY_DRAFT_ITEM` makes a changed clause a new version through `APPLY_POLICY_CHANGE`, which splits the period of the version in force (`FOR PORTION OF BUSINESS_TIME`).
4. Amounts are in Indian rupees: an amount's key ends `_inr`, never `_usd`.

### The rule-checker change

`rules.extract_quantities` now reads "48 h" (digits, then `h`) as 48 hours, and "7 calendar days" as 7 days. Before, intake's rule-value check failed every parameter SPR states in those forms ("min_t_hours = 48 is not stated in the clause text"), and Db2 refuses a blocked item, so E1 (operator-cancelled trains: "no later than 7 calendar days") and the fare table P-03 ("T >= 48 h") could not be loaded at all: 5 uploads of v1 and 5 of v2 in trial E never loaded either. The change was made before any case was read. No airline or bank clause, eval case, demo scenario or intake document contains either form (checked with grep), so it cannot change any recorded result on those domains. Unit tests: [tests/test_rules_units.py](../../tests/test_rules_units.py).

The checker still reads no rupee amounts and no minutes: SPR's `_inr` and `_minutes` parameters are stored and shown, but the deterministic check never compares a claim with them. On SPR it compares hours, days and percentages only.

## The editor's rule

Every upload was decided by one written rule (`accuracy.review`), the same for every upload, and a rebuild refuses a recorded decision that differs from what the rule gives:

- Accept an item when intake's checks let it through, its text is one whole section of the document, and it is filed under the right clause: a change must be a new version of the clause that holds that section, and a new clause must be for a section no clause holds yet. E5 in v1 and v2 opens with "NOT IN FORCE -", which reads as its heading, and a proposal may leave those words out.
- Reject everything else, with the reason. A draft with nothing to accept is rejected.
- Upload a version again while one of its sections is not in force for that version, at most 5 uploads per version.

No clause needed a correction through `APPLY_POLICY_CHANGE`: every accepted item's text is the document's, and intake's checks had already refused any parameter whose value the text does not state. Parameters whose names read oddly but check nothing (no unit the checker reads) were left as proposed; they are listed in the table below.

## Trials before the final onboarding

Each trial's records are in `src/asof/eval/unseen/onboarding/trial-*/` (every model proposal, with the SHA-256 of the messages sent, and the scores).

| Trial | Prompt | Uploads | What happened |
|---|---|---|---|
| A, `trial-shipped-prompt` | shipped intake prompt, cap 16 | v1 twice | 8 of 14 sections proposed, all word for word, all ending 2026-04-30 (exclusive, so 30 April had no clause). P-01, P-02, P-03 (the fare table), P-08, E5 and P-09 never proposed; E1 blocked ("7 calendar days"). The second upload added no section and cut 4 sections short. |
| B, `trial-sections-prompt` | + rules 1 and 2 | v1 once | 14 of 14 proposed, 13 whole. 6 blocked: rupee amounts named `_usd` (3), P-01's parameters, P-03's `min_t_hours`, E1. All still ending 2026-04-30. |
| C, `trial-exclusive-ends` | + "END: 2026-04-30 means effective_to 2026-05-01", + rule 4 | v1 twice, v2 once | v1: 13 of 14 accepted (E1 blocked). v2: 14 proposed, but no change could be applied: with v1 ended on 1 May, `APPLY_POLICY_CHANGE` had no version in force to replace (SQLSTATE 75013, seen in a preview). Hence rule 3. |
| D, `trial-open-ends-1` | final prompt | v1 three times | Upload 1: 11 accepted; P-03 blocked (`min_t_hours` given twice, 48 not read as hours), P-07 not word for word, E1 blocked. Uploads 2 and 3 both filed P-03's text as a new version of CAN-002, the Premium QuickBook clause, with that clause's title: intake's checks pass it, and accepting it would have replaced the PQ rule with the fare table. Rejected; the editor's rule was then written down and the onboarding restarted. |
| (not kept) | final prompt | v1 once | The first upload after that restart: 4 accepted, 10 blocked for parameters with no single value. Its record was deleted by mistake before it was kept; the next trial's first upload got the same decision. |
| E, `trial-open-ends-2` | final prompt, editor's rule | v1 five times, v2 five times | 12 of 14 v1 sections and 12 of 14 v2 sections loaded; P-03 and E1 never did (hours written "48 h" and "7 calendar days", invalid key names such as `max_charge_1A_inr`, and P-03 filed under the waitlist clause twice). Hence the rule-checker change. |

Two of these are worth carrying forward as findings about AsOf, not about SPR:

- **A missing section gets filed under the wrong clause.** When a section is not yet in the policy, a re-upload tends to propose it as a new version of a neighbouring clause (P-03 as P-05 or P-06). Intake's checks only test the text against the document, so nothing but the editor stops it.
- **Intake cannot load a version after a gap.** If a clause's version has an end date, the next version of that clause cannot be applied (75013); only open-ended versions can be replaced. The console cannot edit a proposal's dates either, so an editor who sees intake's "end should be 2026-05-01" warning can only reject the item.

## Final onboarding

Eight uploads: v1 twice, v2 once, v3 five times. At the end every one of the 14 sections is in force for every version, as 14 clauses, and a booking date finds the version GPT's P-01 says governs it (tests/test_unseen_onboarding.py rebuilds SPR in a throwaway schema and checks the booking fee on 2026-04-30, 2026-05-01, 2026-08-31 and 2026-09-01).

| | v1 | v2 | v3 |
|---|---|---|---|
| Sections that changed from the version before | 14 (first) | 10 | 13 |
| Proposed in the first upload | 14 | 14 | 15 (one extra: a cut-short piece of P-02 filed under the E5 clause) |
| Accepted from the first upload, as proposed | 12 | 10 (all 10 changed; 4 restated word for word) | 12 |
| Blocked by intake's checks in the first upload | 2: P-03 (`min_t_hours` and `max_t_hours` given several times), P-07 (not word for word) | 0 | 0 |
| Accepted from later uploads | P-03, P-07 (upload 2) | | none |
| Never proposed correctly | | | E5, five times out of five: its new text (an evacuation-order exception) was always proposed as a new clause, while OTH-005 holds E5's v1 and v2 text ("No separate evacuation exception exists") |
| Corrected by the editor (`APPLY_POLICY_CHANGE`) | | | E5 (OTH-005 from 2026-09-01) and P-05's permission (CAN-002 from 2026-09-01) |

Against the source text:

- **Texts**: every accepted text is one whole section, word for word (E5 in v1 without its opening words "NOT IN FORCE -"). Two proposals in eight uploads were not word for word (intake's check blocked both). In every v3 upload but one, an extra proposal filed a piece of P-02 under the E5 clause (cut short, or spanning sections); the editor's rule rejected each. No invented text reached Db2.
- **Dates**: none wrong. Every proposal started on its version's date; rule 3 left every end open, and Db2 split each period when the next version was applied (`FOR PORTION OF BUSINESS_TIME`).
- **Numbers**: no accepted parameter states a value the text does not (intake's check refuses those). The parameters hold 18 to 23 of the 23 to 28 values each version states with a unit; the fare table's thresholds (48 h, 12 h, 4 h, and their v2 and v3 values) sit in key names rather than in values. Rupee amounts and minutes are stored (`_inr`, `_minutes`) but never compared with a claim: the rule checker reads neither.
- **Needing correction**: two. E5 in v3 never arrived as a change of its clause, and v3's P-05 came with `voluntary_refund_pq_allowed = false` where v3 refunds a confirmed PQ passenger less 35% at least 24 hours out. Both corrections are in `decisions.json` with their reasons, and in the table below.
- **Left as proposed**: v1's P-03 parameter `refund_pct = 50` names the table's 50% charge a refund (for v1 the two are both 50%, so the number is right), and v3's P-02 has `min_t_hours = ["At least"]`, a list the checker ignores. Neither is read by any check.
- **Labels**: a clause gets a new version label only when its text changes, so labels are per clause, not per policy version: P-02 and P-08 carry v1 to 2026-09-01, E5's v3 text is OTH-005 v2, and the corrected P-05 row is CAN-002 v4. The results name each cited row's policy version from its start date.
- **Titles**: a clause's title is set when it is created. E5's clause is titled "Not in Force" in every version, including v3's evacuation exception, and `APPLY_POLICY_CHANGE` cannot change it. The judge sees that title next to the v3 text.

The records in `src/asof/eval/unseen/onboarding/` (`upload_NN_vN.json`, `decisions.json`) rebuild SPR in any schema without calling a model:

```bash
python -m asof.eval.unseen.onboard                   # fresh schema ASOF_UNSEEN (dropped and rebuilt)
python -m asof.eval.unseen.onboard --schema ASOF     # added to an existing AsOf schema; refuses if SPR is there
```

A rebuild replays each recorded proposal only if intake would send the model exactly the recorded messages (same PDF, same prompt, same clauses already in force), re-derives each decision from the editor's rule and refuses one that differs, stores each draft with `ADD_POLICY_DRAFT` and `ADD_POLICY_DRAFT_ITEM`, and decides it with `DECIDE_POLICY_DRAFT` and `APPLY_DRAFT_ITEM`, then applies the recorded corrections with `APPLY_POLICY_CHANGE`: the console's procedures, on the same Db2 users (`asofapp` reads, `asofedit` writes). Recording a new onboarding: move the current records into a `trial-*` folder, then `python -m asof.eval.unseen.onboard --drive` (needs a model key).

Accuracy per upload: a section is "whole" when the proposal's text is the section's text (normalised as intake normalises), "cut short" when it is part of it, "not in the document" when intake's verbatim check fails. "Values stated / captured": numbers the section states with a unit (INR, %, h, hours, minutes, calendar days, passengers), and how many of them the proposal's parameters hold.

<!-- generated:uploads -->
| Upload | Version | Sections missing before | Proposed | Whole sections | Cut short | Not in the document | Blocked by checks | Wrong or second clause | Accepted | Dates wrong | Values stated / captured |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | v1 | P-01, P-02, P-03, P-04, P-05, P-06, P-07, P-08, E1, E2, E3, E4, E5, P-09 | 14 | 12 | 1 | 1 | 2 | 0 | 12 | 0 | 23 / 18 |
| 2 | v1 | P-03, P-07 | 14 | 13 | 1 | 0 | 0 | 0 | 2 | 0 | 23 / 20 |
| 3 | v2 | P-01, P-03, P-04, P-05, P-06, P-07, E1, E2, E3, E4 | 14 | 13 | 1 | 0 | 0 | 0 | 10 | 0 | 26 / 21 |
| 4 | v3 | P-01, P-02, P-03, P-04, P-05, P-06, P-07, P-08, E1, E2, E3, E4, E5 | 15 | 13 | 1 | 0 | 0 | 1 | 12 | 0 | 28 / 23 |
| 5 | v3 | E5 | 15 | 13 | 1 | 1 | 1 | 1 | 0 | 0 | 28 / 23 |
| 6 | v3 | E5 | 15 | 13 | 1 | 0 | 0 | 1 | 0 | 0 | 28 / 22 |
| 7 | v3 | E5 | 15 | 13 | 1 | 0 | 0 | 1 | 0 | 0 | 28 / 23 |
| 8 | v3 | E5 | 14 | 13 | 1 | 0 | 0 | 1 | 0 | 0 | 28 / 23 |

The editor's reason for every item, by upload:

- Upload 1 (v1), draft 1:
  - #1 OTH-001: accepted: P-01
  - #2 OTH-002: accepted: P-02
  - #3 CAN-001: blocked by intake's checks: rule keys: min_t_hours is given twice; rule keys: max_t_hours is given twice; rule keys: min_t_hours is given twice; rule keys: max_t_hours is given twice; rule keys: min_t_hours is given twice
  - #4 OTH-003: accepted: P-04
  - #5 CAN-002: accepted: P-05
  - #6 CAN-003: accepted: P-06
  - #7 CAN-004: blocked by intake's checks: verbatim text: this text is not in the document word for word
  - #8 OTH-004: accepted: P-08
  - #9 REF-001: accepted: E1
  - #10 REF-002: accepted: E2
  - #11 REF-003: accepted: E3
  - #12 REF-004: accepted: E4
  - #13 OTH-005: accepted: E5 (without its opening words 'NOT IN FORCE -')
  - #14 OTH-006: accepted: P-09
- Upload 2 (v1), draft 2:
  - #1 OTH-001: restates OTH-001 word for word; nothing to apply
  - #2 OTH-002: restates OTH-002 word for word; nothing to apply
  - #3 CAN-004: accepted: P-03
  - #4 OTH-003: restates OTH-003 word for word; nothing to apply
  - #5 CAN-002: restates CAN-002 word for word; nothing to apply
  - #6 CAN-003: restates CAN-003 word for word; nothing to apply
  - #7 OTH-007: accepted: P-07
  - #8 OTH-004: restates OTH-004 word for word; nothing to apply
  - #9 REF-001: restates REF-001 word for word; nothing to apply
  - #10 REF-002: restates REF-002 word for word; nothing to apply
  - #11 REF-003: restates REF-003 word for word; nothing to apply
  - #12 REF-004: restates REF-004 word for word; nothing to apply
  - #13 OTH-005: restates OTH-005 word for word; nothing to apply
  - #14 OTH-006: restates OTH-006 word for word; nothing to apply
- Upload 3 (v2), draft 3:
  - #1 OTH-001: accepted: P-01
  - #2 OTH-002: restates OTH-002 word for word; nothing to apply
  - #3 CAN-004: accepted: P-03
  - #4 OTH-003: accepted: P-04
  - #5 CAN-002: accepted: P-05
  - #6 CAN-003: accepted: P-06
  - #7 OTH-007: accepted: P-07
  - #8 OTH-004: restates OTH-004 word for word; nothing to apply
  - #9 REF-001: accepted: E1
  - #10 REF-002: accepted: E2
  - #11 REF-003: accepted: E3
  - #12 REF-004: accepted: E4
  - #13 OTH-005: restates OTH-005 word for word; nothing to apply
  - #14 OTH-006: restates OTH-006 word for word; nothing to apply
- Upload 4 (v3), draft 4:
  - #1 OTH-001: accepted: P-01
  - #2 OTH-002: accepted: P-02
  - #3 CAN-004: accepted: P-03
  - #4 OTH-003: accepted: P-04
  - #5 CAN-002: accepted: P-05
  - #6 CAN-003: accepted: P-06
  - #7 OTH-007: accepted: P-07
  - #8 OTH-004: accepted: P-08
  - #9 REF-001: accepted: E1
  - #10 REF-002: accepted: E2
  - #11 REF-003: accepted: E3
  - #12 REF-004: accepted: E4
  - #13 REF-005: E5 is already in force under another clause
  - #14 OTH-006: restates OTH-006 word for word; nothing to apply
  - #15 OTH-005: cuts P-02 short
- Upload 5 (v3), draft 5:
  - #1 OTH-001: restates OTH-001 word for word; nothing to apply
  - #2 OTH-002: restates OTH-002 word for word; nothing to apply
  - #3 CAN-004: restates CAN-004 word for word; nothing to apply
  - #4 OTH-003: restates OTH-003 word for word; nothing to apply
  - #5 CAN-002: restates CAN-002 word for word; nothing to apply
  - #6 CAN-003: restates CAN-003 word for word; nothing to apply
  - #7 OTH-007: restates OTH-007 word for word; nothing to apply
  - #8 OTH-004: restates OTH-004 word for word; nothing to apply
  - #9 REF-001: restates REF-001 word for word; nothing to apply
  - #10 REF-002: restates REF-002 word for word; nothing to apply
  - #11 REF-003: restates REF-003 word for word; nothing to apply
  - #12 REF-004: restates REF-004 word for word; nothing to apply
  - #13 OTH-008: E5 is already in force under another clause
  - #14 OTH-006: restates OTH-006 word for word; nothing to apply
  - #15 OTH-005: blocked by intake's checks: verbatim text: this text is not in the document word for word
- Upload 6 (v3), draft 6:
  - #1 OTH-001: restates OTH-001 word for word; nothing to apply
  - #2 OTH-002: restates OTH-002 word for word; nothing to apply
  - #3 CAN-004: restates CAN-004 word for word; nothing to apply
  - #4 OTH-003: restates OTH-003 word for word; nothing to apply
  - #5 CAN-002: restates CAN-002 word for word; nothing to apply
  - #6 CAN-003: restates CAN-003 word for word; nothing to apply
  - #7 OTH-007: restates OTH-007 word for word; nothing to apply
  - #8 OTH-004: restates OTH-004 word for word; nothing to apply
  - #9 REF-001: restates REF-001 word for word; nothing to apply
  - #10 REF-002: restates REF-002 word for word; nothing to apply
  - #11 REF-003: restates REF-003 word for word; nothing to apply
  - #12 REF-004: restates REF-004 word for word; nothing to apply
  - #13 REF-005: E5 is already in force under another clause
  - #14 OTH-006: restates OTH-006 word for word; nothing to apply
  - #15 OTH-005: its text is not one section of the document
- Upload 7 (v3), draft 7:
  - #1 OTH-001: restates OTH-001 word for word; nothing to apply
  - #2 OTH-002: restates OTH-002 word for word; nothing to apply
  - #3 CAN-004: restates CAN-004 word for word; nothing to apply
  - #4 OTH-003: restates OTH-003 word for word; nothing to apply
  - #5 CAN-002: restates CAN-002 word for word; nothing to apply
  - #6 CAN-003: restates CAN-003 word for word; nothing to apply
  - #7 OTH-007: restates OTH-007 word for word; nothing to apply
  - #8 OTH-004: restates OTH-004 word for word; nothing to apply
  - #9 REF-001: restates REF-001 word for word; nothing to apply
  - #10 REF-002: restates REF-002 word for word; nothing to apply
  - #11 REF-003: restates REF-003 word for word; nothing to apply
  - #12 REF-004: restates REF-004 word for word; nothing to apply
  - #13 OTH-008: E5 is already in force under another clause
  - #14 OTH-006: restates OTH-006 word for word; nothing to apply
  - #15 OTH-005: its text is not one section of the document
- Upload 8 (v3), draft 8:
  - #1 OTH-001: restates OTH-001 word for word; nothing to apply
  - #2 OTH-002: restates OTH-002 word for word; nothing to apply
  - #3 CAN-004: restates CAN-004 word for word; nothing to apply
  - #4 OTH-003: restates OTH-003 word for word; nothing to apply
  - #5 CAN-002: restates CAN-002 word for word; nothing to apply
  - #6 CAN-003: restates CAN-003 word for word; nothing to apply
  - #7 OTH-007: restates OTH-007 word for word; nothing to apply
  - #8 OTH-004: restates OTH-004 word for word; nothing to apply
  - #9 REF-001: restates REF-001 word for word; nothing to apply
  - #10 REF-002: restates REF-002 word for word; nothing to apply
  - #11 REF-003: restates REF-003 word for word; nothing to apply
  - #12 REF-004: restates REF-004 word for word; nothing to apply
  - #13 OTH-008: E5 is already in force under another clause
  - #14 OTH-006: restates OTH-006 word for word; nothing to apply
  - correction OTH-005 from 2026-09-01: v3 replaces E5 'NOT IN FORCE - No separate evacuation exception exists.' with an evacuation-order exception. All five v3 uploads proposed it as a new clause (rejected: E5 is already held by OTH-005), so without this the v1 text, that no evacuation exception exists, would stay in force for v3 bookings. Applied with APPLY_POLICY_CHANGE from 2026-09-01, open-ended: the section's text word for word and the one parameter intake had proposed for it (max_evacuation_claim_deadline_days = 30, which intake's check passes). The clause keeps its v1 title, 'Not in Force': APPLY_POLICY_CHANGE cannot change a title.
  - correction CAN-002 from 2026-09-01: Upload 4 proposed v3's P-05 with voluntary_refund_pq_allowed = false, but v3 refunds a confirmed PQ passenger less a 35% charge when they cancel at least 24 hours before departure (v2's proposal said true for the same rule). Intake flagged the value as one it could not read, for the editor to confirm. Same text and charge, the permission corrected. The rule checker has no cue for this key, so no check changes; the correction keeps the data right. Db2 gives the new row the label v4, since v3 is taken.
<!-- /generated:uploads -->

## Post-hoc corrections (after the first run)

After the first unseen-domain run, whose misses turned on fare-table band edges, the editor added each version's P-03 fare table and P-05 Premium QuickBook rule to their clauses' `RULE_JSON` as `time_bands` (six `APPLY_POLICY_CHANGE` calls, same text, every earlier parameter kept; `onboarding/posthoc_changes.json`, data in `bands.py` from the policy text). A rebuild applies them after the recorded uploads; `python -m asof.eval.unseen.onboard --first-run-policy` leaves them out. They were made after reading the cases' results, so they are not part of the blind onboarding above. Results: [unseen-results.md](unseen-results.md), "Post-hoc run 2".
