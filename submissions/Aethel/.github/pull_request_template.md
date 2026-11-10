## IBM Db2Hack 2026 — Aethel

### Summary
- [ ] Functional Aethel wellbeing companion prototype
- [ ] IBM Db2 persistence for profiles, reminders, conversation logs, and community notes
- [ ] LangGraph workflow for contextual analysis and supportive AI response
- [ ] Setup documentation, architecture, and screenshots

### Verification
- [ ] `python -m unittest discover -s backend/tests -v`
- [ ] `python -m backend.init_db` completed against the configured Db2 database
- [ ] `GET /api/health` reports `db2: true` and `storage_mode: "db2"`
- [ ] Created and retrieved a profile and reminder using the same browser session
- [ ] No `.env`, API key, password, or private credential is included

### Evidence
- Screenshots: `submission/screenshots/`
- Architecture: `frontend/assets/architecture.png`
- Demo/deployment link (if available):

### Notes
State clearly whether the submitted run used live IBM Db2 or the local-memory development fallback.
