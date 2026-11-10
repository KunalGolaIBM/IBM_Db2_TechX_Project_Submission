# LOTLINE — Verified Evidence Screenshots Index

> **Synthetic Benchmark Notice:** All captured screens demonstrate synthetic benchmark scenario `INC-2026-001` (source lot `RAW-204`, supplier GreenLeaf Foods, Maharashtra, India). Demonstration data for IBM Db2 TechX Summit 2026 judging; not a real food-safety incident or official FSSAI filing.

| Filename | Resolution | Description & Provenance | Single Source of Truth |
|:---|:---|:---|:---|
| `01-overview-desktop.png` | 1920×1080 | LOTLINE Operational Recall Dashboard & Soffit 002 visual identity | IBM Db2 `INCIDENTS` & `LOTS` |
| `02-overview-mobile.png` | 390×844 | Mobile responsive view with full KPI telemetry | IBM Db2 live query response |
| `03-traceability-lineage.png` | 1920×1080 | Recursive production lineage: RAW-204 → WIP-301/302/303 → FIN-401/402/403 | Recursive SQL CTE on `LOT_LINEAGE` |
| `04-agent-findings.png` | 1920×1080 | Four LangGraph agents with Db2 verified database evidence badges | Gemini 3.5 Flash + Db2 Grounding |
| `05-agent-action-plan.png` | 1920×1080 | Structured mitigation actions (ACT-001..004) with governance status | `LOTLINE_APP.RECALL_ACTIONS` |
| `06-human-approval-gate.png` | 1920×1080 | Human-in-the-loop safety authorization modal with audit confirmation | Human operator decision gate |
| `07-audit-timeline.png` | 1920×1080 | Persistent append-only audit trail with actor, timestamp & details | `LOTLINE_APP.AUDIT_LOG` |
| `08-control-tower-mass-reconciliation.png` | 1920×1080 | Tab 1: Deterministic raw mass balance showing 50.0 KG UNRECONCILED | 500 KG intake - 400 KG WIP - 50 KG Q |
| `09-control-tower-logistics.png` | 1920×1080 | Tab 3: Active logistics interception for SHP-002 (200 units FIN-401) | `LOTLINE_APP.LOGISTICS_INTERVENTIONS` |
| `10-control-tower-recovery-disposition.png` | 1920×1080 | Tab 4: Physical recovery matrix separating warehouse containment from trade returns | Distinct non-overlapping recovery fields |
| `11-control-tower-fssai-tracker.png` | 1920×1080 | Tab 6: 14 Schedule-I statutory items & FoSCoS demo tracking reference | FSSAI Food Recall Regulations 2017 |
| `12-control-tower-closure.png` | 1920×1080 | Tab 7: 12 statutory effectiveness metrics & server-computed closure blockers | Rejection of unauthorized recall closure |
| `13-dossier-page-1.png` | A4 (150 DPI) | Dossier Page 1: Executive Incident Brief & Exposure Summary | ReportLab A4 Vector Dossier |
| `14-dossier-page-2.png` | A4 (150 DPI) | Dossier Page 2: Contamination Traceability Tree & Mass Reconciliation | ReportLab A4 Vector Dossier |
| `15-dossier-page-3.png` | A4 (150 DPI) | Dossier Page 3: Finished Goods Exposure & Retail Shipment Distribution | ReportLab A4 Vector Dossier |
| `16-dossier-page-4.png` | A4 (150 DPI) | Dossier Page 4: Human-in-the-Loop Response Actions & Operator Attribution | ReportLab A4 Vector Dossier |
| `17-dossier-page-5.png` | A4 (150 DPI) | Dossier Page 5: Closed-Loop Physical Recovery & Controlled Disposition | ReportLab A4 Vector Dossier |
| `18-dossier-page-6.png` | A4 (150 DPI) | Dossier Page 6: Immutable Db2 Audit Evidence & SHA-256 Tamper Digest | ReportLab A4 Vector Dossier |

---
*Generated directly from the running LOTLINE application backed by IBM Db2 12.1.5.0.*
