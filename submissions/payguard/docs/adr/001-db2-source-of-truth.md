# ADR 001: Db2 is the source of truth

Status: accepted.

Entity status, report counts, screening evidence and payment state must agree. Keep
relational records and embeddings in Db2, using parameterized SQL and one atomic
transaction for each report. Checkout re-reads Db2 instead of trusting browser fields.

This avoids dual writes to separate vector and transactional databases. Db2 becomes a
central availability dependency: rules may produce a degraded verdict during an outage,
but an unpersisted screening cannot authorize payment. Replicas may serve analytics;
payment authorization must account for replication lag and read the primary.
