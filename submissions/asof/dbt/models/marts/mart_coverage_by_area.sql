-- Where the policy runs out: claims no clause in force covered, by document and area (first pass).
select
    DOC_ID,
    AREA,
    count(*)                                                    as CLAIMS,
    sum(case when VERDICT = 'NOT_COVERED' then 1 else 0 end)    as NOT_COVERED,
    decimal(100.0 * sum(case when VERDICT = 'NOT_COVERED' then 1 else 0 end) / count(*), 5, 1) as NOT_COVERED_PCT
from {{ ref('stg_claims') }}
where PASS_NO = 1
group by DOC_ID, AREA
