# Windows Quickstart (PowerShell)

Everything below runs from the project folder, `submissions\db2-locklens`, in **PowerShell**.
Docker Desktop must be running (whale icon steady). Python 3.11 or 3.12 is recommended.

> Status: these steps were written without access to a Windows machine, Docker or Db2. The
> commands follow the official tools' documentation but the first real run is yours; the
> troubleshooting section lists the likely snags.

## 0. Open the folder
```powershell
cd C:\path\to\IBM_Db2_TechX_Project_Submission\submissions\db2-locklens
```

## 1. Create the two environment files (one shared password)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```
It asks for a password (8–64 letters/digits) and writes `.env.db2` (for the Db2 container) and `.env`
(for LockLens) with the same value. Both are git-ignored.

Manual alternative (the two passwords **must** match):
```powershell
copy db2.env.example .env.db2      # edit DB2INST1_PASSWORD
copy .env.example .env             # edit DB2_PASSWORD
```

## 2. Start Db2
```powershell
docker compose up -d
docker logs -f db2server           # Ctrl+C to stop following; wait for "Setup has completed"
```
First start takes several minutes. `docker ps` shows `(healthy)` once the database accepts connections.

## 3. Python environment
Create the virtual environment **outside** this folder (the repository validator rejects the `.pem`
files every venv contains):
```powershell
python -m venv ..\..\.venv
..\..\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```
If activation is blocked: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again.

## 4. Check the Db2 connection and create the incident tables
```powershell
python locklens_cli.py test-connection --wait 900    # retries while Db2 finishes starting
python locklens_cli.py init-db                       # safe to re-run
```
Expected: `OK: Connection to Db2 succeeded.` and four `OK`/`EXISTS` lines.

## 5. Run the tests
```powershell
pytest -v                                            # mocked unit tests; no Db2 needed
```
Expected: all pass; the real-Db2 test is skipped. Please note the result in
`FINAL_TEST_REPORT.md` (section "Run on your machine").

## 6. Create the demo data
```powershell
docker exec db2server rm -rf /tmp/locklens
docker cp scripts db2server:/tmp/locklens
docker exec -it db2server su - db2inst1 -c "db2 connect to testdb && db2 -tvf /tmp/locklens/demo_setup.sql"
```
(Optional real integration test, now possible:)
```powershell
$env:LOCKLENS_RUN_INTEGRATION = "1"; pytest tests/integration -v -s; Remove-Item Env:LOCKLENS_RUN_INTEGRATION
```

## 7. Start the dashboard
```powershell
streamlit run src/app.py
```
Open http://localhost:8501. Turn on *Auto-refresh* in the sidebar if you like.

## 8. The two-session demo
Open **two more** PowerShell windows.

**Window A (blocker, keep open):**
```powershell
docker exec -it db2server su - db2inst1
db2 connect to testdb
db2 +c -tvf /tmp/locklens/demo_session_a.sql
```
**Window B (waiter):**
```powershell
docker exec -it db2server su - db2inst1
db2 connect to testdb
db2 -tvf /tmp/locklens/demo_session_b.sql
```
Window B hangs: that is the lock wait. In the dashboard press *Refresh now* and look at *Live Lock Monitor*,
*Blocking Relationships*, *Diagnostics* and *Incident History*.

**Resolve:** in Window A run `db2 rollback` (or `db2 commit`). Window B finishes; refresh the dashboard.

**Clean up** (inside a container shell): `db2 connect to testdb` then `db2 -tvf /tmp/locklens/demo_cleanup.sql`.

## 9. Stop everything
```powershell
docker compose stop            # keeps the data volume
docker compose down -v         # also deletes the Db2 data volume (everything is re-created next time)
```

## Troubleshooting
| Symptom | Likely cause and fix |
|---|---|
| `pip install` fails building `ibm_db` | Use Python 3.11 or 3.12 (a prebuilt wheel exists for common versions); upgrade pip |
| `ImportError`/DLL error when importing `ibm_db` | Install the *Microsoft Visual C++ Redistributable (x64)* and retry |
| `The ibm_db driver is not installed` | Venv not activated or `pip install -r requirements-dev.txt` not run |
| `docker compose up` says `.env.db2` not found | Step 1 not done |
| Container exits immediately | Check `docker logs db2server`; `privileged: true` must be present; give Docker Desktop ≥ 4 GB RAM (Settings → Resources) |
| `port is already allocated` (50000) | Another Db2/service uses it: `netstat -ano \| findstr :50000`, stop it, or change the left side of `ports:` and `DB2_PORT` |
| `unreachable` / `database_not_found` | Db2 is still starting; use `--wait 900` and watch `docker logs db2server` |
| `invalid_credentials` | `DB2_PASSWORD` in `.env` differs from `DB2INST1_PASSWORD` in `.env.db2`. If you changed it after the first start, run `docker compose down -v` and start again |
| Dashboard shows `Not authorized` notes (SQL0551N) | The user lacks `EXECUTE` on the `MON_GET_*` routines (see README → Db2 privileges) |
| Dashboard says incident tables don't exist | Run `python locklens_cli.py init-db` (or Settings → Initialise incident tables) |
| Window B does not block | Window A must run with `db2 +c` (autocommit off) and must not have committed; B must be the `UPDATE` script; both must use the same table row |
| Lock wait shows but the table is "not resolved" | `MON_FORMAT_LOCK_NAME` privilege or format difference; the blocking relationship is still valid |
| `SQL0911N` / lock timeout in B | B waited longer than its timeout; roll back A sooner or raise `SET CURRENT LOCK TIMEOUT` in `demo_session_b.sql` |
| Windows changed line endings in SQL files | `.gitattributes` keeps `*.sql` as LF; if needed run `git add --renormalize .` |
| `streamlit` not found | Activate the venv (step 3) |
| Validator reports `.pem`/forbidden files | A venv exists inside `submissions\db2-locklens`; move it out (step 3) |
