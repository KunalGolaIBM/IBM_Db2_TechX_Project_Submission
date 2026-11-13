-- Checks per day, policy document, channel and decision.
select
    DECIDED_ON,
    DOC_ID,
    CHANNEL,
    DECISION,
    count(*)                 as DECISIONS,
    integer(avg(LATENCY_MS)) as AVG_LATENCY_MS
from {{ ref('stg_decisions') }}
group by DECIDED_ON, DOC_ID, CHANNEL, DECISION
