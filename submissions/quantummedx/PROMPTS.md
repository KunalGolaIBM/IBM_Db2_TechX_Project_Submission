# AI-assisted development log

QuantumMedX was built with Claude (Anthropic) as a coding assistant, working from three prompts written by the author: a full-stack master prompt, a hackathon-submission prompt and a UI/UX prompt. The author directed scope and reviewed results. This log records what was asked, what went wrong and what was verified.

## Milestones
1. Inspected the official repository, template and validator; created `submissions/quantummedx/` that passes the validator.
2. Wrote the Db2 schema, connection pool, repository layer and init script.
3. Built and tested the ML core (analysis, leakage-safe preprocessing, three classical models, Qiskit VQC).
4. Built the FastAPI routes (auth, uploads, training, comparison) and tested them with an in-memory repository stand-in.
5. Built the agent toolbox, CrewAI crew, pipeline, report builder and number verifier.
6. Built a five-screen React frontend; type-checked, built and smoke-tested it.
7. Wrote documentation and the Round 1 proposal.

## Defects found and fixed
- A test expected 3 samples in one class; the correct count was 2. The test, not the code, was wrong.
- A leftover dead conditional in the experiment-result insert was removed.
- `requirements.txt` initially omitted Qiskit and CrewAI and capped pandas below the version the tests ran on; both fixed.
- CrewAI 1.x needs the `litellm` package for providers such as Groq; the crew-build test now uses a natively supported provider and the README and `.env.example` document the extra package.
- Docs said the quantum model used Qiskit Aer; the code uses Qiskit's `StatevectorSampler`, so the docs were corrected.
- The `AGENT_RUNS.MODE` column was renamed `RUN_MODE` to avoid a possible SQL keyword clash.

- First real run on the author's PC: the database name `QUANTUMMEDX` (11 characters) exceeds Db2's 8-character limit, so Db2 never created it and every connection failed with SQL1042C. Renamed to `QMEDX` throughout and documented in the troubleshooting guide.

## Not verified at the time of writing
- Execution against a live IBM Db2 instance (the Db2 SQL has been reviewed but not run by the assistant).
- A live CrewAI run with a real LLM key.
- Visual review of the UI in a browser.
The author should record their own results in `docs/TESTING.md`.
