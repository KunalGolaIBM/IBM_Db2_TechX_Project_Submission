-- Every citation names a clause version by (CLAUSE_ID, CLAUSE_BUS_START). That version must exist
-- in the current rows or in system-time history, even after later policy changes. Expect no rows.
select c.LEDGER_ID, c.CLAIM_NO, c.CLAUSE_ID, c.CLAUSE_BUS_START
from {{ ref('stg_claims') }} c
where c.CLAUSE_ID is not null
  and not exists (select 1 from {{ source('asof', 'POLICY_CLAUSE') }} p
                  where p.CLAUSE_ID = c.CLAUSE_ID and p.BUS_START = c.CLAUSE_BUS_START)
  and not exists (select 1 from {{ source('asof', 'POLICY_CLAUSE_HIST') }} h
                  where h.CLAUSE_ID = c.CLAUSE_ID and h.BUS_START = c.CLAUSE_BUS_START)
