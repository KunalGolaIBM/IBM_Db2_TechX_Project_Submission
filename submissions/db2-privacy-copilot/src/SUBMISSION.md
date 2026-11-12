# Db2 Privacy Copilot — Pitch Brief

## Project

**Db2 Privacy Copilot** is a decision-support workspace for privacy operations built around IBM Db2.

## Problem

Privacy teams can struggle to locate personal data across related tables, understand consent history, and estimate the impact of a rights request. Manual investigation can be slow and may leave the reasoning and approvals difficult to audit.

## Proposed solution

The application reads Db2 catalog metadata to map tables and relationships, surfaces likely personal data for review, and records consent history. It prepares a dry-run rights-request plan with affected tables and estimated impact. An authorized reviewer examines the plan, and deterministic SQL checks validate the approved statements before execution. The action and its audit event are committed together.

## Intended beneficiaries

Data protection officers, privacy operations teams, Db2 database administrators, and developers evaluating privacy workflows.

## What is implemented

- Streamlit workspace and FastAPI endpoints
- Catalog-based schema discovery and relationship mapping
- Value-pattern and semantic PII classification
- Temporal consent records
- Rights-request planning, reviewer approval, and plan-hash verification
- Deterministic SQL guardrails and transactional execution
- SHA-256 linked audit events with chain verification

## How Db2 is used

Db2 stores the application and synthetic clinic records, consent history, request state, taxonomy vectors, and audit events. The application reads `SYSCAT` views for schema metadata. Temporal tables preserve consent history. The `langchain-db2` DB2VS integration supports semantic PII taxonomy lookup on Db2 12.1.2 or newer. Transactions keep approved data changes and audit writes atomic.

## Walkthrough

1. Discover tables and foreign-key relationships.
2. Classify likely PII and review confidence signals.
3. Inspect consent history for a synthetic subject.
4. Create a rights request and inspect the dry-run plan and plan hash.
5. Review and approve as DPO.
6. Verify the resulting audit chain.

## Current scope and limitations

The clinic dataset is synthetic. The application supports selected DPDP-related workflows; it does not certify legal compliance or replace legal review. Retention rules require owner verification. The current role selector is not an organization identity provider. Use real personal data only after adding production authentication, reviewing access controls, and completing a security review.

## Verification evidence

GitHub Actions CI run #22 succeeded on Nov 10, 2026 for commit `be74dc2` on `main`. Both the quality job and the live Db2 integration job succeeded. This result applies to that commit. Local workspace edits made after the run are not covered by it.

Run: https://github.com/dreameterftw/db2-privacy-copilot/actions/runs/42799280571
