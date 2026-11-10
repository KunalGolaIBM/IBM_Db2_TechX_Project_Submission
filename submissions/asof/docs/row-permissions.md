# Row permissions per policy domain

AsOf checks answers for more than one policy domain: the fictional Aurelia Air (`AURELIA-CSP`) and Fernhollow Bank
(`FERNHOLLOW-FEES`). In a real deployment those belong to different teams, and an analyst or specialist on one should
not read the other's decisions. Db2 enforces that with row permissions (the "R" in RCAC), so it holds for any SQL a
user runs, through any view, and for the rows a procedure writes on the user's behalf. The SQL is in
[`06_domain_permissions.sql`](../src/asof/sql/06_domain_permissions.sql); the roles and users are granted by
[`rowaccess.py`](../src/asof/rowaccess.py).

## The rule

Every row that records a decision belongs to one policy document: the ledger row's `DOC_ID`, and for the tables that
hang off it, the `DOC_ID` of the row they point at. Db2 shows a row only to:

1. holders of role `ASOF_ALL_DOMAINS`;
2. holders of `SECADM`: the owner, `db2inst1`, who runs setup, backup, reset and the tests' checks, and who could drop
   the permissions anyway, so hiding rows from it would hide nothing;
3. holders of a role that `ASOF.DOMAIN_ACCESS` maps to the row's `DOC_ID`.

Anyone else sees no rows at all. Each permission is `ENFORCED FOR ALL ACCESS`, so the same rule limits what an `UPDATE`
or `DELETE` can reach, and Db2 refuses an `INSERT` or `UPDATE` whose resulting row the caller could not see
(`SQL20471N`, SQLSTATE 22542).

| Table | Domain of a row |
|---|---|
| `ANSWER_LEDGER` | its `DOC_ID` |
| `CLAIM_CITATION` | its decision's |
| `ESCALATION_REVIEW` | the held decision's it answers |
| `CORRECTION_NOTICE` | the answer's it corrects |
| `ANSWER_SUGGESTION` | the help-centre answer's it would replace |
| `MQT_DOMAIN_DECISION_STATS`, `MQT_DOMAIN_CLAIM_OUTCOMES` | the `DOC_ID` they group by |
| `MQT_DECISION_STATS`, `MQT_CLAIM_OUTCOMES` | every domain at once: shown only under rules 1 and 2 |

Policy itself (`POLICY_CLAUSE`, its history, `PUBLISHED_ANSWER`, `V_POLICY_TIMELINE`) is not protected: it is what the
company publishes to customers, the same for every reader, and every check needs it.

Domains map to roles in data, not in SQL. Setup creates a role `ASOF_DOMAIN_<KEY>` for every domain in
[`domains.py`](../src/asof/domains.py) and writes its row into `DOMAIN_ACCESS`, so a third domain is covered by the same
permissions with no new SQL. `V_DOMAIN_SCOPE` applies the same rule to `POLICY_DOC`: it lists the documents whose
decisions the current user may see.

## Users

| User | Holds | Sees |
|---|---|---|
| `asofapp` (runtime), `asofedit` (editor), `asofrev` (specialist), `asofread` (analyst), `asofmart` (dbt) | `ASOF_ALL_DOMAINS` | every domain |
| `db2inst1` (owner) | `SECADM` | every domain |
| `airread`, `bankread` (domain analysts) | `ASOF_ANALYST` and `ASOF_DOMAIN_AIRLINE` or `ASOF_DOMAIN_BANK` | their domain |
| `airrev`, `bankrev` (domain specialists) | `ASOF_SPECIALIST` and the domain role | their domain |

The runtime user must see every row: `APPEND_LEDGER` writes every domain's decisions and `VERIFY_CHAIN` hashes the
whole chain in order. The editor's change impact, the all-domain specialist inbox and dbt's marts read across
domains too. The domain users are OS users in the Db2 container, created by setup like the others, with passwords
generated into `.env` (`ASOF_AIRLINE_ANALYST_PASSWORD` and so on). `ASOF_SPECIALIST` holds exactly what `asofrev`
holds (connect, `ASOF_TEXT_READER`, `RESOLVE_ESCALATION`, `DECIDE_NOTICE`); which held decisions a domain specialist
can reach is the row permissions' call. Setup refuses a domain user that is also one of the all-domain users.

