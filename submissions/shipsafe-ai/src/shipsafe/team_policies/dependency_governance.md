---
id: POL-DEP-003
title: Third-Party Dependency and Known Vulnerability Policy
category: dependencies
version: 1.1.0
---
# Third-Party Dependency and Known Vulnerability Policy

## Rule
Packages with known Critical or High severity CVEs must be upgraded to a patched
version before a production release. Medium severity CVEs require a tracked
remediation ticket within 30 days.

## Minimum versions
PyYAML must be 5.4 or newer (CVE-2020-14343, arbitrary code execution in `yaml.load`).
requests must be 2.31.0 or newer (CVE-2023-32681, Proxy-Authorization header leak).
urllib3 must be 2.0.7 or newer. cryptography must be 41.0.6 or newer.

## Remediation
Pin the patched version in `requirements.txt` or `pyproject.toml`, regenerate the lock
file and re-run the assessment to confirm the finding is resolved.
