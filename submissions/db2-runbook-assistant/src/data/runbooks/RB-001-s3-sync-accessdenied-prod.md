---
runbook_id: RB-001
title: Deployment fails on S3 sync step with AccessDenied (prod)
service: web-frontend
environment: prod
severity: high
status: active
last_verified: 2025-09-12
---

## Symptom
The production deployment pipeline fails at the "S3 sync" step with `AccessDenied` (HTTP 403) when uploading build artifacts to the production static-assets bucket.

## Steps
1. Stop and do not retry the pipeline repeatedly; repeated failures can trigger security alerts.
2. Raise an emergency change request (CR) before touching any production permission.
3. Identify the role the pipeline assumes and confirm it was not rotated recently.
4. Run an IAM policy simulation for that role against `s3:PutObject` and `s3:ListBucket` on the prod bucket to find the missing or denied action.
5. Check for an explicit Deny in the bucket policy or a service control policy; fix the role's identity policy through the approved IaC repository, with peer review.
6. NEVER widen the production bucket policy (for example `Principal: *` or `s3:*`) to get the deploy through.
7. After the approved change is applied, re-run the pipeline once and verify the site serves the new build.
8. Record the root cause and the CR number in the incident ticket.

## Escalation
If the simulation shows no gap or the deny comes from an organisation-level policy, page the platform security on-call and attach the simulation output.
