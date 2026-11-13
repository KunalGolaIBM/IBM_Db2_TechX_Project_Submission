select
    c.LEDGER_ID,
    c.PASS_NO,
    c.CLAIM_NO,
    d.DOC_ID,
    c.AREA,
    c.VERDICT,
    c.LLM_VERDICT,
    c.RULE_CHECK,
    c.CLAUSE_ID,
    c.CLAUSE_VERSION,
    c.CLAUSE_BUS_START,
    case when c.LLM_VERDICT = 'SUPPORTED' and c.VERDICT = 'CONTRADICTED' and c.RULE_CHECK = 'MISMATCH'
         then 1 else 0 end as RULE_OVERRIDE
from {{ source('asof', 'CLAIM_CITATION') }} c
join {{ ref('stg_decisions') }} d on d.LEDGER_ID = c.LEDGER_ID
