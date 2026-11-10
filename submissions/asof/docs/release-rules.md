# Release rules: Db2 refuses a release the policy does not back

The Python check decides PASS, CORRECTED or ESCALATED. Until now Db2 stored whatever the check decided. With [08_release_rules.sql](../src/asof/sql/08_release_rules.sql), Db2 itself refuses to record an answer as released unless the policy in force backs every claim the customer is given. The check still makes the decision; Db2 makes sure a wrong one cannot be recorded as a release.

## What Db2 enforces

A `BEFORE INSERT` trigger on `ANSWER_LEDGER`, `ANSWER_LEDGER_RELEASE_RULES`, runs for every `PASS` and `CORRECTED` row, whoever inserts it: `APPEND_LEDGER` as the runtime user, or the owner writing straight into the table. It reads the claims from `VERDICTS_JSON`, the document that is hashed into the chain, through `CLAIMS_FROM_JSON` (`JSON_TABLE`), and joins each released claim to `POLICY_CLAUSE FOR BUSINESS_TIME AS OF` the row's `AS_OF_DATE`, matching the clause ID, version label and version start in the row's policy document. Every released claim must:

- be `SUPPORTED` and name a clause,
- cite a clause version that was **in force** on the customer's date, and
- carry a **quote** of at least 12 characters that is in that version's text.

| SQLSTATE | Db2 refuses because |
|---|---|
| `75080` | a released claim is not `SUPPORTED`, or names no clause |
| `75081` | a released claim cites a version not in force on the customer's date (a wrong label, a period that ended, a clause of another document) |
| `75082` | a released claim's quote is missing, shorter than 12 characters, or not in the cited version's text |
| `75083` | the claims do not have the shape the decision needs: a PASS carries only the draft's check, a CORRECTED answer must carry the re-check of its rewrite, and every array entry must be a claim Db2 can read |
| `75003` | more than 16 claim entries (8 per check), as `APPEND_LEDGER_ROW` already refuses |

