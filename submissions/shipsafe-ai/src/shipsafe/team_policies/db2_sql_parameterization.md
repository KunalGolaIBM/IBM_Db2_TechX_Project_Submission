---
id: POL-DB2-001
title: IBM Db2 Parameterized SQL and Injection Defense
category: security
version: 1.2.0
---
# IBM Db2 Parameterized SQL and Injection Defense

## Rule
Every SQL statement sent to IBM Db2 must use parameter markers (`?`) with
`ibm_db.prepare` / `ibm_db.execute`, `ibm_db_dbi` cursors, or an ORM that binds
parameters. Building SQL text with f-strings, `%` formatting, `.format()` or string
concatenation is a release-blocking security violation (SQL injection).

## Remediation
Replace `cursor.execute(f"SELECT ... WHERE ID = '{user_id}'")` with
`cursor.execute("SELECT ... WHERE ID = ?", (user_id,))`. Identifiers such as schema or
table names cannot be parameter markers; validate them against an allowlist instead.

## Severity
Unparameterized SQL that touches user input is Critical and blocks the pull request.
