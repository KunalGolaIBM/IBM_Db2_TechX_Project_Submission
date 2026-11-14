# ADR 003: Exclusive connection leases

Status: accepted.

A shared DB-API connection plus one global query lock serialized requests and tied all
requests to one session. Use a bounded condition-based pool: configurable minimum/maximum,
admission timeout, health probe, driver timeouts, rollback on release and reconnect after
a dropped connection. LangChain DB2VS borrows from this same pool for its whole operation.

Each transaction owns one session; the lock protects capacity bookkeeping only. Report
MERGE and insertion share a lease. Retry only known rolled-back conflicts; do not replay
an ambiguously committed write after a network failure. Connection budgets multiply by
process count. Thread-based execution still needs explicit capacity planning.
