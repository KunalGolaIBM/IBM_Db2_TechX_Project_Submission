# CarbonNova

CarbonNova is a React/Vite frontend and Express API prototype for agricultural parcel mapping, field-sensor monitoring, deterministic carbon-indicator calculations, Nemotron-powered evidence interpretation, and auditable exports. It is intended as a decision-support and project-preparation tool; it does **not** certify or issue carbon credits.

## Current capabilities

- Interactive Leaflet map with Esri World Imagery and OpenStreetMap terrain layers, Nominatim place search, coordinate search, and browser-permission GPS location.
- Draw and edit user parcel polygons; geodesic area and perimeter; save, reopen, rename, and delete records in the existing JSON database. Saving creates a linked project in data-collection status. Mapped boundaries are not legal/cadastral surveys.
- Deterministic engine kept separate from AI. Its current outputs include SOC stock based on land-type default factors, respiration flux, and indicative modelled sequestration. It explicitly labels defaults, missing laboratory measurements, and limitations. This is a prototype formula and is **not** a validated project-credit methodology; AI does not calculate carbon.
- Carbon Evidence Ledger snapshots persist assessment IDs, linked parcel/project, input observation IDs, source labels, method version, assumptions, missing inputs, limitations, pending human review, and a revision chain.
- Existing sensor-ingest API and demo sensor readings. Seeded/demo readings are synthetic and labelled; they are not evidence. PDF and CSV exports are built by the server from saved project data.
- AI assistant is data-grounded through server routes, with provider errors surfaced (never substituted with fake answers).

## Architecture

- `src/`: React 19, React Router, TanStack Query, Zustand, Tailwind, Leaflet/react-leaflet and Recharts.
- `server/`: Express 5 API, OpenAI-compatible SDK client, JSON-file persistence (`server/data/db.json`), deterministic science engine, project/parcel/assessment/report/AI endpoints.
- Parcel persistence extends the existing JSON store additively (`parcels` and `assessments` arrays); older stores load with empty arrays. Back up `server/data/db.json` before deploying changes.
- This repository's auth UI is a prototype, not backend authentication. The current API's `user-1` owner filter is a demo isolation convention only, not a security boundary. Do not expose it to real users or sensitive data until authenticated server-side identity and authorization are implemented.

## Requirements and local setup

Node.js 20.19+ or 22.12+ (Vite 8 requirement), npm.

```bash
npm install
npm --prefix server install
npm run dev:server
# In a second terminal:
npm run dev
```

Open the Vite URL printed by the frontend (normally `http://localhost:5173`). The API listens at `http://localhost:4000`; health endpoint: `http://localhost:4000/api/health`.

Production frontend build and static preview:

```bash
npm run build
npm run preview
```

Run backend tests:

```bash
npm --prefix server test
```

Lint:

```bash
npm run lint
```

`VITE_API_URL` is an optional frontend build-time API origin, defaulting to `http://localhost:4000/api`. It is public configuration; never put credentials in Vite variables.

## Nebius Token Factory / NVIDIA Nemotron

The Nebius route uses `server/lib/nebius.js` and OpenAI-compatible chat completions. Default endpoint: `https://api.tokenfactory.nebius.com/v1/`, with bearer authentication supplied by the OpenAI SDK. Default model: `nvidia/Nemotron-3_5-Lightning`. `NEBIUS_MODEL` and `NEBIUS_BASE_URL` can override those values. `NEBIUS_TIMEOUT_MS` sets the SDK timeout (default 30 seconds). The model is selected/configured in application code; `/api/ai/status` performs a best-effort model-list lookup but cannot prove inference will succeed.

Nebius uses a **Nebius Token Factory API key**, not an NVIDIA Build API key. Put the key in `server/.env` (or project-root `.env`, already loaded by the existing server setup), and never add it to frontend environment variables:

```dotenv
NEBIUS_API_KEY=replace-with-a-Nebius-Token-Factory-key
# Optional:
NEBIUS_MODEL=nvidia/Nemotron-3_5-Lightning
NEBIUS_TIMEOUT_MS=30000
```

No key is configured in the current environment, so a real provider inference call has **not** been verified and hackathon compliance is not claimed. The root `.env` contains an NVIDIA Build credential; it was not printed, altered, or treated as a Nebius credential. The existing alternate NVIDIA Build API route is retained separately but is not the Nebius integration.

Provider references checked for this implementation:

