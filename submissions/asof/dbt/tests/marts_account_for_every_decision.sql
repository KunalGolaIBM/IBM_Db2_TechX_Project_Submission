-- The daily mart must add up to the ledger, row for row. Expect no rows.
select 1 as MISMATCH
from sysibm.sysdummy1
where (select coalesce(sum(DECISIONS), 0) from {{ ref('mart_decisions_daily') }})
   <> (select count(*) from {{ source('asof', 'ANSWER_LEDGER') }})
