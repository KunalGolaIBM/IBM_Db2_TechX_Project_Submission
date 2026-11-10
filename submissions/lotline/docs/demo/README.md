# LOTLINE — Official Demonstration Video

> **Mandatory Notice:** Demonstration using synthetic benchmark scenario `INC-2026-001`. Demonstration data for IBM Db2 TechX Summit 2026. Not a real food-safety incident or official FSSAI/FoSCoS filing.

## Video Specifications
- **Format:** MP4 (Video: H.264 / Audio: AAC stereo)
- **Resolution:** 1920×1080 (1080p, 16:9 widescreen, 25 fps progressive)
- **Duration:** 2 minutes 19 seconds (00:02:19.85)
- **File:** `LOTLINE_DEMO_VIDEO.mp4` (8.3 MB)
- **Provenance:** Genuine screen recording captured directly from the live application backed by containerized IBM Db2 12.1.5.0.

## Storyboard Structure
1. **0:00–0:12:** Hook & Title Card — Problem context, IBM Db2 12.1 integration, and mandatory synthetic benchmark scenario notice.
2. **0:12–0:35:** Operational Dashboard — Active incident `INC-2026-001` (GreenLeaf Foods, 500 KG raw spinach intake, Salmonella pathogen screening, 2,400 finished product units commercial exposure).
3. **0:35–0:55:** Recursive Production Traceability — Recursive SQL Common Table Expression (CTE) tracing `RAW-204` -> `WIP-301..303` -> `FIN-401..403`.
4. **0:55–1:15:** LangGraph Multi-Agent Investigation — Intake, Traceability, Risk Assessment, and Response Planning agents grounding interpretations strictly on Db2 records.
5. **1:15–1:40:** Recall Execution Control Tower:
   - *Tab 1 (Mass Balance):* 50.0 KG unexplained raw mass variance surfaced as `UNRECONCILED` (no automated balancing).
   - *Tab 2 (Consignee Comms):* Notice lifecycles and acknowledgments across 4 retail partners.
   - *Tab 3 (Logistics Interception):* Real-time cargo halting for active shipment `SHP-002` (200 units `FIN-401`).
   - *Tab 4 (Product Recovery):* Non-overlapping separation between warehouse quarantine (1,350 units) and trade circulation returns (0 / 1,050 units, 0.0%).
   - *Tab 5 (Dispositions):* Controlled destruction authorizations requiring certified evidence.
   - *Tab 6 (FSSAI FoSCoS Tracker):* 14 Schedule-I statutory items and synthetic demo portal reference.
   - *Tab 7 (Effectiveness & Closure):* 12 statutory indicators and rejection of unauthorized recall closure.
6. **1:40–2:00:** Human-in-the-Loop Governance & Audit Trail — Human operator confirmation modal, ACID Db2 atomic transaction, and append-only audit trail in `LOTLINE_APP.AUDIT_LOG`.
7. **2:00–2:15:** Official Regulatory PDF Dossier — Real-time compilation of 6-page A4 vector dossier with two-pass SHA-256 tamper-evident digest.
8. **2:15–2:20:** Outro — Architecture summary and repository links.
