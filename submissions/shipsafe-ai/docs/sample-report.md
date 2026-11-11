# ShipSafe AI Production-Readiness Assessment Report

**Release Gate Status:** `🔴 BLOCKED`  
**Project:** `vulnerable_project` (`prj_vulnerable_project_78fd987e05f4`)  
**Assessment ID:** `asm_5714f25d9dda`  
**Profile:** `pre-pr`  
**Timestamp:** `2026-11-11 11:23:23 UTC`  
**Commit / HEAD:** `uncommitted` | **Branch:** `main`  

---

## 1. Executive Summary
BLOCKED: 6 blocking issue(s) violate production-readiness criteria.

- **Critical Issues:** 4
- **High Severity Issues:** 1
- **Medium Severity Issues:** 1
- **Low / Informational:** 0
- **Total Findings:** 6

---

## 2. Release Gate Policy Evaluation
- Blocked by Policy GATE-001: 4 Critical severity finding(s) detected (Secrets/RCE/SQLi).
- Blocked by Policy GATE-002: 1 High severity finding(s) detected.
- Blocked by Policy GATE-003: Required automated test suite failed.
- Warning GATE-101: 1 Medium severity finding(s) identified.
- Notice GATE-201: Check 'infrastructure_trivy' was skipped (No Dockerfile, Compose, or IaC configuration detected).

---

## 3. Tool Execution & Provenance

| Tool Name | Status | Exit Code | Duration (ms) | Operational Notes |
| :--- | :--- | :--- | :--- | :--- |
| `shipsafe_secrets_scanner` | `failed` | `1` | `3ms` | Inspected 5 files with 5 deterministic secret rules. Identified 1 secrets. |
| `shipsafe_sast_bandit` | `failed` | `1` | `1ms` | SAST analysis completed across 4 Python files. Found 2 security findings. |
| `shipsafe_dependency_audit` | `failed` | `1` | `0ms` | Scanned 1 manifests against advisory database. Found 2 vulnerable packages. |
| `shipsafe_quality_ruff` | `passed` | `0` | `1ms` | Checked quality across 4 Python files. Found 0 quality/lint warnings. |
| `shipsafe_test_runner` | `failed` | `1` | `166ms` | Test run completed in 166ms. Result: FAIL (Failures: 1, Errors: 0) |

### Skipped & Unsupported Checks
- **`infrastructure_trivy`**: No Dockerfile, Compose, or IaC configuration detected

---

## 4. Normalized Findings & Evidence

### Finding 1: AWS Access Key ID Detected
- **Severity:** `CRITICAL` | **Confidence:** `high` | **Category:** `secrets`
- **Source Scanner:** `shipsafe_secrets_scanner` | **Rule ID:** `SEC-001`
- **Fingerprint:** `c57b3cd69248de3901b9859564de018fe30aed689f748002772e8276a9bd5071`
- **Location:** `src/api.py:7`
- **Description:** Potential secret or credential pattern identified in src\api.py:7
```json
{
  "snippet": "AWS_SECRET_KEY = \"[REDACTED_AWS_KEY]\""
}
```
**Remediation Guidance:**
Revoke the exposed AWS credential immediately in AWS IAM and store secrets in environment variables or HashiCorp Vault.


### Finding 2: Potential SQL Injection / Unparameterized Query
- **Severity:** `CRITICAL` | **Confidence:** `high` | **Category:** `security`
- **Source Scanner:** `shipsafe_sast_bandit` | **Rule ID:** `B608-SQLI`
- **Fingerprint:** `fb85c526c3a379a25f264b5f770ba7d784bd672bb008f00e8b71abe33e1f3120`
- **Location:** `src/api.py:12`
- **Description:** Database query constructed via dynamic string formatting or concatenation. IBM Db2 queries must use parameterized markers (?) to prevent SQL injection.
```json
{
  "snippet": "query = f\"SELECT BALANCE FROM ACCOUNTS WHERE ACCOUNT_ID = '{account_id}'\""
}
```
**Remediation Guidance:**
Refactor to use parameterized SQL queries with query markers (e.g., `ibm_db.execute(stmt, (param1, param2))` or parameter tuple). Never format user input directly into SQL strings.


### Finding 3: Subprocess Executed with shell=True
- **Severity:** `HIGH` | **Confidence:** `high` | **Category:** `security`
- **Source Scanner:** `shipsafe_sast_bandit` | **Rule ID:** `B602-SUBPROCESS-SHELL`
- **Fingerprint:** `384ffa1dca011632bc537f2584fab2079c2b8210e4bc56fcdb9e7cf50743bf59`
- **Location:** `src/api.py:19`
- **Description:** Spawning a process with `shell=True` exposes the application to arbitrary shell command injection.
```json
{
  "snippet": "subprocess.run(backup_cmd, shell=True)"
}
```
**Remediation Guidance:**
Set `shell=False` and pass command arguments as an array of validated strings: `subprocess.run(['command', 'arg1'])`.


### Finding 4: Vulnerable Dependency: pyyaml==5.3.1 (CVE-2020-14343)
- **Severity:** `CRITICAL` | **Confidence:** `high` | **Category:** `dependencies`
- **Source Scanner:** `shipsafe_dependency_audit` | **Rule ID:** `CVE-2020-14343`
- **Fingerprint:** `493f25d9de566284447475d21e1b1b33ad106433870dd3c4dfbb9c7d2d4c3e6c`
- **Location:** `requirements.txt:1`
- **Description:** PyYAML before 5.4 lacks proper restrictions on untrusted YAML tags allowing full arbitrary code execution.
```json
{
  "package": "pyyaml",
  "installed_version": "5.3.1",
  "vulnerable_below": "5.4.0"
}
```
**Remediation Guidance:**
Upgrade pyyaml to >= 5.4.1 or use yaml.safe_load().


