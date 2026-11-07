# Frontend & UX QA

## Method

Playwright (headless Chromium) against the live Next.js app, with the real FastAPI
backend and persisted session #501. Raw results: `reports/ui_qa_results.json`.
Screenshots: `reports/screenshots/ui-desktop.png`, `reports/screenshots/ui-mobile.png`.

## Result summary

| Check | Status | Evidence |
| --- | --- | --- |
| PDF upload via real file picker | PASSED | LoRA PDF selected; 201 response; “already in the evidence library” notice |
| Research text input | PASSED | Paper-demo text loaded |
| Claim cards | PASSED | 4 claim cards for session #501 |
| Classification badges | PASSED | Supported/contradicted/insufficient labels rendered |
| Source passage inspection | PASSED | Evidence panel shows document, page, passage ID |
| Page references | PASSED | “PAGE” displayed in evidence viewer |
| Numerical discrepancy highlighting | PASSED | 8-vs-6 layers shown in numeric-check panel |
| Verification history | PASSED | Session #501 reopened |
| JSON download | PASSED | `aegis-session-501.json` |
| Markdown download | PASSED | `aegis-session-501.md` |
| Evaluation dashboard | PASSED | Actual measured metrics from the results file displayed (run at QA time: macro F1 0.615, Recall@10 0.80) |
| Desktop layout | PASSED | 1560×1180; no console errors |
| Mobile layout | PASSED after fix | 390 px; scrollWidth = 390 = viewport |
| Keyboard navigation | PASSED | Focus reaches nav links, theme toggle, demo buttons |
| Display/backend consistency | PASSED | 4 claims and metrics match API/session data |

## Defects found and fixed

### P2 — Mobile horizontal overflow from a long document title

**Reproduction:** upload a text document whose title contains
`<script>alert('aegis')</script>`; at a 390 px viewport the document scroll width
expanded to **1991 px**, dragging the research-input card off-screen.

**Fix:** added `min-w-0` constraints to the panel, evidence list, list items, and
buttons, plus overflow clipping on the title container. Retest with the same malicious
title and at 390 px: `scrollWidth = innerWidth = 390`; no overflow.

### Test-harness issue (not an application defect)

The first automated upload attempt used `setInputFiles` directly on the hidden input
and missed the transient success banner. Re-testing through the actual **Upload** button
and file chooser produced a 201 response and the dedupe notice. The final QA uses the
real picker path.

## Assertions

- **No mock results in screenshots.** Session #501 is real persisted data from the
  three-paper pipeline; evaluation metrics come from
  `experiments/results/scifact_dev_metrics.json`.
- No horizontal overflow after the fix.
- No browser console errors during the final run.
- Evaluation tables scroll inside their own containers; the page itself does not
  overflow.

## Not tested

- Screen-reader audit and full WCAG conformance.
- Safari/Firefox.
- Touch gestures.
- Very large claim lists (hundreds of claims) in the browser.
- A live verification launched from the UI while the 40-case LLM suite was running; the
  UI was validated against a persisted session to avoid concurrent model contention.
