g# Submissions Directory

This directory contains all submitted hackathon projects for the **IBM Db2 TechX Summit 2026**.

## Directory Structure Rules

1. Each submission must exist as an independent, isolated subdirectory: `submissions/<project-slug>/`.
2. Do not modify or delete other participants' folders.
3. Use `submissions/_template/` as your baseline by copying it:
   ```bash
   cp -r submissions/_template submissions/my-project-slug
   ```
4. `<project-slug>` must be lowercase kebab-case (e.g. `db2-vector-rag-search`).

## Required Files per Submission

Every project directory must include:
- `README.md` — Complete project overview, problem statement, setup, and running instructions.
- `architecture.md` — Component architecture diagram and Db2 data flow.
- `submission.json` — Structured JSON metadata with project and team details.
- `.env.example` — Template environment variables with dummy placeholders.
- `src/` — Source code of your application or demonstration.