### Finding 5: Vulnerable Dependency: requests==2.25.1 (CVE-2023-32681)
- **Severity:** `MEDIUM` | **Confidence:** `high` | **Category:** `dependencies`
- **Source Scanner:** `shipsafe_dependency_audit` | **Rule ID:** `CVE-2023-32681`
- **Fingerprint:** `cfb1eb80a371f13a465b8dba89003f6fd480f94bcb42fa9f786946657618ece2`
- **Location:** `requirements.txt:2`
- **Description:** Requests leaks Proxy-Authorization headers to destination servers when following redirects.
```json
{
  "package": "requests",
  "installed_version": "2.25.1",
  "vulnerable_below": "2.31.0"
}
```
**Remediation Guidance:**
Upgrade requests to >= 2.31.0.


### Finding 6: Test Suite Regression: 1 Failed Test(s)
- **Severity:** `CRITICAL` | **Confidence:** `high` | **Category:** `tests`
- **Source Scanner:** `shipsafe_test_runner` | **Rule ID:** `TEST-SUITE-FAILURE`
- **Fingerprint:** `86d6bd3f80db9dd1fff1b3b844924b2a995fbb2962daab3fcc9cb15d7aff4c4d`
- **Location:** `tests:1`
- **Description:** Automated test run reported 1 failure(s) and 0 error(s).
```json
{
  "output_excerpt": "-----\nTraceback (most recent call last):\n  File \"D:\\Projects\\Hackathons\\IBM_DB2\\IBM_Db2_TechX_Project_Submission\\submissions\\shipsafe-ai\\fixtures\\vulnerable_project\\tests\\test_api.py\", line 23, in test_account_query_uses_parameter_markers\n    self.assertIn(\"?\", sql)\n    ~~~~~~~~~~~~~^^^^^^^^^^\nAssertionError: '?' not found in \"SELECT BALANCE FROM ACCOUNTS WHERE ACCOUNT_ID = 'ACC-1'\"\n\n----------------------------------------------------------------------\nRan 1 test in 0.001s\n\nFAILED (failures=1)\n"
}
```
**Remediation Guidance:**
Investigate test assertion failures and ensure all regression tests pass before approving Pull Request.


---

## 5. Governing Policies (retrieved from the IBM Db2 vector store)

### Secret and Credential Management Standard (`POL-SEC-002`)
*Source: policies/secrets_management.md | Section: Rule | Db2 cosine similarity: 0.291*

> # Secret and Credential Management Standard  
## Rule
Hardcoded secrets, cloud access keys (for example AWS `AKIA...` keys), API tokens,
GitHub personal access tokens, private keys and database passwords must never be
committed to source code, configuration files or test fixtures.

### IBM Db2 Parameterized SQL and Injection Defense (`POL-DB2-001`)
*Source: policies/db2_sql_parameterization.md | Section: Rule | Db2 cosine similarity: 0.474*

> # IBM Db2 Parameterized SQL and Injection Defense  
## Rule
Every SQL statement sent to IBM Db2 must use parameter markers (`?`) with
`ibm_db.prepare` / `ibm_db.execute`, `ibm_db_dbi` cursors, or an ORM that binds
parameters. Building SQL text with f-strings, `%` formatting, `.format()` or string
concatenation is a release-blocking security violation (SQL injection).

### Safe Process Execution and Dynamic Code Policy (`POL-SEC-004`)
*Source: policies/command_execution.md | Section: Remediation | Db2 cosine similarity: 0.270*

> ## Remediation
Call `subprocess.run([...], shell=False)` with a fixed argument list and validated
arguments. Use `json` or `ast.literal_eval` instead of `eval`, and JSON or Protocol
Buffers instead of `pickle` for data crossing a trust boundary.

### Third-Party Dependency and Known Vulnerability Policy (`POL-DEP-003`)
*Source: policies/dependency_governance.md | Section: Minimum versions | Db2 cosine similarity: 0.290*

> ## Minimum versions
PyYAML must be 5.4 or newer (CVE-2020-14343, arbitrary code execution in `yaml.load`).
requests must be 2.31.0 or newer (CVE-2023-32681, Proxy-Authorization header leak).
urllib3 must be 2.0.7 or newer. cryptography must be 41.0.6 or newer.

### Automated Test and Code Quality Gate (`POL-TST-005`)
*Source: policies/testing_quality_gate.md | Section: Rule | Db2 cosine similarity: 0.327*

> # Automated Test and Code Quality Gate  
## Rule
All automated unit and integration tests must pass with zero failures before merge.
A failing test suite blocks the pull request. Skipped checks must be reported as
skipped, never as passed.

---

## 6. Limitations & Disclaimer
> **Disclaimer:** A clean scan (`PASS`) is an indication of conformance to deterministic engineering > rules and static checks; it does not constitute mathematical proof of software correctness or complete > vulnerability absence. Manual peer review, penetration testing, and load verification remain essential.

*ShipSafe AI report. Assessment persisted in IBM Db2: True.*