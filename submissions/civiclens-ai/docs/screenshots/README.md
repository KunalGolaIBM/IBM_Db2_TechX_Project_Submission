# Screenshots

Genuine screenshots of the running CivicLens AI dashboard: the **production build**, the **real FastAPI backend**, **real IBM Db2** rows and **real OpenStreetMap tiles**. Nothing is mocked, composited or edited. All complaint data is **SYNTHETIC** and labelled as such in the UI.

They are produced by `src/frontend/e2e/screenshots.spec.ts` (`npm run screenshots`) at a device scale factor of 2; `manifest.json` records, for every file, what it shows, who was signed in, the viewport, the pixel size, a SHA-256 and the capture time. Each screenshot asserts that the thing its caption promises is on screen before it is taken (for example, a decision result must be in the viewport), so a capture cannot silently miss its subject. Bearer tokens never appear: the sign-in box is a password field, and tokens are not rendered anywhere in the UI.

Regenerate: seed the demo workflow (`python src/backend/scripts/seed_demo_workflow.py`), start the API and the preview server, then run `npm run screenshots` in `src/frontend`. Afterwards reset with `python src/backend/scripts/cleanup_test_data.py --workflow --yes`.

## Reading the data (desktop, 1440 px wide)

### 01-sign-in

Sign-in: the access token goes in a password field and is kept for the browser tab only.

*not signed in · 2880×1800px · 125 KB*

![Sign-in: the access token goes in a password field and is kept for the browser tab only.](01-sign-in.png)

### 02-intelligence-overview

Intelligence overview: every figure is an aggregate query over IBM Db2; synthetic records are counted and labelled separately.

*signed in as **alice (analyst)** · 2880×4724px · 963 KB*

![Intelligence overview: every figure is an aggregate query over IBM Db2; synthetic records are counted and labelled separately.](02-intelligence-overview.png)

### 03-geographic-intelligence

Geographic intelligence: OpenStreetMap basemap, one marker per complaint (dashed ring = synthetic) and Db2-aggregated hotspot cells.

*signed in as **alice (analyst)** · 2880×2542px · 1771 KB*

![Geographic intelligence: OpenStreetMap basemap, one marker per complaint (dashed ring = synthetic) and Db2-aggregated hotspot cells.](03-geographic-intelligence.png)

### 04-geographic-hotspot-selected

Category filter (water leak) applied and the hotspot selected: the map centres on the Db2 grid cell and its complaints.

*signed in as **alice (analyst)** · 2880×2542px · 1634 KB*

![Category filter (water leak) applied and the hotspot selected: the map centres on the Db2 grid cell and its complaints.](04-geographic-hotspot-selected.png)

### 05-complaints

Complaint browser: search, category and record-type filters, severity, and SYNTHETIC badges on every demo record.

*signed in as **alice (analyst)** · 2880×2000px · 455 KB*

![Complaint browser: search, category and record-type filters, severity, and SYNTHETIC badges on every demo record.](05-complaints.png)

### 06-complaint-detail

A complaint record opened from the browser, with a link to its place on the map.

*signed in as **alice (analyst)** · 2880×2000px · 402 KB*

![A complaint record opened from the browser, with a link to its place on the map.](06-complaint-detail.png)

### 07-investigations

Investigation workspace: investigations in every lifecycle state.

*signed in as **alice (analyst)** · 2880×1600px · 274 KB*

![Investigation workspace: investigations in every lifecycle state.](07-investigations.png)

### 08-investigation-results

An investigated case: evidence from Db2, the audited tool calls the rule-based investigator made, its recommendations (labelled "Rule-based · no LLM") and the reviewers' decisions.

*signed in as **alice (analyst)** · 2880×5798px · 1569 KB*

