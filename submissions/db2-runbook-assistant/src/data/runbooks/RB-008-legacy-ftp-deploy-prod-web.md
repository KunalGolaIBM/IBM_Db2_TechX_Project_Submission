---
runbook_id: RB-008
title: Legacy manual FTP deploy for web-frontend (prod)
service: web-frontend
environment: prod
severity: medium
status: deprecated
last_verified: 2022-03-01
---

## Symptom
The automated pipeline is unavailable and a production web-frontend release must be pushed by hand. This process is deprecated and retained only for history.

## Steps
1. Build the release archive on a workstation.
2. Connect to the legacy web host over FTP using the shared deploy account.
3. Upload the archive to the release directory and unpack it.
4. Switch the `current` symlink to the new release directory.
5. Restart the web server and check the home page.

## Escalation
Contact the web team lead. Use the pipeline-based process instead whenever possible.
