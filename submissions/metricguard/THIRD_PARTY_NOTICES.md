# Third-party notices

MetricGuard's own code is Apache-2.0 (`LICENSE`, `NOTICE`). The repository vendors no third-party source code. The packages below are installed from PyPI and npm at setup time and keep their own licenses. Versions are the ones installed and checked on 2026-11-07; licenses were read from each package's installed metadata.

## Runtime, Python (`backend/pyproject.toml`)

| Component | Version | License | How it is used |
|---|---|---|---|
| ibm_db (bundles IBM Data Server Driver / clidriver) | 3.3.0 | Apache-2.0 (clidriver: IBM terms shipped with the wheel) | Db2 client driver |
| IBM Db2 Community Edition image `icr.io/db2_community/db2` | 12.1.5.0 | IBM license, accepted via `LICENSE=accept` | Local database server (pulled, not redistributed) |
| FastAPI | 0.162.2 | MIT | HTTP API |
| Uvicorn | 0.54.0 | BSD-3-Clause | ASGI server |
| Pydantic / pydantic-settings | 2.14.3 / 2.16.2 | MIT | Schemas, configuration |
| python-dotenv | 1.2.4 | BSD-3-Clause | `.env` loading |
| langchain-core | 1.7.6 | MIT | LangChain runtime for the structured planner |
| langchain-openai | 1.7.4 | MIT | `ChatOpenAI`, used against the Meta Model API (OpenAI-compatible Chat Completions) |
| openai (Python SDK) | 3.46.0 | Apache-2.0 | Transport used by langchain-openai (timeouts, retries) |
| langchain-anthropic | 1.7.10 | MIT | Optional adapter (`AI_PROVIDER=anthropic`), mock-tested only |
| anthropic (Python SDK) | 2.6.0 | Apache-2.0 | Transport used by langchain-anthropic |
| langsmith (transitive) | 0.14.17 | MIT | Installed by langchain-core; tracing is not enabled |

## Runtime, frontend (`frontend/package.json`)

| Component | Version | License |
|---|---|---|
| Next.js | 16.4.5 | MIT |
| React / React DOM | 19.3.1 | MIT |
| Recharts | 3.10.1 | MIT |
| lucide-react | 1.70.0 | ISC |
| clsx | 2.1.1 | MIT |
| geist (Geist Sans and Mono fonts) | 1.9.2 | SIL Open Font License 1.1 |

## Development and test only

| Component | Version | License |
|---|---|---|
| pytest, httpx | 9.2.0, 0.28.1 | MIT, BSD-3-Clause |
| TypeScript | 5.9.3 | Apache-2.0 |
| Playwright Test | 1.65.0 | Apache-2.0 |
| Vitest, jsdom, Testing Library (react, user-event, jest-dom) | 5.1.0, 29.1.1, 16.3.3, 14.6.8, 7.0.1 | MIT |
| ESLint, eslint-config-next, @vitejs/plugin-react | 9.39.5, 16.4.5, 6.2.1 | MIT |
| Tailwind CSS, @tailwindcss/postcss | 4.3.5 | MIT |
| openapi-typescript | 7.13.0 | MIT |
| @types/node, @types/react, @types/react-dom | 24.19.2, 19.3.0, 19.3.0 | MIT |

Transitive dependencies are resolved from `backend/pyproject.toml` and `frontend/package-lock.json` and are not listed one by one. Apache-2.0 dependencies are used unmodified, so no NOTICE text from them has to be reproduced. If a dependency is ever vendored or modified, add its license and NOTICE here.

The "Meta Muse Spark 1.3" model is called as a hosted service through the Meta Model API; no model weights are distributed. Use of the API is governed by Meta's own terms. The IBM Db2 VS Code extension used for the organizer's evidence screenshot is not part of this submission.
