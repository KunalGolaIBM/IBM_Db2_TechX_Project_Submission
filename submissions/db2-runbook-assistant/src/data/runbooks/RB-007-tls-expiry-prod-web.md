---
runbook_id: RB-007
title: TLS certificate expiring or expired on web-frontend (prod)
service: web-frontend
environment: prod
severity: high
status: active
last_verified: 2025-10-05
---

## Symptom
Browsers show certificate warnings for the production web-frontend, or monitoring warns that the TLS certificate expires in fewer than 14 days.

## Steps
1. Check the expiry: `echo | openssl s_client -connect www.example.com:443 2>/dev/null | openssl x509 -noout -dates`.
2. Check whether automatic renewal ran; review the certificate manager's logs for failed challenges.
3. Fix the cause (DNS record for validation, blocked challenge path, expired API token) and trigger a renewal.
4. If auto-renewal cannot be fixed quickly, issue a certificate manually through the approved CA workflow under an emergency change request.
5. Deploy the new certificate to the load balancer and CDN.
6. Verify the full chain with an external checker and confirm the new expiry date.

## Escalation
If the certificate has already expired, declare an incident and page the platform on-call.
