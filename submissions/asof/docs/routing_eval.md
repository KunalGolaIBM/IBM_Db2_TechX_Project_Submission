# Routing evaluation

Which policy document a question and draft are about, decided by `asof/router.py`: Db2 ranks the clauses of both documents in force on the customer's date by `VECTOR_DISTANCE` and routes a clear lead with no model call; a close call goes to the routing agent, which can only confirm Db2's leader or hand the question to a person (reason `ROUTE_UNCERTAIN`, answered in the specialist inbox).

Thresholds, set on the 20-case dev split: route on Db2 alone when the leader is nearer by at least 0.3 (cosine distance) and the other document's best clause is farther than 0.45; ask a person when no clause of either document is nearer than 0.65; between the two, the routing agent may confirm Db2's leader only when it leads by at least 0.12. The 40-case test split was committed and its SHA-256 pinned in `6f3a15e`, before the router existed, and is never tuned on.

**Misrouted** is the dangerous error: a draft checked against the other company's policy. **Asked** costs a specialist's time but is safe. **Guessed**: a question that needs a person (ambiguous, out of scope, or needing both documents) routed to one document anyway.

The routing agent is off by default (`ASOF_ROUTER_AGENT=false`): on the test split it recovered every shared-vocabulary case Db2 alone sent to a person, but with the local model it also guessed on ambiguous questions, and asking is the safe failure. A deployment can turn it on after measuring its own model with `python -m asof.eval.routing --split routing-test`.

## routing-test: Db2 vote only (no model), run 2026-11-08 at `6c5e99f`

| Measure | Result |
|---|---|
| Routed to the right document | 26 of 30 |
| **Misrouted** (other document) | **0 of 30** |
| Asked a person, document was clear | 4 of 30 |
| Asked a person when it should | 10 of 10 |
| Guessed when it should have asked | 0 of 10 |
| Decided by Db2 alone / with the agent / asked | 26 / 0 / 14 |
| Routing agent calls | 0 |
| Median latency | 19 ms |

| Category | Cases | Correct | Misrouted | Asked | Guessed |
|---|---|---|---|---|---|
| clear_airline | 8 | 8 | 0 | 0 | 0 |
| clear_bank | 8 | 8 | 0 | 0 | 0 |
| trap | 12 | 8 | 0 | 4 | 0 |
| ambiguous | 5 | 5 | 0 | 0 | 0 |
| out_of_scope | 3 | 3 | 0 | 0 | 0 |
| mixed | 2 | 2 | 0 | 0 | 0 |
| injection | 2 | 2 | 0 | 0 | 0 |

Not as labelled: `RT17` (trap) expected AURELIA-CSP, got ASK via ask; `RT22` (trap) expected AURELIA-CSP, got ASK via ask; `RT24` (trap) expected FERNHOLLOW-FEES, got ASK via ask; `RT27` (trap) expected FERNHOLLOW-FEES, got ASK via ask.

## routing-test: Db2 vote + routing agent (ollama:qwen2.5:7b-instruct), run 2026-11-08 at `6c5e99f`

| Measure | Result |
|---|---|
| Routed to the right document | 30 of 30 |
| **Misrouted** (other document) | **0 of 30** |
| Asked a person, document was clear | 0 of 30 |
| Asked a person when it should | 6 of 10 |
| Guessed when it should have asked | 4 of 10 |
| Decided by Db2 alone / with the agent / asked | 26 / 8 / 6 |
| Routing agent calls | 10 |
| Median latency | 33 ms |

| Category | Cases | Correct | Misrouted | Asked | Guessed |
|---|---|---|---|---|---|
| clear_airline | 8 | 8 | 0 | 0 | 0 |
| clear_bank | 8 | 8 | 0 | 0 | 0 |
| trap | 12 | 12 | 0 | 0 | 0 |
| ambiguous | 5 | 1 | 0 | 0 | 4 |
| out_of_scope | 3 | 3 | 0 | 0 | 0 |
| mixed | 2 | 2 | 0 | 0 | 0 |
| injection | 2 | 2 | 0 | 0 | 0 |

Not as labelled: `RT29` (ambiguous) expected ASK, got AURELIA-CSP via db2+agent, agent said AURELIA-CSP; `RT30` (ambiguous) expected ASK, got AURELIA-CSP via db2+agent, agent said AURELIA-CSP; `RT31` (ambiguous) expected ASK, got FERNHOLLOW-FEES via db2+agent, agent said FERNHOLLOW-FEES; `RT33` (ambiguous) expected ASK, got AURELIA-CSP via db2+agent, agent said AURELIA-CSP.

## routing-dev: Db2 vote only (no model), run 2026-11-08 at `6c5e99f`

| Measure | Result |
|---|---|
| Routed to the right document | 13 of 14 |
| **Misrouted** (other document) | **0 of 14** |
| Asked a person, document was clear | 1 of 14 |
| Asked a person when it should | 6 of 6 |
| Guessed when it should have asked | 0 of 6 |
| Decided by Db2 alone / with the agent / asked | 12 / 0 / 8 |
| Routing agent calls | 0 |
| Median latency | 16 ms |

| Category | Cases | Correct | Misrouted | Asked | Guessed |
|---|---|---|---|---|---|
| clear_airline | 3 | 3 | 0 | 0 | 0 |
| clear_bank | 3 | 3 | 0 | 0 | 0 |
| trap | 6 | 5 | 0 | 1 | 0 |
| ambiguous | 3 | 3 | 0 | 0 | 0 |
| out_of_scope | 2 | 2 | 0 | 0 | 0 |
| mixed | 1 | 1 | 0 | 0 | 0 |
| injection | 2 | 2 | 0 | 0 | 0 |

Not as labelled: `RD07` (trap) expected AURELIA-CSP, got ASK via ask.

## routing-dev: Db2 vote + routing agent (ollama:qwen2.5:7b-instruct), run 2026-11-08 at `6c5e99f`

| Measure | Result |
|---|---|
| Routed to the right document | 14 of 14 |
| **Misrouted** (other document) | **0 of 14** |
| Asked a person, document was clear | 0 of 14 |
| Asked a person when it should | 5 of 6 |
| Guessed when it should have asked | 1 of 6 |
| Decided by Db2 alone / with the agent / asked | 12 / 3 / 5 |
| Routing agent calls | 4 |
| Median latency | 26 ms |

| Category | Cases | Correct | Misrouted | Asked | Guessed |
|---|---|---|---|---|---|
| clear_airline | 3 | 3 | 0 | 0 | 0 |
| clear_bank | 3 | 3 | 0 | 0 | 0 |
| trap | 6 | 6 | 0 | 0 | 0 |
| ambiguous | 3 | 2 | 0 | 0 | 1 |
| out_of_scope | 2 | 2 | 0 | 0 | 0 |
| mixed | 1 | 1 | 0 | 0 | 0 |
| injection | 2 | 2 | 0 | 0 | 0 |

Not as labelled: `RD14` (ambiguous) expected ASK, got AURELIA-CSP via db2+agent, agent said AURELIA-CSP.
