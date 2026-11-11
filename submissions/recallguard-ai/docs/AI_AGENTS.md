# AI Agents

## Design principle
**Facts from Db2, narrative from AI, verification from Db2 again.** Agents cannot invent suppliers, batch IDs, quantities, retailers or lab results. Every such value in an agent output comes from a Db2 result set or from verbatim document text, and the Verification Agent checks all of it independently.

## Pipeline (`app/agents/orchestrator.py`)
Five agents run in sequence and share one context (`ctx`). Each agent's row in `AGENT_INVESTIGATIONS` moves `QUEUED → RUNNING → COMPLETED/FAILED`, carrying its structured JSON output and a timestamped execution log. The UI polls this table to show real progress.

| # | Agent | Input | Db2 work | Output model |
|---|---|---|---|---|
| 1 | Investigation | incident, linked documents | `EVIDENCE_DOCUMENTS`, `QUALITY_REPORTS` | `InvestigationFindings`: source, supplier, lab findings with page citations, extracted lots/dates, **conflicts**, missing evidence |
| 2 | Supply Chain | suspected source | 6 recursive/aggregate traceability queries | `SupplyChainFindings`: direct and indirect batches, products, locations with units, **data gaps**, queries executed |
| 3 | Risk Assessment | impact counts, gaps, evidence status | — | `RiskAssessment`: score, class, 6 factor contributions, completeness, confidence, disclaimer |
| 4 | Recall Planning | impact rows, risk, evidence | same-SKU exclusion query | `RecallPlan`: batch × location items (priority, basis, reason, lineage path, evidence refs), simulated notices, excluded batches, report |
| 5 | Verification | plan + context | reverse recursion, per-batch lineage, raw shipment joins, ID existence | `VerificationReport`: checks, verdict, unsupported claims, missing/extraneous items, human-review reasons |

Incident transitions made by agents: `INVESTIGATING → EVIDENCE_REVIEW` (after agent 1) and `→ RECALL_RECOMMENDED` (after agent 4). Only humans move a recall beyond `PENDING_APPROVAL`.

## Modes
| Mode | When | What happens |
|---|---|---|
| `CREWAI_LLM` | `LLM_PROVIDER` + `LLM_MODEL` + key are set | For each step, a CrewAI `Agent` (role/goal/backstory, tools `db2_trace_impact` + `evidence_search`) runs a `Task` with `output_pydantic`. The narrative is merged into the fact model; facts are unchanged |
| `DETERMINISTIC_FALLBACK` | no LLM configured, or an LLM step fails | Deterministic Db2-backed agents. Labelled on every card: "Deterministic fallback · not an LLM". The API `mode_note` says "NOT an LLM response" |

If an LLM call fails mid-run, that step is stored as `DETERMINISTIC_FALLBACK` and the log records why. The run continues.

## Verification checks
1. The forward trace equals an **independent reverse trace** (upstream from every finished batch). Failure is a BLOCKER.
2. Every descendant finished batch has a recall item. Failure is a BLOCKER.
3. Every planned batch descends from the source, checked with a per-batch lineage query. Failure is a BLOCKER.
4. Every batch-location item is backed by a shipment record or is the producing facility. Failure is a BLOCKER.
5. Every recipient of an affected batch is notified (non-recursive join). Failure is a BLOCKER.
6. Units located reconcile to units produced. Failure is a WARNING.
7. No identifier in narrative text is absent from Db2. Failure is a BLOCKER.
8. Contamination is lab-confirmed. Failure is a WARNING.
9. No conflicting evidence. Failure is a WARNING.
10. Traceability records are complete. Failure is a WARNING.

The verdict is `FAIL` / `PASS_WITH_WARNINGS` / `PASS`. `requires_human_review` is always `true`.

The tests inject faults (an unrelated batch, a dropped batch, an invented `PB-2026-9999`) and assert that each one is caught.

## Tested
- Deterministic agents end to end on the tomato scenario.
- Real `Crew.kickoff()` with a local stub `BaseLLM`: a single step, and the full orchestrator in `CREWAI_LLM` mode (narrative merged, Db2 facts untouched).
- Construction of CrewAI Agent/Task/Crew objects with the Db2 tools.

A hosted LLM was **not** called in the build environment (no API key).