![An investigated case: evidence from Db2, the audited tool calls the rule-based investigator made, its recommendations (labelled "Rule-based · no LLM") and the reviewers' decisions.](08-investigation-results.png)

### 09-investigation-run-options

An open investigation: the run options say plainly that no language model is configured, so Auto mode will use the labelled rule-based fallback.

*signed in as **alice (analyst)** · 2880×3794px · 609 KB*

![An open investigation: the run options say plainly that no language model is configured, so Auto mode will use the labelled rule-based fallback.](09-investigation-run-options.png)

### 10-human-review-queue

Human review as a reviewer: the proposal, who or what wrote it, the evidence behind it, and the decision controls.

*signed in as **rita (reviewer)** · 2880×2590px · 477 KB*

![Human review as a reviewer: the proposal, who or what wrote it, the evidence behind it, and the decision controls.](10-human-review-queue.png)

### 11-human-review-decided

A decided recommendation: the reviewer, the time and the comment are recorded and the decision cannot be changed.

*signed in as **rita (reviewer)** · 2880×1800px · 476 KB*

![A decided recommendation: the reviewer, the time and the comment are recorded and the decision cannot be changed.](11-human-review-decided.png)

### 12-human-review-analyst-readonly

An analyst can read the review queue but is shown no approve or reject controls (and the server would refuse them: 403).

*signed in as **alice (analyst)** · 2880×1600px · 383 KB*

![An analyst can read the review queue but is shown no approve or reject controls (and the server would refuse them: 403).](12-human-review-analyst-readonly.png)

### 13-agent-transparency

Agent transparency: no language model is configured, so every recommendation is shown as rule-based or manual; the guard rails and the audited tool activity are listed.

*signed in as **alice (analyst)** · 2880×4178px · 799 KB*

![Agent transparency: no language model is configured, so every recommendation is shown as rule-based or manual; the guard rails and the audited tool activity are listed.](13-agent-transparency.png)

## The investigation workflow, driven through the UI

### 18-new-investigation

Creating an investigation: a title and the question it should answer.

*signed in as **alice (analyst)** · 2880×1600px · 272 KB*

![Creating an investigation: a title and the question it should answer.](18-new-investigation.png)

### 19-attach-evidence

Attaching evidence: complaints are picked from the database; synthetic records are badged and attached ones are marked.

*signed in as **alice (analyst)** · 2880×1600px · 260 KB*

![Attaching evidence: complaints are picked from the database; synthetic records are badged and attached ones are marked.](19-attach-evidence.png)

### 20-investigation-run-result

After Auto mode ran: the result says the rule-based fallback was used and why, the evidence, audited tool calls and the proposed recommendation (still awaiting a reviewer).

*signed in as **alice (analyst)** · 2880×4772px · 1090 KB*

![After Auto mode ran: the result says the rule-based fallback was used and why, the evidence, audited tool calls and the proposed recommendation (still awaiting a reviewer).](20-investigation-run-result.png)

### 21-review-confirm

Approving asks for confirmation and states who the decision will be recorded as.

*signed in as **rita (reviewer)** · 2880×2000px · 303 KB*

![Approving asks for confirmation and states who the decision will be recorded as.](21-review-confirm.png)

### 22-review-approved

Success: the decision, the reviewer and the time are recorded in Db2 and in the audit log.

*signed in as **rita (reviewer)** · 2880×2000px · 447 KB*

![Success: the decision, the reviewer and the time are recorded in Db2 and in the audit log.](22-review-approved.png)

## Error states, each provoked against the real backend

### 23-error-409-already-decided

409: reviewer B acted on a stale view; Db2's compare-and-set refused the second decision and the first one stands.

*signed in as **omar (reviewer)** · 2880×2000px · 444 KB*

![409: reviewer B acted on a stale view; Db2's compare-and-set refused the second decision and the first one stands.](23-error-409-already-decided.png)

### 24-error-403-forbidden

403: the request carried an analyst token; the server refused it and nothing changed.

*signed in as **rita (reviewer)** · 2880×2000px · 501 KB*

![403: the request carried an analyst token; the server refused it and nothing changed.](24-error-403-forbidden.png)

### 25-error-422-validation

422: a rejection without a comment is refused by the server, with the reason in words.

*signed in as **rita (reviewer)** · 2880×2000px · 510 KB*

![422: a rejection without a comment is refused by the server, with the reason in words.](25-error-422-validation.png)

### 26-error-401-signed-out

401: the server rejected the token, so the session ended and the user is asked to sign in again.

*not signed in · 2880×1800px · 150 KB*

![401: the server rejected the token, so the session ended and the user is asked to sign in again.](26-error-401-signed-out.png)

### 27-error-503-database-unavailable

503: the API answers but the database does not. The message is generic (no host, port or credentials) and no unreliable figures are shown.

*signed in as **alice (analyst)** · 2880×1600px · 123 KB*

![503: the API answers but the database does not. The message is generic (no host, port or credentials) and no unreliable figures are shown.](27-error-503-database-unavailable.png)

### 28-error-503-auth-not-configured

503: a backend with no access tokens configured refuses everyone instead of letting them in.

*not signed in · 2880×1600px · 159 KB*

![503: a backend with no access tokens configured refuses everyone instead of letting them in.](28-error-503-auth-not-configured.png)

## Phone (390 px wide)

### 14-phone-overview

Phone: the overview reflows to one column; charts stay readable and keep their data tables.

*signed in as **alice (analyst)** · 780×8400px · 738 KB*

![Phone: the overview reflows to one column; charts stay readable and keep their data tables.](14-phone-overview.png)

### 15-phone-map

Phone: the filters start collapsed so the map is on the first screen; hotspot cells and complaint markers are plotted on it.

*signed in as **alice (analyst)** · 780×3742px · 1018 KB*

![Phone: the filters start collapsed so the map is on the first screen; hotspot cells and complaint markers are plotted on it.](15-phone-map.png)

### 16-phone-investigation

Phone: an investigation with evidence, recommendations and the audit trail.

*signed in as **alice (analyst)** · 780×7600px · 850 KB*

![Phone: an investigation with evidence, recommendations and the audit trail.](16-phone-investigation.png)

### 17-phone-review

Phone: the review queue and a recommendation with its decision controls.

*signed in as **rita (reviewer)** · 780×3912px · 404 KB*

![Phone: the review queue and a recommendation with its decision controls.](17-phone-review.png)
