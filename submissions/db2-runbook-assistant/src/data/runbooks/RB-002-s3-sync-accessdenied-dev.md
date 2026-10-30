---
runbook_id: RB-002
title: Deployment fails on S3 sync step with AccessDenied (dev)
service: web-frontend
environment: dev
severity: low
status: active
last_verified: 2025-08-30
---

## Symptom
The dev deployment pipeline fails at the "S3 sync" step with `AccessDenied` (HTTP 403) when uploading build artifacts to the dev static-assets bucket.

## Steps
1. Simply retry the pipeline once; transient credential errors are common in dev.
2. If it fails again, refresh the pipeline's temporary credentials (re-run the credentials job or re-assume the dev deploy role).
3. Confirm the pipeline is targeting the dev bucket and not a stale bucket name in the environment variables.
4. If the dev bucket policy is missing the pipeline role, widening the dev bucket policy temporarily (for example allowing `s3:PutObject` for the dev account) is acceptable. No change request is needed in dev.
5. Re-run the pipeline and confirm the dev site shows the new build.
6. Later, codify the permission in IaC so the manual fix does not drift.

## Escalation
If it still fails after the policy change, ask in the #dev-platform channel; no paging is needed for dev.
