---
id: POL-SEC-004
title: Safe Process Execution and Dynamic Code Policy
category: security
version: 1.0.0
---
# Safe Process Execution and Dynamic Code Policy

## Rule
Production code must not start processes with `shell=True`, and must not call `eval()`
or `exec()` on data. Untrusted data must not be deserialized with `pickle`.

## Remediation
Call `subprocess.run([...], shell=False)` with a fixed argument list and validated
arguments. Use `json` or `ast.literal_eval` instead of `eval`, and JSON or Protocol
Buffers instead of `pickle` for data crossing a trust boundary.
