# Indian Railways refunds (public demo domain)

**Summary of public rules, not an official IRCTC or Indian Railways statement.** A third public domain for the demo, `INDIAN-RAIL-REFUNDS`, next to Aurelia Air and Fernhollow Bank: cancellation charges and refunds for confirmed train tickets, in AsOf's own words, in two dated versions. It is not legal or travel advice.

| Version | In force | Basis | Loaded into AsOf from |
|---|---|---|---|
| v1 | 12 Nov 2015 | Railway Passengers (Cancellation of Ticket and Refund of Fare) Rules, 2015 | 2020-01-01, the earliest date AsOf stores (intake and `APPLY_POLICY_CHANGE` refuse earlier dates) |
| v2 | 15 Apr 2026 | The Railway Minister's announcement of 24 Mar 2026: an announcement, not a gazetted rule | 2026-04-15 |

Every number, sentence and source URL is in one file, [src/asof/data/indian_rail.json](../src/asof/data/indian_rail.json).

## How it gets into Db2

The way a customer's policy does ([asof/indianrail.py](../src/asof/indianrail.py)):

1. A text-layer PDF per version (`data/samples/indian-rail-refunds-v1.pdf`, `-v2.pdf`), made from the data file.
2. Policy intake: v1 as a new document, v2 as a dated new version. The model's proposals come from the shipped recording (`data/replay.json`), so every database gets the same clauses: the public demo (replay mode), a developer's, CI's.
3. The editor accepts each proposal that is one whole section of its version (`DECIDE_POLICY_DRAFT`, `APPLY_DRAFT_ITEM`).
4. One editor correction per version through `APPLY_POLICY_CHANGE`:
   - It sets the clause's `RULE_JSON` to the fare table's `time_bands`, so the deterministic rule check decides the hour bands ([rules.py](../src/asof/rules.py) `band_check`; a band may also have a minimum charge per class, and a strict or inclusive edge).
   - It drops intake's flat numbers, because a single hour limit or percentage cannot say which band it belongs to.
   - It puts the version's source URLs in the row's `CHANGE_NOTE`, so the clause text and its quotes stay the summary's.
   - Db2 gives these rows new labels: v2 is the 2015 rules, v4 the 2026 rules.

Setup loads the domain when it is missing (`python -m asof.setup`, after the grants), and so does `python -m asof.indianrail [--schema X]`. Both are idempotent.

## Where it shows

- **The API:** `DocId` accepts `INDIAN-RAIL-REFUNDS`.
- **The console:** the Playground's document selector, which shows the label when it is chosen, the policy timeline and the specialist inbox.
- **The router:** it joins as a third document without changing how the airline and the bank route. When one of them leads and the rail document is not within `AGENT_MARGIN` (0.12) of it, the vote is the original two-document vote on the airline and the bank alone (same distances, same nearest clauses, same agent prompt). When the rail document leads, the vote decides between it and the runner-up with the usual thresholds. When the two are within 0.12, Db2 cannot tell them apart, so the routing agent, shown both, picks one (confident) or a person is asked: the one case where the agent may name a document Db2 did not rank first. Typed train questions ("I cancel my confirmed Sleeper ticket 6 hours before departure...") are such near ties with the airline (cosine distances 0.396 and 0.400), and the agent routes them to the rail document. In the routing splits, only three cases leave the two-document vote (RT35, RD16, RD17), all questions about neither policy, where no clause is near and a person is asked either way.
  The frozen `routing-test` split, run live once with the rail document loaded (`docs/routing/routing-test__openrouter_google_gemini-3.1-flash-lite__e92de25__*.json`), gave the same result as its run of 8 Nov: 30 of 30 routed right, 0 misrouted, 10 of 10 asked when they should, 0 guessed, 10 agent calls.
- **Row permissions:** the domain gets its own role and `DOMAIN_ACCESS` row, and ships with no analyst or specialist of its own.

Two Playground scenarios, recorded live once with `openrouter:google/gemini-3.1-flash-lite`:

| Scenario label | Travel date | Draft | Decision | Why |
|---|---|---|---|---|
| Indian Railways (summary, not official): travel 2 May 2026 | 2026-05-02 | You get 50% back. | **CORRECTED** (CORRECTED_FROM_CLAUSES) | v2 applies (from 2026-04-15): under 8 hours, no refund. The judge and the band check both found the draft contradicted; the rewrite, "For a confirmed ticket cancelled less than 8 hours before the scheduled departure, no refund is given.", passed its re-check, citing CAN-001 v4. |
| Indian Railways (summary, not official): travel 28 Mar 2026 | 2026-03-28 | Under the new rules, cancelling within 8 hours gets no refund. | **CORRECTED** (CORRECTED_FROM_CLAUSES) | The new slabs were announced on 24 Mar but are not in force until 15 Apr, so v1 still applies on 28 Mar: 12 to 4 hours, 50% charged, so half back. The judge and the band check both found the draft contradicted; the rewrite, "For a confirmed Sleeper Class ticket cancelled between 12 hours and 4 hours before the scheduled departure, the cancellation charge is 50% of the fare, subject to a minimum flat charge of Rs 120.", passed its re-check, citing CAN-001 v2 (in effect from 2020-01-01). |

The 28 Mar scenario was re-recorded live on 12 Nov 2026 (it replaced a 20 Mar scenario whose draft matched the old rule).

Question for both: "I cancel my confirmed Sleeper ticket 6 hours before departure; how much do I get back?"

## Limitations

- IRCTC's refund page still shows the 2015 slabs (48, 12 and 4 hours) as of 12 November 2026; v2 here follows the minister's announcement, which is not a gazette notification.
- G.S.R. 41(E) of 16 January 2026, a separate gazette rule for Vande Bharat Sleeper and Amrit Bharat II trains only, is not modelled.
- v2 states no rupee amounts for the flat charge more than 72 hours out (no official source gives them), so the rule check does not check rupee amounts in that band.
- The summary covers confirmed tickets only (no waitlisted or RAC tickets, no Tatkal, no GST amounts).
- The intake prompt for this domain has four rules of its own (`prompts.INDIAN_RAIL_INTAKE_RULES`). Two came from its first live intakes: one named every rupee amount `_usd` (intake's checks blocked it; SPR needed the same rule), and the next split the section into one proposal per sentence. Both of those outputs were thrown away, not recorded.
