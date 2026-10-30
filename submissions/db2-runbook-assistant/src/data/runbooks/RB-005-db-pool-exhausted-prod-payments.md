---
runbook_id: RB-005
title: Database connection pool exhausted on payments-api (prod)
service: payments-api
environment: prod
severity: critical
status: active
last_verified: 2025-10-10
---

## Symptom
Production payments-api returns 503 errors and logs `Timeout waiting for connection from pool`. Active connections are at the pool maximum.

## Steps
1. Check the pool dashboard for active, idle and waiting connections.
2. On the database, list sessions by client and state to spot a leak or long-running transactions.
3. Terminate sessions that are idle-in-transaction for more than 10 minutes, following the approved procedure.
4. Restart the affected payments-api instances one at a time, waiting for health checks between each, to release leaked connections.
5. Look for a recent deploy that changed query patterns or removed connection close calls; roll back if there is a clear link.
6. Do not raise the pool size above the database's connection limit without DBA approval.
7. Monitor for 30 minutes to confirm waiting connections stay at zero.

## Escalation
Page the payments on-call and the DBA on-call if errors persist after the rolling restart.
