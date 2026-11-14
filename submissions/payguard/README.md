# PayGuard

> Check a payment before you send it. Rules, IBM Db2 intelligence and optional Gemini
> investigation flag scams; the server enforces the verdict before PayPal checkout.

![Coverage](docs/results/coverage.svg) ![Tests](docs/results/tests.svg)
[CI](https://github.com/Josebert2001/payguard/actions/workflows/ci.yml) |
[Architecture](docs/ARCHITECTURE.md) | [Testing](docs/TESTING.md) |
[Performance](docs/PERFORMANCE.md) | [Demo video](https://youtu.be/Xl68sUC8XLY)

IBM Db2Hack 2026 finalist project by Sunday Robert (Josebert).
PayGuard also demonstrates an AI payment firewall for PayPal checkout: blocked payments
are refused, REVIEW requires acknowledgement, and the amount comes from Db2.

![PayGuard](docs/screenshots/home.png)

## Start with one command

Prerequisites: Python 3.12 and Docker Desktop with its Linux engine running.

On Windows:

```powershell
.\start.bat
```

The launcher creates an environment, installs dependencies, starts Db2, waits for setup,
applies migrations, seeds missing knowledge and opens http://localhost:8000. First-time
Db2 initialization can take several minutes. Keep the private `.env` out of Git.

Manual setup on Windows or Linux:

```bash
python -m venv .venv
# Linux: source .venv/bin/activate
# Windows PowerShell: .venv/Scripts/Activate.ps1
python -m pip install -r requirements-dev.txt
cp .env.example .env
docker compose up -d
# Wait for "Setup has completed" in: docker logs payguard-db2
python src/seed.py
python -m uvicorn main:app --app-dir src
```

Set the same local Db2 password in `.env` and Docker. Gemini and PayPal credentials are
optional. With no API keys, local hash embeddings, all deterministic screening, entity
lookups, vector retrieval and analyst presets work. Screenshot reading and actual
PayPal sandbox checkout require their respective provider keys.

## What the buyer can do

- Paste a seller chat: PayGuard extracts contacts and price, then returns ALLOW, REVIEW
  or BLOCK with plain English or Nigerian Pidgin reasons.
- Upload/share a screenshot: optional Gemini vision extracts the visible transcript.
- Open `/market`: two fixed fictional listings demonstrate platform checkout.
- Ask the investigator to check evidence, or use the analyst's guarded read-only SQL
  console. Preset questions work without AI.
- File a community report. MERGE escalates a non-trusted contact at three reports.

Known blocked contacts and hard credential/gift-card/remote-access indicators set risk
floors. AI additions are clamped to 0..20 and cannot lower risk. Safe examples cannot
cancel hard evidence. Checkout re-reads the stored verdict and amount; fake client
amounts and model-proposed ALLOW instructions do not bypass the gate.

## Architecture and scalability

`api/` contains the HTTP boundary; `services/` orchestrates screening, investigation,
analyst and checkout; `domain/` owns signals, scoring, models and capability Protocols;
`adapters/` implements Db2, LangChain DB2VS, Gemini, PayPal and embeddings. Original
Python import names and old API paths remain available.

Production data lives in Db2. Transactions exclusively lease connections from a bounded
pool, including IBM DB2VS retrieval. Blocking work runs in worker threads. Query embeddings,
static knowledge retrieval and entity lookups have bounded LRU/TTL caches; reports invalidate
entity lookups. Velocity, community reports, verdicts and checkout authorization stay fresh.

Public endpoints have `/api/v1` paths and legacy aliases. Responses include `X-Request-ID`;
logs are structured JSON. Per-IP limits cover screening, screenshots, reporting and
platform verification. Vector/Gemini failures preserve available deterministic evidence
and return `degraded: true`. Missing persistence disables payment authorization.

Versioned SQL migrations are tracked with checksums in `PG_META`. EXPLAIN confirms indexes
for entity lookup, velocity and region-prefiltered playbook retrieval. The optional ANN
migration is deferred on the tested Db2 12.1.5 container, which rejects index creation;
the measured app uses exact cosine search. See the architecture document for the actual
error, query plans, deployment diagram and scaling path.

## API

```bash
curl -X POST http://localhost:8000/api/v1/screen \
  -H 'Content-Type: application/json' \
  -d '{"message":"Abeg send your OTP and BVN make we upgrade your account","explain":false}'
```

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/screen` | Screen text/payment |
| `POST /api/v1/screen-image` | Screen screenshot |
| `POST /api/v1/report` | File an atomic community report |
| `POST /api/v1/checkout/verify` | Platform check; private `X-API-Key` required |
| `POST /api/v1/paypal/orders` | Persisted-verdict and amount gate |
| `POST /api/v1/analyst` | Guarded read-only analyst query |
| `GET /api/v1/health` | Db2 ping, pool state, Gemini reachability, embedder |
| `GET /api/v1/metrics` | Counts, rolling p50/p95 latency, verdicts, cache hit rates |

Set `PLATFORM_API_KEY` for server-to-server checkout verification. Missing configuration
fails closed. The browser never receives that key. The public demo accepts only fixed
listing IDs, and `PLATFORM_DEMO_ENABLED=false` disables it.

Important settings (all are described in `.env.example`):

| Setting | Default / purpose |
|---|---|
| `DB2_POOL_MIN`, `DB2_POOL_MAX` | 2 / 10 per app process |
| `DB2_POOL_TIMEOUT`, `DB2_CONNECT_TIMEOUT`, `DB2_QUERY_TIMEOUT` | 5s / 5s / 3s |
| `GEMINI_TIMEOUT`, `INVESTIGATION_TIMEOUT` | 5s per HTTP operation / 10s tool-loop budget |
| `CACHE_SIZE` | 512 entries per cache |
| `EMBEDDING_CACHE_TTL`, `PATTERN_CACHE_TTL`, `ENTITY_CACHE_TTL` | 60s / 10s / 5s |
| `RATE_LIMIT_PER_MINUTE` | 60 expensive requests per IP |
| `EMBED_PROVIDER`, `EMBED_DIM` | local / 768; changing provider requires consistent reseeding |

## Tests and measured results

```bash
python -m ruff check src tests loadtest scripts
python -m mypy src
python -m pytest -q --cov=src --cov-report=term-missing
python -m pytest --db2 -q -m db2
python -m pytest --db2 -q --cov=src --cov-report=json:.artifacts/full-coverage.json
python scripts/evaluate.py --db2 --output .artifacts/evaluation.json
```

Measured on the local Python 3.12 / Docker Db2 environment:

| Check | Before | After |
|---|---:|---:|
| Offline tests passing | 44 | 175 |
| Live Db2 tests passing | not run in baseline | 9 |
| Source line coverage (offline) | 70.5% | 84.4% |
| Local screening requests/sec | 43.69 | 94.60 |
| Load-test p95 | 1500 ms | 1000 ms |

The final combined suite passed **184 tests** with **86.9%** source line coverage.
The offline suite skips the live checks. Coverage denominators changed with the refactor;
baseline coverage is restricted to the original source tree, excluding new unimported files.

| Canonical implementation | Offline line coverage |
|---|---:|
| src/domain/scoring.py | 96.9% |
| src/domain/signals.py | 97.1% |
| src/services/analyst.py | 94.6% |
| src/services/presenter.py | 96.4% |
| src/adapters/db2.py | 84.5% |
| src/adapters/memory.py | 96.6% |


Every reported result comes from an executed command. Exact summaries and per-module
coverage are in [verification.json](docs/results/verification.json). Commands, including
failed attempts and environment repairs, are recorded in [docs/COMMANDS.md](docs/COMMANDS.md).

Evaluation uses 15 held-out messages excluded from the knowledge table: confusion
matrix `[[5,5],[0,5]]` (scam/safe rows, flagged/allowed columns), precision 1.0,
recall 0.5 and false-positive rate 0.0. No thresholds were tuned on this set.
The tiny, previously exposed corpus is not an independent production benchmark.
The historical 15 overlaps were removed; only the cleaned training rows are ingested.

Reproduce the measured load workload in two terminals, after seeding:

```bash
python scripts/serve_benchmark.py
python -m locust -f loadtest/locustfile.py --headless -u 50 -r 10 -t 60s \
  --host http://127.0.0.1:8000 --csv .artifacts/after --only-summary
```

The benchmark helper disables external AI and raises the quota only in its own process.
[PERFORMANCE.md](docs/PERFORMANCE.md) records the baseline, final result, hardware,
database contents and limitations. It does not claim internet/Gemini or production-scale
throughput from a small local workload.

## Roadmap: "Truecaller for account numbers"

Let banks and fintechs check a recipient when a buyer enters a NUBAN number, before
confirming a transfer. Next steps include verified reports, reporter reputation,
abuse controls and correction/appeal flows; a WhatsApp forwarding assistant and browser
extension; shared Redis caching/rate limiting; queued AI investigation; and horizontal
app instances with replica-backed analytics. These are future work.

Current limitations: fictional demo contacts, short process-local cache staleness,
small evaluation corpus, limited semantic recall from hashing, and no measured
multi-host or Gemini-under-load benchmark. See the architecture trade-offs and ADRs.

## Team and credits

Sunday Robert (Josebert), [@Josebert2001](https://github.com/Josebert2001):
design, Db2 integration, investigator and PayPal checkout.

The demo contacts are fictional. Public-source example attribution stays in the CSVs.
PayPal Orders v2 credentials remain on the server; only the public client ID is exposed.
