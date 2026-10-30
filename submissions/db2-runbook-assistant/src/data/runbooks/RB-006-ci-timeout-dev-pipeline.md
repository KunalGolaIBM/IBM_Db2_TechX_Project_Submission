---
runbook_id: RB-006
title: CI job timeout in data-pipeline (dev)
service: data-pipeline
environment: dev
severity: low
status: active
last_verified: 2025-07-18
---

## Symptom
A data-pipeline CI job in dev is cancelled with "job exceeded maximum execution time".

## Steps
1. Open the job log and find the last step that produced output; that step is the likely hang.
2. Check whether the runner is under load or out of disk; restart the runner if needed.
3. Clear the dependency cache for the job and retry; corrupted caches often cause stalls.
4. If a test is hanging, run it locally with a timeout flag to reproduce.
5. If the job is legitimately slow, split it into parallel stages or raise the timeout in the dev CI config.
6. Re-run the job and confirm it finishes within the limit.

## Escalation
If several unrelated jobs time out, report it in #dev-platform as a runner capacity problem.
