# Data flow in full

Each flow through AsOf step by step. The sequence diagram of a check and the short version of each flow are in [architecture.md](../architecture.md#data-flow). Back to [architecture.md](../architecture.md).

## Checking an answer

1. **Input.** The caller supplies the question, the draft and the customer's date. The date is never inferred by a model.
2. **Redaction.** Emails, phone numbers, card numbers, booking references and person names are masked. Only redacted text reaches the LLM provider and the ledger.
3. **Extraction.** One LLM call returns at most 8 atomic claims with area and type. More than 8 escalates. If it returns none, each sentence of the draft that names something a policy decides (a fee, a refund, eligibility, a deadline) becomes a claim of its own, judged as written; a draft with no such sentence ("You're welcome, have a good trip!") has no policy claims.
4. **Retrieval.** Each claim is embedded locally and sent to Db2 as one parameterised query: clause versions in force on the date, ranked by cosine distance, top 4.
5. **Judgement.** One LLM call judges every claim against the deduplicated clauses, with the customer's (redacted) question as data, quotes the deciding clause text verbatim, and reports for each claim whether it assumes a situation the question states differently.
6. **Checks in code.** A verdict whose clause was not retrieved becomes NOT_COVERED, and so does a SUPPORTED verdict whose quote is not in the clause. A CONTRADICTED verdict with a short exact quote is grounded by the clause sentence holding it, or by a rule-check mismatch. A SUPPORTED verdict with a situation conflict becomes CONTRADICTED. The rule check then compares numbers, limits, delay tiers and permissions with `RULE_JSON`, and a delay the claim states for the customer with the one in the question. A mismatch forces CONTRADICTED, and can move the citation to the delay tier that actually applies.
7. **Decision.**
   - All claims supported (or no policy claims, and no policy sentence to judge): PASS, with policy references appended.
   - Any claim contradicted: rewrite from the cited clauses, then a full re-check. Released as CORRECTED only if every claim in the rewrite is supported, otherwise ESCALATED.
   - Uncovered claims with nothing contradicted: ESCALATED.
   - Any error: ESCALATED.
8. **Record.** `APPEND_LEDGER` writes the decision and both checks' citations in one transaction. If it fails, the answer is withheld (HTTP 503).

## Changing policy and finding what it affects

The editor submits a new clause version for a period. `APPLY_POLICY_CHANGE` validates the period and label, then runs `UPDATE ... FOR PORTION OF BUSINESS_TIME`: Db2 splits the existing version at the period boundaries, and system versioning moves the replaced row to `POLICY_CLAUSE_HIST`. The same transaction flags help-centre answers whose dates overlap the change. `CHANGE_IMPACT` then returns every released answer that cited the clause, marked STALE (its customer date now falls under a different version) or HISTORICALLY_VALID, plus every help-centre answer, marked NEEDS_REVIEW (with the date it went wrong) or STILL_VALID.

**Preview before publishing.** `POST /api/policy/preview` (the "Preview impact" button) runs the same `APPLY_POLICY_CHANGE` and `CHANGE_IMPACT` as the editor inside one transaction and then rolls it back. The editor sees exactly what Db2 would split, flag and report as stale, computed by the same procedures on the changed data, and afterwards there is no new version, no history row and no flagged help-centre answer (`test_a_preview_reports_the_real_impact_and_leaves_nothing_behind` compares a preview with the real change that follows it).

## Taking in a policy document

The editor uploads a PDF. pypdf reads it page by page; one model call proposes clause versions; code checks each against the document (verbatim text, quoted date, rule values in the text) and blocks any that fails. `ADD_POLICY_DRAFT` stores the file and Db2's hash of it, and `ADD_POLICY_DRAFT_ITEM` each proposal with its checks; nothing is in force. The editor reviews each item against the version in force on its date, can preview the approval (applied and measured by `CHANGE_IMPACT` in a transaction that is rolled back), and approves the items to accept: `DECIDE_POLICY_DRAFT` then `APPLY_DRAFT_ITEM` per item, which calls `APPLY_POLICY_CHANGE` for a changed clause, all in one transaction.

## Answering a held decision

The specialist opens a held decision in the inbox: the question, the draft, each claim with the clause version it was checked against, and the clauses in force on the customer's date nearest the question. The reply runs through the check graph once with `record=False`: no rewrite, nothing written; if extraction finds no claim in a reply that talks policy, its policy sentences are judged as written. If it may be sent (every claim supported, no claims, or uncovered claims with the specialist's note), `RESOLVE_ESCALATION` locks the chain, re-validates everything from the verdicts, appends the `REVIEWED` row and writes `ESCALATION_REVIEW`, in one transaction; the chain-head anchor follows.

## A correction notice

After a policy change, the notice agent takes each `STALE` answer from `CHANGE_IMPACT`, looks up related clauses, rewrites the answer from the clause now in force for the customer's date, and runs the full check on that date (recorded, channel `email`). `ADD_NOTICE` stores the notice after its cross-checks; a specialist's approval (`DECIDE_NOTICE`) marks it `SENT`.

## Routing

With `doc_id` `auto`, the router embeds the question and draft, and one Db2 statement returns each document's nearest three clauses in force on the date. A lead of 0.30 or more (with the other document's best clause farther than 0.45) routes; nothing nearer than 0.65 in either document, or a lead under 0.12, holds the decision for a person (`Gate.hold`, reason `ROUTE_UNCERTAIN`); in between, the agent may confirm the leader if it is on, and otherwise a person decides. The route goes into the hashed verdicts either way.

## Replaying a decision

For each clause a decision cited, three queries:

- the exact row it used, matched by `CLAUSE_ID`, `BUS_START` and `SYS_START` across current and history rows
- what Db2 held for that customer date when the answer was given (`FOR SYSTEM_TIME AS OF created_at FOR BUSINESS_TIME AS OF as_of_date`)
- what applies today for that date (`FOR BUSINESS_TIME AS OF as_of_date`)
