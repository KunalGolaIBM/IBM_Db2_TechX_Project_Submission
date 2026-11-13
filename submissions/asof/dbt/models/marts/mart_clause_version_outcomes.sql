-- How each clause version fared when drafts were checked against it (first pass only).
select
    DOC_ID,
    CLAUSE_ID,
    CLAUSE_VERSION,
    CLAUSE_BUS_START,
    count(*)                                                    as CLAIMS_CHECKED,
    sum(case when VERDICT = 'SUPPORTED' then 1 else 0 end)      as SUPPORTED,
    sum(case when VERDICT = 'CONTRADICTED' then 1 else 0 end)   as CONTRADICTED,
    sum(RULE_OVERRIDE)                                          as RULE_OVERRIDES
from {{ ref('stg_claims') }}
where PASS_NO = 1 and CLAUSE_ID is not null
group by DOC_ID, CLAUSE_ID, CLAUSE_VERSION, CLAUSE_BUS_START
