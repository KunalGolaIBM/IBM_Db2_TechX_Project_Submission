# Command record

The complete shell command and Python source-transformation inputs are recorded in
[results/command-log.json](results/command-log.json), in execution order. Repeated
commands and failed attempts are retained. Source edits also used the apply_patch tool.
The record includes environment checks, tests, coverage, migrations, query-plan probes,
evaluation, load tests and commits. Private .env contents and credentials are excluded.

Publishing commands are recorded separately in that JSON before execution, so they can
be committed with the published source. Their outcome is reported in the PR comment
and final task response. Generation of this record and final status reads are
bookkeeping and are not recursively logged.

Primary verification commands (use the activated Python 3.12 environment):

```bash
python -m ruff check src tests loadtest scripts
python -m mypy src
python -m pytest -q --cov=src --cov-report=json:.artifacts/unit-coverage.json
python src/seed.py
python -m pytest --db2 -q --cov=src --cov-report=json:.artifacts/full-coverage.json
python scripts/evaluate.py --db2 --output .artifacts/evaluation.json
python scripts/explain.py --output .artifacts/explain.json
python scripts/serve_benchmark.py
python -m locust -f loadtest/locustfile.py --headless -u 50 -r 10 -t 60s --host http://127.0.0.1:8000 --csv .artifacts/after-final --only-summary
```

The benchmark server and Locust run in separate terminals. Result summaries distinguish
local successful checks from any later remote GitHub Actions execution.