`WITH RS` keeps the clause rows the trigger read share-locked until the append commits, so a policy change cannot replace the version between the check and the commit: `APPLY_POLICY_CHANGE` waits for the append instead. `ESCALATED` rows send the holding reply, so nothing in them needs backing. `REVIEWED` rows (a specialist's reply) are written only by `RESOLVE_ESCALATION`, which has its own rules (75055 to 75058) and allows a reply on the specialist's documented judgment.

### CORRECTED answers get the same rule

A CORRECTED answer is a release too: the customer receives the rewrite, and the rewrite was claim-checked in a second pass. So the rule applies to the claims of that re-check (`pass` 2), the only claims the customer sees. The draft's claims (`pass` 1) include the contradiction that triggered the rewrite and are deliberately not checked: they were never sent. This is the same split `CHANGE_IMPACT` and `ADD_NOTICE` already use to decide which claims a released answer relied on.

### The quote, compared the way the gate compares it

`QUOTE_NORM` repeats the gate's normalisation (`gate.normalise`) in SQL: curly quotes and the en dash made plain, whitespace runs collapsed, surrounding quote marks and trailing punctuation dropped, lower case. Two steps of the Python version are missing: Db2 12.1 LUW has no `NORMALIZE_STRING`, so there is no NFKC folding, and HTML entities are not unescaped. The shipped clause texts are plain ASCII with no entities, so nothing differs for them. Where a clause did use such characters, Db2 would refuse a quote the gate accepted, and the answer would be held: the safe direction.

## What the gate does when Db2 refuses

The gate fails closed ([gate.py](../src/asof/gate.py), `Gate._record`). A refusal with one of the release SQLSTATEs turns the decision into `ESCALATED` with reason `RELEASE_REFUSED` and the holding reply, and that held decision is appended to the ledger with what Db2 said in `verdicts.release_refused` (the decision the check wanted, its reason, the SQLSTATE). The claims and the rewrite stay in the verdicts as evidence. The customer gets the holding reply and never the text Db2 refused, and the specialist inbox picks the hold up like any other. If recording the hold fails too, nothing is released (`LEDGER_UNAVAILABLE`, HTTP 503), as before. Any other database error is not mistaken for a refusal.

The race this closes in practice: the check retrieves the version in force, and before its decision is recorded an editor commits a change that replaces that version for the customer's date. `test_a_policy_change_between_the_check_and_the_record_is_held_not_released` runs exactly that against Db2: the PASS is refused with 75081 and recorded as a hold.

### One path the gate released that Db2 now holds

When the deterministic rule check finds that a claim's situation belongs to another tier of a tiered clause (the delay compensation tiers, for example) and the claim's numbers match that other clause, the gate moves the citation to it and drops the judge's quote, since the quote came from the first clause (`Gate._settle`). The claim stays `SUPPORTED` with no quote, so Db2 refuses it (75082) and the answer is held. That is the documented rule (a supported claim needs a verbatim quote from the clause it cites) applied to the one path that skipped it. The built-in replay scenarios do not take this path (below); a live eval run would show how often it happens.

## No decision changed in replay

Replay mode ([replay.py](../src/asof/replay.py)) replaces only the model: every built-in scenario (the playground checks, the change-impact presets and the specialist replies in `ui/scenarios.json`) runs through live retrieval, the rule check, the release rules and the ledger. `tests/test_db2_replay.py` asserts that each one reaches the decision it reached against the live model when it was recorded. With the release rules installed, all of them still do (8 of 8 tests passed on 10 Nov 2026, stock Db2 12.1.5 image): the 17 playground checks (6 PASS, 7 CORRECTED, 4 ESCALATED, so 13 releases went through the trigger), the 4 help-centre fixes the change-impact agent drafts for the presets (all PASS), and the 2 specialist replies.

The frozen eval splits (`src/asof/eval/*_test*.jsonl`) are not covered by the recording: it holds only the built-in scenarios, and `python -m asof.eval` refuses replay mode on purpose, since an eval measures a live model. Their decisions under the release rules need a live re-run.

## PREVIEW_POLICY_CHANGE: Db2 undoes the preview itself

`POST /api/policy/preview` used to run `APPLY_POLICY_CHANGE` and `CHANGE_IMPACT` in one transaction that Python then rolled back, so the guarantee depended on the caller's connection (it refused an autocommit connection for that reason). `PREVIEW_POLICY_CHANGE` moves the guarantee into Db2:

1. `SAVEPOINT`, then `CALL APPLY_POLICY_CHANGE` with the same arguments (so the same checks and SQLSTATEs, 75010 to 75014).
2. `CALL CHANGE_IMPACT`, its result set read through `ASSOCIATE RESULT SET LOCATOR` and `ALLOCATE CURSOR` into an array of a row type (`IMPACT_ROW`, `IMPACT_ROWS`), which a rollback does not touch.
3. `ROLLBACK TO SAVEPOINT`: the new version, the split rows, the history rows and the help-centre flags are gone.
4. The counts as OUT values and, as the result set, `UNNEST` of the array in `CHANGE_IMPACT`'s order.

On any error it rolls back to the savepoint and re-raises the error unchanged. `policy.preview_change` calls it (granted to the policy editor only) and still rolls back afterwards to release locks. The API route, its response and the public demo, where previews are allowed without an editor token, behave as before; an autocommit connection is now safe too. The tests compare a full snapshot before and after a preview: every row `POLICY_CLAUSE` ever held with its system-time period (`FOR SYSTEM_TIME FROM ... TO ...`), the history table, the help-centre answers, the ledger, its citations, the chain head, suggestions and notices. They also check that the preview's rows equal, column for column, what `CHANGE_IMPACT` returns after the real change.

The loader learned one new kind of statement for this, `-- type:`, because `CREATE TYPE` has no `OR REPLACE`; a schema drop also drops types, and skips the constructor functions Db2 generates for them (`ORIGIN = 'S'`), which go with their type.

## Db2 limits found on the way

| Tried | Result |
|---|---|
| `JSON_TABLE(?, 'strict $.claims[*]' COLUMNS (...) ERROR ON ERROR)` | SQL0104N (42601): only `'strict $'` is accepted as the row path, so `CLAIMS_FROM_JSON` reads each array position with a literal index, 16 branches in a `UNION ALL` |
| `JSON_VALUE(?, '$.claims.size()' RETURNING INTEGER)` (also `lax`, `[last]`, `.length()`) | NULL, no error: JSON path item methods are not evaluated. The trigger counts entries with 16 `JSON_EXISTS` tests instead, so an entry `CLAIMS_FROM_JSON` cannot read (no `claim_no`) is refused, not skipped |
| `NORMALIZE_STRING(?, NFKC)` | SQL0206N (42703) with the keyword, SQL0440N (42884) with a string: not in Db2 12.1 LUW, so the quote rule has no NFKC step |
| `TRANSLATE(?, '''''""-', U&'\2018\2019\201C\201D\2013')` | SQL0176N (42815): multi-byte characters in the translation strings are refused; `QUOTE_NORM` uses `REPLACE` for each character |

What did work, first time: a compiled `BEFORE INSERT` trigger that is `SECURED` (the ledger has column masks), reads a masked column into `JSON_TABLE`, joins a bitemporal table `FOR BUSINESS_TIME AS OF` a transition variable, and reads `WITH RS`; and `ROLLBACK TO SAVEPOINT` inside a procedure that returns a result set built after the rollback.
