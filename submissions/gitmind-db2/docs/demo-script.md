# GitMind 2.0 — Demonstration Script & Evaluation Walkthrough

This step-by-step demonstration showcases GitMind 2.0's capabilities powered by **IBM Db2**.

---

## Prerequisites
1. Clone the repository and navigate to the project directory:
   ```bash
   cd submissions/gitmind-db2
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your environment variables in `.env` (copy from `.env.example`).

---

## Demo Stage 1 — IBM Db2 Connectivity & Diagnostic Health Check
Verify live database capability detection and native vector support:
```bash
python src/gitmind/cli.py db2 doctor
```
**Expected Output:**
- Connection status verified.
- Db2 server version detected (e.g. 12.1.2+).
- Native Db2 `VECTOR` data type validated.
- Native `VECTOR_DISTANCE` execution probe passed.
- Configured schema (`GITMIND`) and vector table (`GITMIND_VECTORS`) verified.

Run schema migrations:
```bash
python src/gitmind/cli.py db2 migrate
```
Inspect schema tables:
```bash
python src/gitmind/cli.py db2 status
```

---

## Demo Stage 2 — Repository Understanding & Knowledge Graph Indexing
Index repository history, Tree-sitter code symbols, documentation, and GitHub PRs:
```bash
python src/gitmind/cli.py index --days 90
```
**What happens under the hood:**
1. Git commits and author histories are parsed and stored in `GITMIND_ARTIFACTS`.
2. Parent commit links (`COMMIT_PARENT`) and touched files (`COMMIT_TOUCHES_FILE`) are mapped in `GITMIND_RELATIONS`.
3. Tree-sitter parses function and class definitions into AST symbol artifacts and links them via `COMMIT_MODIFIES_FUNCTION`.
4. Text chunks pass through secret redaction and are embedded into `GITMIND_VECTORS` via `langchain-db2` `DB2VS`.

Ask a grounded question:
```bash
python src/gitmind/cli.py ask "Why was authentication introduced and how did it evolve?"
```
**Expected Output:**
- History Agent analyzes commit evolution.
- Code Agent pinpoints function-level changes.
- Synthesizer verifies evidence against Db2 and returns **Verified Facts**, **Historical Inferences**, and **Grounded Evidence**.

---

## Demo Stage 3 — Persistent Multi-Agent Engineering Memory
Ask about prior findings:
```bash
python src/gitmind/cli.py memory search "authentication regression"
```
**What happens under the hood:**
- GitMind queries previously saved `GITMIND_FINDINGS` and semantic vectors in Db2.
- Institutional memory is recalled even after full CLI restart!

---

## Demo Stage 4 — Signature Differentiator: Historical Change-Risk Review (`gitmind review`)
Analyze branch or working changes for historical risk:
```bash
python src/gitmind/cli.py review --base main
```
**What happens under the hood:**
1. Inspects the active git diff and extracts touched files.
2. Tree-sitter identifies modified function/class symbols.
3. Queries Db2 vector store and Knowledge Graph for past reverts, regressions, and bug fixes.
4. Executes the deterministic risk engine:
   - Evaluates explainable risk signals (+pts).
   - Generates an executive risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
5. Persists the review finding in Db2 for future sessions.
6. Emits a clean, evidence-backed report with actionable recommendations!

---

## Demo Stage 5 — Automated Benchmark Suite
Run the 28 unit, integration, and golden evaluation benchmark tests:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```
**Expected Output:**
- All 28 tests pass:
  - 100.0% Hit@5 on the 20-question golden evaluation dataset.
  - 0.858 Mean Reciprocal Rank (MRR).
  - 100.0% Factual claim grounding.
  - Zero cross-repository multi-tenant data leakage.
  - 100.0% secret redaction rate.
