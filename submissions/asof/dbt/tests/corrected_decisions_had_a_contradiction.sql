-- A CORRECTED decision means the draft contradicted the policy. One without a contradicted
-- first-pass claim would be a ledger the check's own rules cannot explain. Expect no rows.
select d.LEDGER_ID
from {{ ref('stg_decisions') }} d
where d.DECISION = 'CORRECTED'
  and not exists (select 1 from {{ ref('stg_claims') }} c
                  where c.LEDGER_ID = d.LEDGER_ID and c.PASS_NO = 1 and c.VERDICT = 'CONTRADICTED')