- [Nebius Token Factory Quickstart](https://docs.tokenfactory.nebius.com/quickstart) documents the OpenAI-compatible base URL and `NEBIUS_API_KEY` setup.
- [Nebius Token Factory August 2026 deprecation notice](https://docs.tokenfactory.nebius.com/august-2026-deprecation-notice) names `nvidia/Nemotron-3_5-Lightning` as the recommended serverless replacement for several models. Use `/api/ai/status` and an actual inference call with the configured account to confirm current account-level availability.

Errors distinguish missing configuration, authentication, unknown models, rate limiting, timeout and upstream/network failures. API-key values are not returned in status responses or intentionally logged. AI text is a draft interpretation, not a measurement, validation, verification or credit issuance.

## Data sources and scientific scope

- Parcels: user-drawn WGS84 latitude/longitude vertices; area is calculated on the server with a spherical geodesic polygon formula. Mapping date and method are stored. Device GPS locates the browser only; it does not establish land ownership.
- Base map: Esri World Imagery and OpenStreetMap tiles are third-party display services; imagery age/resolution varies by tile. Place search uses OpenStreetMap Nominatim. The app currently does not calculate NDVI or retrieve satellite acquisition records, historical imagery, or land-cover classifications; these states are explicitly unavailable, not simulated.
- Sensor readings: device-ingest endpoint or labelled synthetic seed data. No laboratory SOC samples are bundled.
- Engine: see `server/lib/carbonEngine.js` and `METHODOLOGY`. The simplified formulas/defaults and uncertainty ranges are prototype decision-support assumptions, not independently validated coefficients or a registry methodology. Soil respiration is a flux and is kept separate from carbon stock and sequestration. Missing soil-lab evidence must be supplied before interpreting the stock output as measured.

## API workflow

- `GET /api/parcels?owner_id=user-1`, `POST /api/parcels`, `PATCH /api/parcels/:id`, `DELETE /api/parcels/:id?owner_id=user-1`
- `GET /api/projects`, existing sensor/monitoring/carbon and reports endpoints
- `POST /api/projects/:id/assessments`, `GET /api/projects/:id/assessments`
- `POST /api/projects/:id/ai/ask` (Nebius), `GET /api/ai/status`
- Existing alternate NVIDIA Build integration remains at `/api/projects/:id/ai/nvidia/ask` and `/api/ai/nvidia/status`.

Parcel/assessment endpoints use the prototype `user-1` owner convention; it is not authenticated authorization. Never rely on it as a production security control.

## Three-minute demonstration

1. Start API and UI; check `/api/health` and `GET /api/ai/status`. Explain that synthetic demo sensor values are labelled as such.
2. Open **Land Analysis**, search a real place or coordinates, choose satellite/terrain, draw at least three vertices, name and save the parcel. Show calculated area, perimeter, mapping date and the not-legally-verified notice. Reload or switch away and reopen the saved parcel.
3. Open the linked Carbon Estimate. Inspect source label, deterministic engine outputs and missing SOC/bulk-density lab evidence. Do not describe these as measured credits.
4. Save an assessment snapshot and open its ledger record: assessment/revision ID, observation sources, formula version, missing inputs, limitations and human-review-pending status.
5. With a configured Nebius key, send a question about those actual inputs and identify the AI response as an interpretation. Without the key, demonstrate the explicit configuration error (not a fabricated response).
6. Download the carbon CSV or PDF from the saved project; show that it carries the data-source and methodology limitations.

## Known limitations / not yet implemented

- No actual Nebius key is configured here; live inference and account-level model access remain untested. No official hackathon rules have been independently confirmed here, so submission compliance cannot be asserted.
- No authentication-backed authorization, production rate limiting, upload pipeline, user-specific ownership claims, or production database/migrations.
- No real environmental-data API/NDVI/historical satellite or weather integration, lab evidence workflow, independent review/signature workflow, registry integration, credit issuance/retirement records, or validated methodology.
- Carbon calculations retain simplified existing defaults and illustrative rates and must not be used for credit claims. Confidence ranges are model assumptions, not empirically calibrated probabilities.
- Parcel boundary import, topology editing beyond point re-draw, and cadastral verification are not included.
- Browser mapping and GPS require network access; GPS additionally requires explicit browser permission. External map services may impose their own usage policies/rates.

## License and submission

No project license file is currently present. Confirm the desired open-source license and add its complete approved text before distributing this software. A public demo deployment is not configured or claimed. Before hackathon submission, check the official current submission rules and required NVIDIA/Nebius account/model constraints, add a valid Nebius key in the server environment, make a live inference call from the application, and record the observed provider/model response.
