# CivicLens AI dashboard (frontend)

React 19 + TypeScript + Vite + Tailwind CSS v4. It talks **only** to the FastAPI backend (`/api/*`); it never connects to IBM Db2 and never holds database credentials. Every number on screen is computed by the backend from Db2 when the page loads.

| View | Route | What it shows |
|---|---|---|
| Intelligence overview | `/` | KPI tiles, complaints by category / severity / day, who wrote the recommendations, top hotspots, live system status, recent audited tool activity |
| Geographic intelligence | `/map` | Leaflet + OpenStreetMap: one marker per complaint (dashed ring = SYNTHETIC), Db2-aggregated hotspot cells, category filters, hotspot window and cluster size |
| Complaints | `/complaints` | Search, filter, sort, paginate, open a record, report a new complaint (analyst) |
| Investigation workspace | `/investigations`, `/investigations/:id` | Create an investigation, attach evidence, run the investigator, inspect status, evidence, audited tool activity and recommendations |
| Human review | `/review` | Reviewer queue, evidence, approve / reject with confirmation; every error state (401, 403, 409, 422, 503) is explained |
| Agent transparency | `/transparency` | LLM status, who actually wrote each recommendation (real LLM, rule-based, or manual), the guard rails, audited activity |

Provenance rule (enforced in one place, `src/lib/generator.ts`): rule-based output is always labelled **“Rule-based · no LLM”**, analyst proposals **“Manual · analyst-written”**, and only output stored with `generator_type = LLM` is called an AI model. A test double is labelled “not a real model”.

## Requirements
* Node.js ≥ 22 and npm.
* A running CivicLens backend (see the project [README](../../README.md)) for anything beyond the unit tests.

## Install and run
```bash
cd submissions/civiclens-ai/src/frontend
npm ci

# development (http://127.0.0.1:5173; /api is proxied to the backend)
npm run dev

# production build, then serve it (http://127.0.0.1:4173; same proxy)
npm run build          # type-checks, then builds into dist/
npm run verify:bundle  # fails if a secret or a database identifier is inside dist/
npm run preview
```
Open the app and sign in with an access token issued by the operator (`CIVICLENS_AUTH_TOKENS` on the backend, see below).

## Configuration
| Setting | Where | Purpose |
|---|---|---|
| `VITE_API_BASE_URL` | build time, **public** | Base URL of the API. Empty (default) means “same origin”, which is what the dev server and `vite preview` provide by proxying `/api`. Set it when the API lives on another origin; the backend must then list this app's origin in `CORS_ORIGINS`. |
| `API_PROXY_TARGET` | dev / preview only | Where `/api` is proxied (default `http://127.0.0.1:8000`). Not exposed to the browser. |

`VITE_*` values are inlined into the browser bundle, so **never put a token, password or database setting in one**. `.env.example` documents this; `npm run verify:bundle` enforces it by scanning `dist/` for the literal values of every secret in the environment and for database identifiers.

## Authentication model (and what is deliberately not done)
* The user pastes a bearer token on the sign-in screen (a password field). It is checked with `GET /api/me` before it is accepted, and held in **`sessionStorage` only**: it is gone when the tab closes, never in the URL, DOM, `localStorage`, cookies or the bundle, and it is sent only to the API (`credentials: 'omit'`).
* A `401` from the server ends the session and returns to sign-in with an explanation. The UI shows controls according to the role, but the server is the authority: every write is re-checked there.
* No token is committed anywhere. There is no shortcut login, no default user and no “remember me”. Static bearer tokens are an interim design for the hackathon demo; a public deployment should front the API with real identity (OIDC) and rate limiting (see the Phase 01B report).
* Production builds carry a Content-Security-Policy `<meta>` (no `unsafe-eval`, scripts from `'self'`, `connect-src` limited to this origin plus the configured API, images from `'self'` and the OpenStreetMap tile host). `frame-ancestors` cannot be set in a `<meta>`; set it (and the other security headers) at the host.