## What it looks like

- `airread` running `SELECT COUNT(*) FROM V_AUDIT_DECISIONS WHERE DOC_ID = 'FERNHOLLOW-FEES'` gets 0. So does a
  `WHERE LEDGER_ID IN (...)` that names the bank's rows.
- Given `SELECT` on the base tables (a test does this in a scratch schema), it still reads only Aurelia Air's rows:
  the permission is on the table, not in the view.
- `bankrev` calling `RESOLVE_ESCALATION` on an Aurelia Air decision gets 75050, "Unknown ledger entry": inside the
  procedure, Db2 hides the row from it. `airrev` answers the same decision.
- A domain user given `EXECUTE` on `APPEND_LEDGER` can append its own domain's decisions; one for the other domain
  fails with `SQL20471N`.
- Ask the ledger has a scope selector (All domains, Aurelia Air, Fernhollow Bank). A domain scope runs the same
  checked SQL as that domain's analyst and shows the scope Db2 applied (`scope_applied`, read from `V_DOMAIN_SCOPE`
  on that user's connection). The model's view descriptions and sample rows are read as that user too.

All of this is in [`tests/test_db2_row_permissions.py`](../tests/test_db2_row_permissions.py); the SQL's structure
(every protected table, the same rule in every copy, secured triggers) in
[`tests/test_row_permissions.py`](../tests/test_row_permissions.py).

## Db2 details that shaped it

- **The rule is written out in each permission**, not kept in one view: Db2 will not drop or replace a view or table
  that a permission depends on (`SQL0478N`), and setup replaces every view on each run. A unit test fails the build
  if one copy drifts.
- **Triggers on a protected table must be `SECURED`.** Activating row access control on `ESCALATION_REVIEW` failed with
  `SQL20469N` reason 37 until its two triggers were; `CORRECTION_NOTICE`'s are too (`02_ledger_rules.sql`).
- **MQTs inherit row access control with no permission.** Once a base table has it, Db2 activates it on every MQT over
  it and every row disappears. The two analytics MQTs count every domain together, so their permission admits only
  rules 1 and 2. Two more MQTs hold the same figures per `DOC_ID` and carry the domain rule. `V_DECISION_STATS` and
  `V_CLAIM_OUTCOMES_BY_AREA` are a `UNION ALL` of both: the first branch is the view as it was, the second answers
  only a reader who is neither an all-domain user nor `SECADM`. So every existing reader gets the same rows, columns,
  types and order as before (which keeps the recorded Ask the ledger examples replaying), and a domain analyst gets
  its own domain's figures. An earlier version added `DOC_ID` to the original MQTs and grouped again in the views:
  that made `DECISIONS` and `CLAIMS` nullable, which changes the schema text the model is shown, and left the order
  of the model's sample rows to a `GROUP BY`.
  `MQT_DOMAIN_CLAIM_OUTCOMES` gets `DOC_ID` by joining the ledger, which a `REFRESH IMMEDIATE` MQT allows only with
  the implicit join syntax (`FROM a, b WHERE`; `JOIN ... ON` is `SQL20058N` reason 10).
- **One permission had to go.** Installs from before this had `P_MQT_DECISION_STATS_ALL_ROWS` (`WHERE 1 = 1`). Db2 ORs a
  table's permissions, so it would have shown every domain's counts to a domain analyst; setup drops it (tested).
- **Permission subqueries need no privileges from the reader.** `airread` holds nothing on `DOMAIN_ACCESS`,
  `POLICY_DOC` or the ledger tables, and Db2 still applies the rule to its queries: the reader's privileges are not
  checked against what a permission reads.

## Limits

- The API's specialist inbox still answers as `asofrev`, which sees every domain: AsOf's API users carry roles but no
  domain. The domain specialists are there for teams that connect per domain, and to prove the rule holds inside the
  procedures.
- Ask the ledger's replay mode has recordings for the All domains scope only (the model's input includes sample rows,
  which differ per scope), so a domain scope needs a live model.
- Changing a domain user's name in `.env` creates the new user; the old one keeps its role until revoked by hand.
