---
runbook_id: RB-004
title: Pod in CrashLoopBackOff in UAT payments-api
service: payments-api
environment: uat
severity: medium
status: active
last_verified: 2025-09-20
---

## Symptom
A payments-api pod in the UAT cluster is in `CrashLoopBackOff` and restarts repeatedly, blocking test cycles.

## Steps
1. List the pods: `kubectl get pods -n payments-uat`.
2. Read the last crash output: `kubectl logs <pod> -n payments-uat --previous`.
3. Describe the pod and check events and exit codes: `kubectl describe pod <pod> -n payments-uat`. Exit code 137 suggests OOMKilled.
4. Verify that config maps and secrets referenced by the deployment exist and have the expected keys.
5. If a recent deploy caused it, roll back: `kubectl rollout undo deployment/payments-api -n payments-uat`.
6. If OOMKilled, raise the memory limit in the UAT values file and redeploy.
7. Confirm the pod reaches `Running` and passes readiness checks.

## Escalation
If the same image works elsewhere but not in UAT, contact the platform team during business hours. No paging is needed for UAT.
