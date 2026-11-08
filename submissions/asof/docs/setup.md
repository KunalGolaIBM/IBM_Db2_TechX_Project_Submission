# Setup and configuration in full

Every setup path, every setting, and the optional parts (IBM watsonx.ai, per-user API access, TLS). The short version is in the [README](../README.md#setup--installation).

## Prerequisites

- **Python 3.12**, the only version the lock file supports (NumPy 2.5 in it has no 3.11 build). macOS: `brew install python@3.12`. Ubuntu 24.04: `sudo apt install python3.12 python3.12-venv`. Ubuntu 22.04 (the organizers' WSL image): `sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt install python3.12 python3.12-venv`. Elsewhere: [python.org](https://www.python.org/downloads/) or `pyenv install 3.12`.
- **Operating system:** macOS 14 or later on Apple Silicon (tested, path C) or x86-64 Linux (tested in CI, paths B and C). **Windows:** use WSL 2 with Ubuntu, as the organizers' guide does, and run everything inside it. **Intel Macs** cannot install the Python side: PyTorch 2.15, which the local embedding model needs, publishes macOS wheels for Apple Silicon on macOS 14 and later only.
- **Docker** (Docker Desktop, Docker Engine, or Colima on macOS) and about 10 GB of free disk for the Db2 image and data
- **IBM Db2 12.1.2 or later** (12.1.5 tested), from any of the three paths below
- **An LLM, optional:** an [OpenRouter](https://openrouter.ai/keys) API key, or [Ollama](https://ollama.com) with `ollama pull qwen2.5:7b-instruct` (no key). With neither, [replay mode](../README.md#replay-mode-no-model-at-all) runs the built-in scenarios.
- **Apple Silicon only:** IBM's Db2 image is Intel-only and runs under emulation. With Colima: `colima start --cpu 4 --memory 6 --vz-rosetta`, then use path C.


## Setup & Installation

**One command** (from `submissions/asof`, with Python 3.12 and Docker):

```bash
./quickstart.sh
```

It creates `.venv` with the locked dependencies, creates `.env`, uses the Db2 already listening on `localhost:50000` (paths A and B below; it asks for that owner password without echoing it) or starts AsOf's Compose service (path C) with a generated owner password, runs `python -m asof.setup`, and serves the app on http://127.0.0.1:8000. With no `OPENROUTER_API_KEY` in `.env` it switches `.env` to replay mode and says so; to check your own answers, add the key and set `LLM_PROVIDER=openrouter` (or `LLM_PROVIDER=ollama`), then restart. CI runs `./quickstart.sh --no-serve` on a bare runner, queries the app and runs a real check with `scripts/smoke_check.py`. The steps it automates:

**1. Python and configuration** (from `submissions/asof`):

```bash
python3.12 -m venv .venv && source .venv/bin/activate
# Linux only, first: pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu   (else pip pulls CUDA)
pip install -r requirements.txt -c requirements.lock && pip install -e . --no-deps
cp .env.example .env     # set DB2_PASSWORD, and OPENROUTER_API_KEY (or LLM_PROVIDER=ollama)
```

**2. A Db2 database.** Pick one; AsOf needs one database (`testdb` at `DB2_HOST:DB2_PORT`, by default `localhost:50000`) and its owner account.

- **A. IBM Db2 Developer Extension for VS Code** (the organizers' recommended path). Install `IBM.db2-for-luw`, click the Db2 icon, then **Create Db2 instance** with host `localhost`, port `50000`, username `db2inst1`, a password, and database `testdb`. Put that password in `.env` as `DB2_PASSWORD`, and if the instance page shows a port other than 50000 (under WSL it is often 50001), set `DB2_PORT` to it, and if it is 50001, also set `DB2_TLS_PORT` to a free port before you turn on AsOf's optional TLS listener, which uses 50001 by default; `./quickstart.sh` and setup both read it. The extension's container is called `db2server`, which setup finds on its own. On Apple Silicon with Colima the create flow can switch the Docker context to Docker Desktop and stall; if `docker context show` says `desktop-linux`, run `docker context use colima` and use path C.
- **B. Plain Docker with IBM's image** (Intel or Linux). Same container and database the organizers' setup guide uses:

  ```bash
  docker run -itd --name db2server --privileged=true -p 127.0.0.1:50000:50000 \
    -e LICENSE=accept -e DBNAME=testdb \
    -e DB2INST1_PASSWORD="$(sed -n 's/^DB2_PASSWORD=//p' .env)" \
    -v db2data:/database icr.io/db2_community/db2:12.1.5.0
  docker logs -f db2server     # wait for "Setup has completed", then Ctrl+C
  ```

- **C. AsOf's Compose file** (Apple Silicon, or anywhere). Builds a thin fix on top of IBM's image (see below) and waits until `testdb` accepts connections. The first start took about 6 minutes on an M-series MacBook Air under Rosetta.

  ```bash
  docker compose up -d --wait db2
  ```

**3. Schema, users and data:**

```bash
python -m asof.setup
```

`python -m asof.setup` is safe to re-run. It generates passwords for the five least-privilege users into `.env` (never printed), creates them as OS users inside the Db2 container (Db2 authenticates against the operating system), installs the schema, seeds the fictional data, applies grants, and finishes by proving, as the runtime user, that the as-of query works and that writes are refused, and, as dbt's user, that it can neither delete ledger rows nor create a table in `ASOF`. If it cannot reach any Db2 container (for example a remote Db2), it prints the exact `useradd` commands to run on the Db2 host.

> **Use a database AsOf can own.** Setup revokes `CONNECT`, `CREATETAB`, `BINDADD` and `IMPLICIT_SCHEMA` from `PUBLIC` on the whole database ([90_grants.sql](../src/asof/sql/90_grants.sql)), so only the named users can connect and only the owner can create objects. That is the point on a database of its own, such as the `testdb` the paths above create, but on a database other applications share it would lock out every user that relied on those defaults. Point `DB2_DATABASE` at a dedicated database.

Which paths were run end to end: C on Apple Silicon (dev machine and a fresh clone), and B in CI on every push to `main` of the standalone repository: x86-64 Linux, IBM's unmodified `icr.io/db2_community/db2:12.1.5.0`, the `docker run` command above, then setup, the Db2 feature checks, the full test suite and the access plans (each run takes Db2 about 60 to 90 s to be ready, then runs everything listed, plus the dbt marts and a real Airflow DAG run). A third CI job runs `./quickstart.sh --no-serve` on a bare runner, which takes path C from nothing. A creates the same `db2server` container and `testdb` database as B.

### Why AsOf builds its own Db2 image

[docker-compose.yml](../docker-compose.yml) builds a thin layer on top of IBM's image ([docker/db2/Dockerfile](../docker/db2/Dockerfile)) because the stock image **silently fails its first-run setup on Apple Silicon**:

- Under Rosetta (Colima `--vz-rosetta`; the emulator is registered without the "preserve argv[0]" flag), `su - db2inst1 -c ...` does not start a login shell, so `db2profile` is never loaded.
- IBM's setup script then fails every `db2` command with "command not found", never starts the engine or creates `TESTDB`, and still prints **"Setup has completed"**.

The derived image fixes this and two follow-on problems. Each change is a no-op on a regular x86 Linux host:

1. **Login-shell wrapper** for the Db2 users, so `db2profile` always loads.
2. **Platform pinned in the Dockerfile** (`FROM --platform=linux/amd64`), because Docker's classic builder, used when the buildx plugin is absent, ignores Compose's `platform:` and looks for an arm64 image that IBM does not publish.
3. **Stale setup marker cleared on start**, so the healthcheck cannot pass on a marker from the previous boot while setup is re-running. `docker compose up --wait` returns only once setup has finished **and** `TESTDB` accepts connections.

Use a Docker named volume (as all three paths do), not a bind mount: Db2 cannot create its home directories on a macOS-shared folder.


## Configuration

All settings are environment variables, read from `.env` ([.env.example](../.env.example) lists every one with dummy values). `.env` is gitignored. The Db2 names are the ones the organizers' guide uses.

| Variable | Purpose |
|---|---|
| `DB2_HOST`, `DB2_PORT`, `DB2_DATABASE` | Where Db2 runs (default `localhost`, `50000`, `testdb`) |
| `DB2_USER`, `DB2_PASSWORD` | Owner account (default `db2inst1`), used only by setup and the feature check. The older names `DB2_ADMIN_USER` / `DB2_ADMIN_PASSWORD` still work. |
| `DB2_CONNECT_TIMEOUT_S`, `DB2_LOCK_TIMEOUT_S` | Seconds to wait for a connection (15) and, for the runtime users, for a row lock (10, `SET CURRENT LOCK TIMEOUT`) before failing closed |
| `DB2_SSL`, `DB2_SSL_SERVER_CERT` | TLS to Db2 (default off). `DB2_SSL=true` adds `SECURITY=SSL`; the certificate file, if set, is pinned with `SSLServerCertificate`. See [TLS to Db2](#tls-to-db2). |
| `DB2_CONTAINER` | Container in which setup creates the four OS users (default `asof-db2`; `db2server` and any single running Db2 container are found automatically) |
| `ASOF_APP_PASSWORD`, `ASOF_EDITOR_PASSWORD`, `ASOF_REVIEW_PASSWORD`, `ASOF_ANALYST_PASSWORD`, `ASOF_MART_PASSWORD` | Least-privilege users (runtime, policy editor, specialist reviewer, read-only analyst, dbt's mart builder); generated by setup if empty. The `*_USER` names next to them default to `asofapp`, `asofedit`, `asofrev`, `asofread` and `asofmart`. |
| `ASOF_AUTH` | `local` (default): the server binds to localhost, refuses `--host` beyond it unless `ASOF_API_TOKEN` is set, takes policy changes and specialist actions only from localhost, and the optional shared tokens below apply. `users`: every `/api/` request needs a personal token holding the route's role; see [Per-user API access](#per-user-api-access). |
| `ASOF_API_TOKEN` | Optional. When set, every `/api/` request needs `Authorization: Bearer <token>` (16 to 256 printable ASCII characters, constant-time compare); `/healthz` and the UI stay open, and the UI asks for the token once per tab. Empty: the server relies on binding to localhost. |
| `ASOF_ANCHOR_KEY_FILE`, `ASOF_ANCHOR_DIR` | Chain-head anchors. The HMAC key is not in `.env` (which holds the owner's password): setup generates it in its own file outside the project folder, `~/.config/asof/anchor.key` by default (`$XDG_CONFIG_HOME/asof/anchor.key` if set), mode 600 in a 700 directory, never printed. A key file inside the project folder, or readable by other users, is refused. `ASOF_ANCHOR_KEY` overrides the file from the environment, for containers and CI. `ASOF_ANCHOR_DIR` is where the anchor logs go (default `var/anchors`, gitignored; for real use, storage the database owner cannot write). No key: anchoring is off and `/healthz` says so. |
| `ASOF_EDITOR_TOKEN` | Optional. Lets a non-local client make editor changes (policy changes, approving drafted corrections) with the `X-AsOf-Editor-Token` header; otherwise those are localhost only. |
| `LLM_PROVIDER` | `openrouter` (default), `ollama`, `openai_compatible`, `watsonx` (see [IBM watsonx.ai](#ibm-watsonxai)), or `replay` (no model: recorded outputs for the built-in scenarios, anything else held; see [Replay mode](../README.md#replay-mode-no-model-at-all)) |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Hosted model (default `google/gemini-3.1-flash-lite`) |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Local model (default `qwen2.5:7b-instruct`) |
| `LLM_FALLBACK`, `LLM_FALLBACK_TIMEOUT_S` | `ollama` (default): a call the hosted model cannot answer (timeout, transport error, no valid output) goes once to local Ollama, and the ledger's model field records it, for example `openrouter:... (fallback ollama:qwen2.5:7b-instruct on 2 of 4 calls)`. `none` turns it off. If both fail, the check fails closed. |
| `ASOF_INDB_EMBEDDINGS`, `EMBEDDING_API_URL`, `EMBEDDING_API_MODEL`, `EMBEDDING_API_KEY` | In-database embeddings: `auto` (default, on when an API key is set), `on` or `off`; HTTPS endpoint serving the same model as the app (default OpenRouter, `sentence-transformers/all-minilm-l6-v2`); the key defaults to `OPENROUTER_API_KEY` |
| `ASOF_INDB_PROVIDER` | Which provider Db2's `EMBEDDER` calls: `openai` (default, the endpoint above) or `watsonx` (`PROVIDER WATSONX`, with the watsonx settings below) |
| `WATSONX_API_KEY`, `WATSONX_URL`, `WATSONX_PROJECT_ID` (or `WATSONX_SPACE_ID`), `WATSONX_MODEL`, `WATSONX_EMBEDDING_MODEL` | IBM watsonx.ai: an IBM Cloud API key, your region's endpoint (default `https://us-south.ml.cloud.ibm.com`; only `*.ml.cloud.ibm.com` and `*.wxai.ibm.com` over HTTPS are accepted), the project the watsonx.ai Runtime service is associated with, the chat model (default `ibm/granite-4-h-small`) and the embedding model Db2 calls (default `sentence-transformers/all-minilm-l6-v2`) |
| `ASOF_INTAKE_MAX_OUTPUT_TOKENS`, `ASOF_INTAKE_TIMEOUT_S` | Policy intake's one model call copies whole clauses, so it gets a larger output cap (4000) and a longer deadline (150 s) than a check's calls |
| `LLM_TIMEOUT_S`, `LLM_MAX_OUTPUT_TOKENS` | Hard per-call deadline and output cap; the gate fails closed when hit. Use `LLM_TIMEOUT_S=180` for Ollama on a laptop (the value the recorded Ollama run used). |
| `ASOF_CHECK_DEADLINE_S` | Whole-check budget (300 s): no step of a check starts after it, and the check fails closed |
| `ASOF_ROUTER_AGENT` | `auto` (default): the routing agent looks at close calls only with a model measured on the pinned routing split; `on`: with any model; `off`: close calls always go to a person ([routing](db2.md#routing-which-policy-a-draft-is-about)) |
| `ASOF_ALLOWED_HOSTS` | Host headers the API answers to (default `127.0.0.1,localhost,::1`), against DNS rebinding |

### IBM watsonx.ai

AsOf runs without watsonx.ai, and the default setup does not change when you add it. To use it, you need four things from IBM Cloud:

1. **An IBM Cloud account with watsonx.ai.** Sign up at [dataplatform.cloud.ibm.com/registration/stepone?context=wx](https://dataplatform.cloud.ibm.com/registration/stepone?context=wx) and choose a region. This provisions watsonx.ai Studio and a **watsonx.ai Runtime** service on the Lite plan, which is free (IBM asks for a card to verify identity; the Lite plan currently includes 300,000 tokens a month).
2. **A project ID.** Sign-up creates a sandbox project with the Runtime service already associated. Open the project, choose **Manage**, then **General**, and copy the **Project ID**. (For another project: **Manage**, **Services and integrations**, **Associate service**, pick the watsonx.ai Runtime instance.)
3. **An API key.** In IBM Cloud: **Manage**, **Access (IAM)**, **API keys**, **Create**. It is shown once; copy it.
4. **The region's endpoint:** `https://us-south.ml.cloud.ibm.com` (Dallas), `eu-de` (Frankfurt), `eu-gb` (London), `jp-tok` (Tokyo), `au-syd` (Sydney) or `ca-tor` (Toronto), as `https://<region>.ml.cloud.ibm.com`. The embedding model AsOf uses in Db2 is offered in us-south, eu-de and jp-tok.

Then, in `.env`:

```bash
WATSONX_API_KEY=...                               # the IBM Cloud API key
WATSONX_PROJECT_ID=...                            # the project ID
WATSONX_URL=https://us-south.ml.cloud.ibm.com
LLM_PROVIDER=watsonx                              # watsonx.ai checks the answers (needs: pip install -r requirements-watsonx.txt)
ASOF_INDB_PROVIDER=watsonx                        # Db2 itself embeds policy text on watsonx.ai (no extra package; re-run python -m asof.setup)
```

Either line can be used without the other. With `LLM_PROVIDER=watsonx`, a wrong key or unreachable region is reported when AsOf starts, and the key never appears in the message. Both paths have run on a real account; the results are [below](evaluation.md#on-ibm-watsonxai). `python -m asof.eval --split test --provider watsonx --model <id>` measures any watsonx.ai chat model on the frozen split. On the Lite plan, mind the monthly token allowance: a check costs about 4,200 tokens, so one 40-case split is about 170,000.

### Per-user API access

By default AsOf trusts its localhost binding (and, optionally, one shared token). For a server other people reach, set `ASOF_AUTH=users` and give each person or calling system a personal token:

```bash
python -m asof.users add maria --roles checker,auditor   # prints maria's token once; Db2 keeps only its SHA-256
python -m asof.users rotate maria                         # new token, the old one stops working
python -m asof.users disable maria                        # refused from the next request
python -m asof.users list
```

| Role | Routes |
|---|---|
| `checker` | `POST /api/gate`, `POST /api/assistant/ask` |
| `auditor` | the ledger, replay, evidence packs, receipts, `VERIFY_CHAIN`, chain-head anchors, analytics, change impact, Ask the ledger, and any route not listed here |
| `editor` | policy changes and previews, drafting and approving corrected help-centre answers (from any client: the role replaces the localhost rule) |
| `reviewer` | the specialist inbox (`/api/reviews`: read held decisions, check and send replies) and correction notices (`/api/notices`: draft, approve, reject) |

Reading the policy timeline and `GET /api/whoami` need any valid token. Each decision records the user who asked in its hashed verdicts (`requested_by`), and each clause version made through the API starts its change note with the editor's name. The web UI asks for the token once per tab. Users are managed with the owner account, so `DB2_PASSWORD` must be set where you run the command; the runtime user can only read the table.

### TLS to Db2

The documented setups connect over plain TCP to `127.0.0.1`, which never leaves the machine. A remote Db2 needs TLS, and every AsOf connection (runtime, editor, analyst, setup) goes through one function, [db.py](../src/asof/db.py) `dsn()`, so one setting covers them all:

```bash
# .env, for Db2 on Cloud: host, port and database from the service credentials
DB2_HOST=<host from the service credentials>
DB2_PORT=<TLS port from the service credentials>
DB2_DATABASE=bludb
DB2_SSL=true
# Optional: pin the server's (or its CA's) certificate; empty trusts the driver's own authorities
DB2_SSL_SERVER_CERT=/path/to/the/downloaded/certificate.crt
```

The certificate path must exist and may not contain `;`, `=` or braces, so it cannot add a keyword to the connection string. AsOf logs a warning when it connects to a non-local Db2 without TLS. On Db2 on Cloud there is no container to create OS users in: create `asofapp`, `asofedit`, `asofread` and `asofmart` in the service console, put their passwords in `.env`, and setup skips the container step with a message.

To try TLS on one machine, turn it on in the local container (self-signed certificate, port 50001; plain TCP on 50000 keeps working):

```bash
scripts/enable_db2_tls.sh
# then in .env: DB2_SSL=true  DB2_PORT=50001  DB2_SSL_SERVER_CERT=var/tls/db2-server.arm
```

The script makes a GSKit key database whose password GSKit generates and stashes (never shown), a certificate for `localhost` and `127.0.0.1`, sets `SSL_SVR_KEYDB`, `SSL_SVR_STASH`, `SSL_SVR_LABEL`, `SSL_SVCENAME=50001` and `DB2COMM=SSL,TCPIP`, restarts the instance and copies the public certificate to `var/tls/` (not committed). `tests/test_tls.py` then connects as the runtime user over TLS and verifies the ledger chain, and checks that the TLS port refuses plain TCP and an untrusted certificate. CI turns TLS on against IBM's stock image and fails if those tests are skipped. Tested against the local container on 7 Nov 2026, on Apple Silicon and in CI; not tested against Db2 on Cloud itself, for want of an account.

> **Security:** never commit `.env`. Before every commit, `python scripts/check_secrets.py` compares the staged changes against the real values in your local `.env` and against common key patterns, and fails without printing anything secret.
