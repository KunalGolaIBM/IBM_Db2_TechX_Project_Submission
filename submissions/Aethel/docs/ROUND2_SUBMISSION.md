# IBM Db2Hack 2026 — Round 2 submission checklist

## Required deliverables

- [x] Project source code and folder structure
- [x] FastAPI backend and browser frontend
- [x] IBM Db2 adapter and schema initializer
- [x] LangGraph + LangChain workflow
- [x] Architecture and setup documentation
- [x] GitHub Actions test workflow and pull request template
- [ ] Live Db2 connection verified on the submitter's machine
- [ ] Final screenshots captured from the live Db2 run
- [ ] Fork the organizer repository, push this project, and open a pull request
- [ ] Paste the PR URL into the organizer's submission form
- [ ] Demo video (prepared separately by the team)

## Before capturing evidence

1. Copy `.env.example` to `.env` and enter valid Db2 connection settings and a long random `SESSION_SECRET`.
2. Set `REQUIRE_DB2=true`.
3. Install `requirements.txt` in a supported Python environment.
4. Run `python -m backend.init_db`.
5. Start the server with `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`.
6. Open `/api/health`. The required evidence is HTTP 200 with `{"status":"ok","db2":true,"storage_mode":"db2"}`.
7. In the same browser session, save a profile, create a reminder, refresh, and verify the profile/reminder remain present.
8. Send one chat message with a valid model key and verify the conversation history is stored.
9. Capture screenshots of the health endpoint, companion profile/reminders, chat, and architecture page. Do not include credentials or personal data.

## GitHub pull request steps

1. Sign in to GitHub and fork `https://github.com/KunalGolaBM/IBM_Db2_TechX_Project_Submission`.
2. Clone your fork, copy the contents of this project into the repository's required submission folder, and preserve `submissions/_template/` conventions.
3. Commit the source, docs, and screenshots. Do not commit `.env`, API keys, passwords, database dumps, or virtual environments.
4. Push your branch to your fork and open a pull request against the organizer's original repository.
5. Use `.github/pull_request_template.md` as the PR description checklist.
6. Copy the created PR URL and submit it through the organizer's Google Form.

## Important verification note

The supplied project archive contained a local `.env` file. The prepared submission package excludes it. If any real credentials in that file were shared, exposed, or committed to a public repository, rotate them before submission.

## Screenshot evidence folder

Place actual screenshots from the live Db2-backed run in `submission/screenshots/`. The folder includes a note describing the expected captures. Screenshots from local-memory mode may be used only to illustrate UI layout and must be labelled as local-mode captures, never as Db2 evidence.
