# Demo Guide — Tomato Contamination (TOM-2026-041)

**Setup:**
1. Run `docker compose up --build`, or start the backend and frontend locally (see README).
2. Open http://localhost:5173.
3. Confirm that the top-bar badge reads **IBM Db2 · connected**. "DEV MODE" means you are not on Db2.

## 1. Run the demo (≈2 seconds of real work)
Click **Run Tomato Contamination Demo**. The panel shows what each API call actually returned:

1. **Incident registered.** The ID is shown; the supplier, *Valle Rosso Tomato Cooperative*, is resolved from Db2 using the lot.
2. **Lab report uploaded.** `lab_report_TOM-2026-041.pdf` yields 17 grounded claims, including 3 positive results, each with page and section.
3. **Five agents run.** The tiles turn green as rows in `AGENT_INVESTIGATIONS` complete. Result: risk 84/100 CRITICAL, verification PASS_WITH_WARNINGS.
4. **Recall plan generated.** Class I, 40 items, 42,000 units, 6 same-SKU batches excluded.
5. **Waiting for human approval.**

## 2. Talking points
- **Supply-chain graph:** open it from the panel. Red nodes are reachable from the source.
  - Point out the 3-level path TOM-2026-041 → PB-1001 → PB-1003 → PB-1007, ending in the ready meal in Delhi and Kolkata.
  - The dashed amber edge (PB-1001 → PB-1006) is an **UNVERIFIED** manual record. It is kept in scope.
  - The "Db2 queries executed" panel lists every recursive statement with row counts.
- **AI Investigation Centre:**
  - Investigation Agent → *Uncertainty & gaps* shows the **conflict**: the supplier COA says "not detected (n=1)" while the lab found 3 of 5 positive.
  - Verification Agent shows 10 checks, including *forward trace == independent reverse trace*.
- **Recall plan:**
  - Each row has its reason (lineage path, Db2 depth, units, location) and evidence refs (shipment IDs, lab page).
  - The *Excluded* tab lists PB-2026-1011/1013 (same Marinara and Pasta Sauce SKUs, from the clean lot TOM-2026-042), which is why this is a **targeted** recall.
  - *Instructions* shows the generated retailer notices, all marked SIMULATED.
- **Risk card:** six factors with weights and reasons. Uncertainty adds risk, never subtracts it. The disclaimer states that this is not a probability of illness.

## 3. Human approval
1. As QA Analyst, the Approve button is disabled and a hint is shown.
2. Switch the top-bar role to **Recall Manager**, add a comment, then click **Approve & send simulated notices**.
3. The incident moves to EXECUTING, and 31 NOTIFY plus quarantine/recover actions are created.
4. Open **Monitor execution** → **Simulate partner responses** to see acknowledgements, quarantine progress, recovered units and the audit timeline.

## 4. Negative checks worth showing
- Trace **PB-2026-1030** (butter biscuits). Nothing tomato-related appears.
- Create an incident on `NOP-2026-999`. The API returns 404, because Db2 has no such lot and orphan incidents are refused.
- **Settings → Reset demo incidents** removes only `is_demo` data.
