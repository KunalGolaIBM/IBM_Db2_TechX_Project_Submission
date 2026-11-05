# CLAUDE.md - Project Guidelines

Project: AI-Powered Recipe & Ingredient Waste Optimizer
Hackathon: IBM Db2 TechX Summit 2026 / Db2Hack
Project Slug: db2-recipe-waste-optimizer
Location: submissions/db2-recipe-waste-optimizer/

## Non-Negotiable Core Rules:
1. All application source code lives inside `submissions/db2-recipe-waste-optimizer/src/`.
2. IBM Db2 must be genuinely used in executable code as the primary system of record (inventory, recipe catalogue, embeddings, cooking history, audit events).
3. Do not replace Db2 with SQLite or other databases for the core path.
4. Keep inventory calculations, unit conversion, and ranking deterministic in Python.
5. Use LangChain for parsing and grounded recipe instruction generation; never delegate arithmetic, inventory mutations, or safety decisions to the LLM.
6. Validate all LLM outputs with Pydantic models.
7. Zero secrets policy: never commit real API keys or passwords. Use `.env.example` and keep real `.env` in `.gitignore`.
8. Always ensure `python scripts/validate_submission.py submissions/db2-recipe-waste-optimizer` passes with 0 errors.
