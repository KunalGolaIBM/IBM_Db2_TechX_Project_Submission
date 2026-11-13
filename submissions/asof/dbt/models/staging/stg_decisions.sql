-- Decisions without any free text: the marts never need what the customer or the assistant wrote.
select
    LEDGER_ID,
    date(CREATED_AT)  as DECIDED_ON,
    CHANNEL,
    DOC_ID,
    AS_OF_DATE,
    DECISION,
    REASON_CODE,
    LATENCY_MS
from {{ source('asof', 'ANSWER_LEDGER') }}
