# Pitch and Walkthrough Guide

## 30-second pitch

Privacy teams need to find personal data across related tables, understand consent history, and estimate the impact of a rights request before changing records. Db2 Privacy Copilot reads schema context from IBM Db2, surfaces likely personal data, and prepares a reviewable rights-request plan. A DPO approves the plan, deterministic SQL checks guard execution, and Db2 records the change with an audit event.

## Five-minute presentation

Use the seven-slide deck in `pitch/Db2_Privacy_Copilot_Pitch_Aryan_Rane.pptx`. Speaker notes include a short talk track and evidence boundary for each slide.

### If the local Db2 stack is running

1. Open the workspace and show schema discovery.
2. Run classification and explain that labels are candidates for review.
3. Open consent history for a synthetic patient.
4. Create a rights request and show the dry-run plan, impact estimate, retention context, and plan hash.
5. Sign in as DPO, review and approve the plan.
6. Show the resulting status and verify the audit chain.

Use synthetic records only. Do not describe the local environment as connected to Db2 unless `/healthz` confirms the Db2 service level and the application is configured with `DB_MOCK=0`.

### If the local Db2 stack is not running

Present the architecture and code path in the repository, then open the linked GitHub Actions run and show the successful `integration` job. State that the CI result applies to commit `be74dc2` on Nov 10, 2026. Do not claim a live local run, and do not show mock output as real Db2 evidence.

## Two-minute code walkthrough

- `app/discovery.py`: reads Db2 catalog metadata and foreign-key relationships.
- `app/classify.py` and `app/vector_store.py`: combine value patterns with taxonomy matching.
- `app/consent.py`: reads and writes consent history using Db2 temporal tables.
- `app/erasure.py`: creates a dry-run plan, hashes the plan, checks approval, and executes approved changes transactionally.
- `app/guardrail.py`: validates SQL shape, parameterization, scope, and approval state.
- `app/audit.py`: appends and verifies SHA-256 linked events.

## If asked whether it runs

> “The CI workflow ran the integration job against a real Db2 container and succeeded on commit `be74dc2`. I’m not running a local Db2 stack live in this session. I can show the CI run and walk through the implementation.”

Only offer a later live run if you are willing and able to arrange one.

## Scope to state clearly

The dataset is synthetic. The application supports selected DPDP-related decision-support workflows. Retention rules require owner review, and the current role selector is not an organization identity provider. Avoid claims of production readiness, legal certification, exact test totals, coverage percentages, or security-block percentages unless you have current evidence for them.

## CI evidence

[Open successful GitHub Actions run #22](https://github.com/dreameterftw/db2-privacy-copilot/actions/runs/42799280571)

- Commit: `be74dc2` on `main`
- Date: Nov 10, 2026
- `quality`: succeeded in 3m 02s
- `integration`: succeeded in 7m 40s
- This evidence does not cover local edits made after that commit.
