# Troubleshooting

## Db2 container
- **Wait for it.** First start takes several minutes. `docker logs -f quantummedx-db2` and wait for "Setup has completed."
- **Container exits immediately:** the compose file needs `privileged: true` (already set) and `LICENSE=accept` in `database/.env.db2`. On Windows use Docker Desktop with the WSL 2 backend.
- **Port 50000 already in use:** stop the other Db2 or change the left side of `"50000:50000"` in `database/docker-compose.yml` and set `DB2_PORT` in `.env` to match.
- **Apple Silicon:** the Db2 image is amd64; enable emulation in Docker Desktop (slow but works) or use a Linux/Windows machine.

## Connection errors from Python
- `SQL1042C` right after a fresh start, and `docker logs quantummedx-db2` shows `SQL1001N ... is not a valid database name`: **Db2 database names are limited to 8 characters.** The project uses `QMEDX`. If your container was created with an older, longer name, open a shell in it (`docker exec -it quantummedx-db2 bash`), run `su - db2inst1`, then `db2 "create database QMEDX using codeset UTF-8 territory US"`, and set `DB2_DATABASE=QMEDX` in `.env`.
- `SQL30082N` with a reason about user name or password: `DB2_PASSWORD` in `.env` must equal `DB2INST1_PASSWORD` in `database/.env.db2`; `DB2_USER` is `db2inst1`.
- `SQL1013N` (database not found): `DB2_DATABASE` must equal `DBNAME` in `database/.env.db2` (`QMEDX`), and the container must have finished setup.
- `SQL30081N` or connection refused: the container is not ready, or the port or host is wrong.
- `pip install ibm_db` fails: use Python 3.10 to 3.12 with a recent pip, and a 64-bit Python. The wheel downloads IBM's client driver on install, so the network must allow it.
- API returns 503 "Db2 setup required": `DB2_PASSWORD` is empty. 503 "not reachable": check the container and `.env`.

## Windows: `SQL1042C` even though Db2 is healthy
If the database exists and connects from inside the container (`docker exec quantummedx-db2 su - db2inst1 -c "db2 connect to QMEDX"`) but Python on Windows still fails with `SQL1042C`, the Windows Db2 client driver inside `ibm_db` is the problem (the same error appears whether or not the database exists). Two options:
1. Try `pip install --force-reinstall --no-cache-dir ibm_db`, make sure the environment variable `IBM_DB_HOME` is not set to another Db2 install, and install the latest Microsoft Visual C++ Redistributable.
2. Run the backend in a Linux container instead (no Windows driver involved):
```powershell
cd database
docker compose up -d --build
docker compose exec backend python scripts/init_db.py
docker compose exec backend pytest -v
```
The API is then at http://localhost:8000 and the frontend works unchanged.

## Schema
- `init_db.py` can be re-run. It skips objects that already exist. To start over: `docker compose down -v` in `database/`, then bring Db2 up and run `init_db.py` again (this deletes all data).
- If a statement fails, send the exact `SQL...N` code and message; do not edit the schema blindly.

## Agents
- `CREWAI` mode returns 400 until `LLM_PROVIDER`, `LLM_MODEL` and `LLM_API_KEY` are set in `.env` and the backend is restarted. Providers CrewAI does not support natively (for example Groq) also need `pip install litellm`.
- `DETERMINISTIC` mode needs no LLM and exercises the same tools, activity logging and report verification.
- Quantum runs take longer with more qubits or iterations; start with 4 qubits and 30 iterations.

## Frontend
- Blank data or network errors: check that the backend runs on port 8000 and `frontend/.env.local` has `VITE_API_URL=http://localhost:8000`. CORS allows `http://localhost:5173` by default (`CORS_ORIGINS` in `.env`).
