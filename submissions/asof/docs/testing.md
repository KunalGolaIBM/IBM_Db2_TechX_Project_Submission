# Testing and verification in full

What the test suite covers, types and coverage, dependency pinning and the fresh-clone check. The evaluation of the check itself is in [evaluation.md](evaluation.md); the headline results are in the [README](../README.md#testing--verification).

```bash
pytest -q                                 # 1215 tests: 9 need an opt-in flag (live LLM, remote endpoints, the backup drill), 3 need TLS on (scripts/enable_db2_tls.sh; CI turns it on), 1 needs the watsonx extra
pytest -q -m "not db2"                    # unit tests only, no database needed
ASOF_RUN_LLM_TESTS=1 pytest -q -m llm     # 4 live tests against the configured LLM (spends API calls)
ASOF_RUN_BACKUP_TESTS=1 pytest -q -m backup   # the online backup and restore drill (about a minute; creates and drops two databases)

pip install -r requirements-dev.txt
python scripts/audit_deps.py             # pip-audit over all 109 pinned packages; exit 1 on any known vulnerability
mypy                                     # type check (configuration in pyproject.toml)
pytest -q --cov=asof --cov-report=term   # line coverage of src/asof
```

**Types and coverage** (Sun 8 Nov 2026, 10 PM). `mypy` 2.4 with the Pydantic plugin finds no issues in the 46 modules. It runs `--strict` on 40 of them: the check and its LangGraph wiring (`gate.py`, `checkgraph.py`), the rule checker, redaction, the ledger, the anchors, policy changes, intake, the specialist inbox, correction notices, the change-impact agent, the router, setup, the seed loader, the Db2 layer, the configuration and the benchmarks. The other six run with relaxed annotation rules: the FastAPI routes, Ask the ledger's LangChain SQL chain, the model clients, replay, the SQL-file loader and the evaluation's counting wrapper, all glue around untyped libraries, and still fully type-checked. The MCP server passes `--strict` in its own environment. The full suite against Db2 covers **80% of the lines in `src/asof`** (7,118 statements, run locally without the opt-in backup drill; CI runs the drill too), including:

| Module | Coverage |
|---|---|
| `redact.py`, `router.py` | 100% |
| `rules.py` | 99% |
| `notices.py`, `impactagent.py` | 97% |
| `policy.py` | 96% |
| `gate.py` | 97% |
| `checkgraph.py` | 95% |
| `ledger.py` | 93% |
| `intake.py` | 92% |
| `review.py` | 88% |
| `api.py` | 86% |

The ledger benchmark is at 89%; the backup drill (`backup.py`) reaches 82% when its opt-in test runs, as it does in CI. The lowest numbers belong to command-line tools that CI runs as steps of their own rather than through pytest: `setup.py` 28%, `explain.py` 55% and the evaluation runners at 37 to 71%. `db2check.py` (95%) and a 40-row run of the chain benchmark (`chainbench.py`, 86%) now run under pytest too. CI runs mypy on every push to `main` and fails the Db2 job if coverage drops below 78%.

`requirements.txt` lists the 23 direct dependencies; `requirements.lock` pins all 109 packages, transitive ones included, at the versions tested. It is used as a pip constraints file, so Linux and Windows still get their platform-only packages. `python scripts/lock_deps.py` regenerates it, and a test fails if the two files disagree. Last audit (8 Nov 2026): no known vulnerabilities; CI repeats it on every push to `main`.

Checked from a fresh clone of the standalone repo on Sun 8 Nov 2026, 11 PM, at commit `0ccebfb` (the code as submitted; later commits change only docs and the slides), with the dev `.env` minus every model key, so in replay mode: `pip install -r requirements.txt -c requirements.lock && pip install -e . --no-deps` took 63 s with a warm pip cache, and `pytest -q` ran 904 tests: 891 passed and 13 were skipped, the 9 opt-in ones, the 3 TLS tests, which need `scripts/enable_db2_tls.sh` first (CI runs them), and the 1 that needs the watsonx.ai extra (CI runs it too). The quick start and `scripts/smoke_check.py` were not re-run on this machine, because both write to its demo ledger; CI's quick-start job runs both from a bare runner at the same commit, starting Db2 through Compose, and passed. The previous local check, at `48b9eb2`, ran `./quickstart.sh --no-serve` in 91 s and the smoke check against the clone's app.

Integration tests install everything into a throwaway `ASOF_TEST` schema, connect as the real least-privilege user, and drop the schema afterwards. They skip automatically when Db2 is unreachable. They cover:

- the same claim reaching `BRV-002` v1 for 2026-03-10 and v2 for 2026-06-02, and both sides of the 2026-04-30 / 2026-05-01 boundary
- replay with `FOR SYSTEM_TIME AS OF` after a policy change
- Db2 rejecting overlapping clause versions and malformed rule JSON
- the runtime user being refused `UPDATE`, `DELETE`, `INSERT`, `CREATE TABLE` and `DROP`, on policy and ledger tables alike
- SQL injection strings returning nothing instead of executing, and stored as plain text in the ledger
- no string-built SQL at request time: an AST scan of every module and test fails the build on SQL built with f-strings, `%`, `+` or `.format()`, except setup and test DDL that names objects through the validating `db.ident` (the three exceptions are named under [IBM Db2 Integration](../README.md#ibm-db2-integration)); runtime statements are literals and even the schema is a bound parameter (`SET CURRENT SCHEMA = ?`)
- the ledger: gapless IDs and linked hashes under three concurrent writers; triggers stopping even the owner; `VERIFY_CHAIN` catching an owner who drops a trigger and edits a row, edits a citation, or deletes the last row
- every gate decision path with a scripted LLM, including a manipulated judge that says SUPPORTED with a real quote (the rule check still overrides it), an invented quote, a clause not in force, timeouts and a ledger outage
- 97 rule-checker tests, mostly realistic claims against the real corpus rules, in both directions (real contradictions caught, situational numbers left alone)
- API validation (byte limits, dates, allow-listed `doc_id`, control characters, unknown fields), body cap, rate limit and security headers
- policy intake: files that are not usable PDFs (not a PDF, too large, encrypted, too many pages, no text layer) refused before any text is read; a paraphrased clause, a rule value the text does not state, a permission stated the other way, an unquoted or unstated date, and an injected instruction all blocked; Db2 refusing a file whose hash differs, an approval by the uploader, an accepted blocked or unchanged item, a second decision and a second apply; a preview leaving nothing behind; the editor refused `UPDATE` and `DELETE` on the draft tables and the runtime user refused the procedures
- the specialist inbox: Db2 refusing a contradicting reply, a second answer, self-review, a missing note, a reply checked against another document and verdicts that disagree with the stated reason; a `REVIEWED` row only through `RESOLVE_ESCALATION` (`APPEND_LEDGER` refuses it, `APPEND_LEDGER_ROW` is granted to no one); a contradiction the extractor missed still refused
- correction notices: Db2 checking every claim made about a notice, one open notice per answer and version, a held correction rejected but never sent, a notice refused after its policy changed again, and none rewritten or deleted, even by the owner
- routing: Db2 ranking both documents in one statement, the agent only confirming Db2's leader, a held route answered against the document the specialist picks; the routing test split frozen by hash
- the customer chat page served under the same CSP, with no inline script and no `innerHTML`, and every suggested question recorded for its booking date
- watsonx.ai: the client built with AsOf's deadline, retry cap and output cap; a refused key reported without the key; Db2 registering a watsonx embedder without storing the key in plain text; and, where the extra is installed (CI), the real SDK taking the arguments AsOf passes
- the MCP server (14 tests in its own environment): tool schemas, a corrected and a held answer, dates and lengths refused before AsOf is called, the token kept out of results, a stdio launch, and one check through a live AsOf

> **Note on the submission validator:** `scripts/validate_submission.py` flags any `.env` or `*.pem` file under the folder, including your local `.env` and certificate files inside `.venv`. Neither is committed. Run the validator from a clean checkout to see what a reviewer sees.
