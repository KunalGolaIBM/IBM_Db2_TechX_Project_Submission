# Code review: the AI-assisted pass and what it changed

On 10 Nov 2026, before the final freeze, AsOf's code had a review pass run with AI coding agents, following the organizers' guidance to review and tidy a submission before judging. The agents ran three static tools, read their output against the code, and proposed changes; Jay approved which ones to apply. Nothing was applied without that approval, and every change went in behind the test suite (unit tests, the Db2 tests it touches, ruff, mypy and the secret check).

## What ran

Over `src/asof` at commit `4d65632`, in a throwaway virtualenv: [vulture](https://github.com/jendrikseipp/vulture) 2.16 (dead code, minimum confidence 60), [deptry](https://github.com/fpgmaas/deptry) 0.25.1 (declared against imported dependencies) and [radon](https://github.com/rubik/radon) 6.0.1 (cyclomatic complexity and maintainability index).

## Findings and decisions

| Finding | Tool | Decision |
|---|---|---|
| 74 possibly unused names | vulture | 71 are names frameworks call: 36 FastAPI routes and exception handlers registered by decorators, pydantic `model_config` and validator methods, LangChain hooks. No action. |
| `Corpus.version_in_force` used only by tests | vulture | **Moved** into the test helpers ([tests/fakes.py](../tests/fakes.py)); the app never called it. |
| `domains.DOC_IDS` used only by tests | vulture | **Kept.** True when the tools ran, but the backtest module merged later the same day uses it ([backtest.py](../src/asof/backtest.py)), so it is no longer dead. |
| `AsOfClauseRetriever` used only by tests and docs | vulture | **Kept.** It is the LangChain `BaseRetriever` integration the README documents for other apps. |
| The `langchain` meta-package is never imported | deptry | **Removed** from `requirements.txt`, `requirements.lock`, `pyproject.toml` and the licence list. Nothing installed requires it (`pip show langchain`: required by nothing), and `langchain-core`, `langchain-community`, `langchain-db2` and LangGraph do not depend on it. The unit tests and the Db2 replay tests then passed in a fresh virtualenv built from the updated requirements. |
| `starlette` imported directly but declared only through FastAPI | deptry | **Declared** at 1.10.0, the version FastAPI 0.162.0 resolves to (`api.py` imports `run_in_threadpool` and `TrustedHostMiddleware` from it). |
| `ibm-db-sa`, `db2-sqlglot-dialect`, `sentence-transformers`, `python-dotenv` reported unused | deptry | False positives: each is loaded by name or by a plugin entry point (an `ibm_db_sa://` URL, SQLGlot's `dialect="db2"`, `langchain_huggingface`, pydantic-settings). No action. |
| watsonx.ai packages imported but not declared | deptry | Intentional: an optional extra in `requirements-watsonx.txt`, imported lazily and tested in its own CI virtualenv. No action. |
| 47 functions at complexity grade C or worse; the worst are `rules.check` (F, 50), `intake._check_one` (E, 39) and `askledger.checked` (E, 39) | radon | **Not refactored before judging.** The two worth splitting first are `rules.check` (the deterministic overrule) and `askledger.checked` (the SQL gate), because both are safety-critical and a per-rule dispatch would make each branch testable on its own. Rewriting them hours before the deadline would trade a measured, tested behaviour for a neater one, so they are listed in the next steps in [limitations.md](limitations.md) instead. |
| Every module grade A for maintainability except `intake.py` (B) | radon | No action. |

Core against optional code, in non-blank lines: `src/asof` is about 10,800 lines of Python, 2,100 of SQL and 2,200 of UI; the optional integrations (dbt, Airflow, Langflow, the MCP server and the cookbook notebook) are about 1,300 together. Moving dbt, Airflow and Langflow under an `integrations/` folder was planned and then left out: it touches CI's Db2 job and the standalone repository's layout for no change in behaviour.

## Fixes found while merging the day's work

Integrating seven parallel streams of work turned up a few problems that tests or CI caught, each fixed in its own commit:

- **A false claim in the docs.** The design notes said `ibm_db` sizes procedure OUT buffers from the placeholder values; on `ibm_db` 3.3.0 a 1-character placeholder came back with a 300-character value. Corrected in `ledger.py` and [design-decisions.md](design-decisions.md).
- **A test key that looked real.** CI's secret check over every tracked file flagged a fake OpenRouter-style key in a live-demo test. It was shortened below the pattern; the check itself was not loosened.
- **Test fixtures that wrote invalid releases.** Once Db2 started refusing releases the policy does not back ([release-rules.md](release-rules.md)), fixtures that appended fake PASS rows were refused too; they now write rows with real citations, so the rule is exercised rather than bypassed.
- **Stale numbers.** The README and test docs still said 904 tests; every count now comes from `pytest --collect-only`.
