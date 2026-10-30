---
runbook_id: RB-003
title: Disk usage above 90% on payments-api hosts (prod)
service: payments-api
environment: prod
severity: critical
status: active
last_verified: 2025-10-02
---

## Symptom
Monitoring alerts that disk usage on a production payments-api host is above 90%. Writes may start failing and the service can stop accepting payments.

## Steps
1. Identify the affected host and mount point with `df -h`.
2. Find the largest directories: `du -xh --max-depth=2 /var | sort -h | tail -20`.
3. Check application logs under `/var/log/payments-api`; if rotation has stalled, force it with `logrotate -f /etc/logrotate.d/payments-api`.
4. Compress or move logs older than 7 days to the archive bucket. Do not delete transaction audit logs.
5. Remove old container images and stopped containers: `docker system prune --filter "until=72h"`.
6. If usage stays above 85%, request a volume expansion through the standard change process.
7. Confirm usage is below 80% and the alert clears.

## Escalation
If usage exceeds 95% or the service is rejecting writes, page the payments on-call immediately and declare an incident.
