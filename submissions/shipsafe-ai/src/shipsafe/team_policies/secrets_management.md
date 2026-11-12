---
id: POL-SEC-002
title: Secret and Credential Management Standard
category: secrets
version: 2.0.0
---
# Secret and Credential Management Standard

## Rule
Hardcoded secrets, cloud access keys (for example AWS `AKIA...` keys), API tokens,
GitHub personal access tokens, private keys and database passwords must never be
committed to source code, configuration files or test fixtures.

## Db2 credentials
Db2 connection credentials must come from environment variables such as `DB2_PASSWORD`
or from an enterprise secret vault at runtime. Connection strings containing `PWD=` must
never be logged or written to reports.

## Remediation
Revoke and rotate the exposed credential immediately, remove it from the code and Git
history, and load it from the environment. Any detected secret blocks merging.