## Tests
| Command | What it runs | Needs |
|---|---|---|
| `npm run typecheck`, `npm run lint` | `tsc --noEmit`, ESLint | nothing |
| `npm test` | Vitest + React Testing Library + MSW: components, views, API client, auth, charts, security rules | nothing |
| `npm run test:live` | The **same TypeScript client** against a real FastAPI + Db2 (zod validates every response shape) | `CIVICLENS_LIVE_API=http://127.0.0.1:8000` and `CIVICLENS_AUTH_TOKENS` (one analyst, two reviewers) |
| `npm run e2e` | Playwright against the **production build**, the real backend and IBM Db2: sign-in, overview, map, complaints, workflow, review, error states, accessibility (axe-core WCAG A/AA), responsive layout | backend running, `CIVICLENS_AUTH_TOKENS`; optional `E2E_DB_DOWN_API` / `E2E_NO_AUTH_API` for the real 503 tests |
| `npm run screenshots` | Captures the evidence screenshots into `../../docs/screenshots/` from the running app | as `e2e`, plus the demo workflow seeded (`src/backend/scripts/seed_demo_workflow.py`) |

Playwright settings worth knowing: it reuses a running preview server (`E2E_NO_SERVER=1` to never start one), traces, videos and automatic screenshots are **off** (they would record the bearer header and the token field), and every test fails on an unexpected browser console error or Content-Security-Policy violation. Rows created by tests are marked `[E2E]` / `[CONTRACT]` and removed with `src/backend/scripts/cleanup_test_data.py`.

```bash
# example: full browser run against a local backend and Db2 (tokens come from the environment, never from the repo)
export CIVICLENS_AUTH_TOKENS='alice:analyst:<token>,rita:reviewer:<token>,omar:reviewer:<token>'
npm run build && npm run preview &          # or: E2E_NO_SERVER=1 npm run e2e   (if preview is already running)
npm run e2e
```
The two extra backends for the 503 tests are ordinary `uvicorn` processes: one started with a wrong `DB2_PORT` (API up, database down) and one without `CIVICLENS_AUTH_TOKENS` (fails closed). Without `E2E_DB_DOWN_API` / `E2E_NO_AUTH_API` those two tests are skipped and reported as skipped.

## Layout
```text
src/
  api/         typed client, zod response schemas (runtime contract check), error mapping, TanStack Query hooks
  auth/        token store (sessionStorage), AuthContext (who am I, capabilities), RequireAuth
  charts/      hand-built SVG/HTML charts: ranked bars, columns, trend line, segmented bar, sparkline (each has a table twin)
  components/  AppShell, Modal, notices, badges, recommendation card, evidence table, audit timeline ...
  lib/         domain constants, generator wording (single source), error wording, validation, formatting
  map/         Leaflet map (direct, not react-leaflet), grid-cell geometry that mirrors the backend
  views/       one file per screen
tests/         Vitest suites (+ MSW handlers, fixtures); tests/live = contract test against the real backend
e2e/           Playwright specs (+ screenshots.spec.ts, which writes docs/screenshots)
```

## Design notes
* Dark charcoal surfaces with copper-orange accents (Tailwind v4 `@theme` tokens in `src/index.css`). The chart palette was validated with the dataviz skill's palette validator (colour-vision-deficiency separation, contrast on the panel surface); the output is saved in `../../docs/evidence/palette_validation.txt`.
* Colour follows the entity (a generator keeps its colour everywhere), severity uses a one-hue ordinal ramp, status colours are reserved and always paired with an icon and a label. Every chart has a “View as table” twin and a hover/focus tooltip.
* Accessible by construction: semantic landmarks, a skip link, visible focus, labelled controls, dialogs that trap and restore focus, `aria-live` for results, no colour-only meaning. axe-core runs in the e2e suite on every view.
* Responsive: the sidebar becomes a scrollable tab strip, tables drop secondary columns on narrow screens instead of scrolling sideways (an e2e check enforces this at 390 px and 820 px), and the map filters collapse behind a button so the map stays on the first screen.

## Known limitations
* Dark theme only; no forced-colors / texture fallback for the charts yet.
* Static bearer tokens and public read endpoints for complaints and hotspots (inherited from Phase 00); no rate limiting. Do not expose this build publicly without the measures above.
* OpenStreetMap tiles are loaded from the public tile server, which is fine for a demo but not for heavy traffic; production needs a tile provider agreement.
