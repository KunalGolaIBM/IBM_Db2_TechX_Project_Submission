# Getting started

About ten minutes, most of it downloading the Granite models once. All downloads are also on **[https://shipsafe-bob.vercel.app](https://shipsafe-bob.vercel.app)**.

**You need:** Python 3.11–3.13 · Docker Desktop or WSL 2 · about 3 GB free disk · VS Code or IBM Bob.

## 1. Start IBM Db2 (10 min)

Easiest: install IBM's **Db2 Developer Extension** in VS Code (it also works in IBM Bob), click the Db2
icon, then **Create Db2 instance**. You get Db2 Community Edition with a `TESTDB` database.

```bash
code --install-extension IBM.db2-for-luw
```

Or run the container yourself:

```bash
docker run -d --name db2server --privileged -p 50001:50000 \
  -e LICENSE=accept -e DB2INST1_PASSWORD=<choose-one> -e DBNAME=TESTDB \
  icr.io/db2_community/db2
```

## 2. Pull the Granite models (5 min)

Install Ollama from ollama.com, then:

```bash
ollama pull granite4:micro          # chat, about 2.1 GB
ollama pull granite-embedding:30m   # embeddings, 62 MB, 384 dimensions
```

## 3. Install ShipSafe and run setup (2 min)

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install ./submissions/shipsafe-ai               # or the published wheel
export DB2_HOST=127.0.0.1 DB2_PORT=50001 DB2_NAME=TESTDB DB2_USERNAME=db2inst1 DB2_PASSWORD=<yours>
shipsafe setup
```

`shipsafe setup` saves the connection to `~/.shipsafe/.env`, checks both models (add `--pull` to download
missing ones), creates the schema (tables, views, stored procedures), indexes the team policies as
vectors and opens the project-memory store. Expected output:

```
[OK]   Settings saved to ~/.shipsafe/.env
[OK]   Granite model granite4:micro is installed
[OK]   Granite model granite-embedding:30m is installed
[OK]   IBM Db2 DB2 v12.1.5.0 127.0.0.1:50001/TESTDB, schema SHIPSAFE: 11 tables, 2 views, 3 stored procedures
[OK]   Policy vectors in Db2: 13 chunks
[OK]   Project memory store: 0 memories
```

## 4. Connect your IDE (1 min)

Run inside the project you work on:

| IDE | Command | What it writes |
|---|---|---|
| IBM Bob | `shipsafe connect bob` | `.bob/mcp.json` and `.bob/rules/shipsafe.md` |
| VS Code | `shipsafe connect vscode` | `.vscode/mcp.json` |
| Claude Code | `shipsafe connect claude` | `.mcp.json` |
| Cursor | `shipsafe connect cursor` | `.cursor/mcp.json` |

Reload the IDE. The `shipsafe` server and its 11 tools appear in the MCP list. In Bob, the rules file
makes the agent call ShipSafe without being asked.

**Extension (Problems panel, quick fix, commands):**

```bash
code   --install-extension shipsafe-3.0.0.vsix
bobide --install-extension shipsafe-3.0.0.vsix
```

Set `shipsafe.pythonPath` to the interpreter from step 3 if `shipsafe-mcp` is not on your PATH.

**Every commit, with or without an assistant:**

```bash
shipsafe hook        # git pre-commit hook: shipsafe check --staged
```

## Try it

```bash
shipsafe check app.py                              # clean / warn / block, exit code 1 on block
shipsafe fix app.py --write                         # Granite crew + verification; writes only if verified
shipsafe sql "SELECT NAME FROM CUSTOMERS WHERE ID = ?"
shipsafe remember "Money is DECIMAL(15,2), never float" --kind decision
shipsafe recall "add a refund endpoint"
shipsafe ask "How must user input reach Db2 queries?"
shipsafe report                                     # what was caught, per IDE (Db2 stored procedure)
shipsafe doctor                                     # health of Db2, vectors, Granite and scanners
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Every command waits about 10 s, then works | Use `DB2_HOST=127.0.0.1`. `localhost` may resolve to IPv6 first, and Docker/WSL forwards Db2 on IPv4 only. |
| `SQL30081N` communication error | Db2 is not running: start it from the Db2 extension, or `docker start db2server` / `podman start db2server` in WSL. |
| `Granite chat model ... is not installed` | `ollama pull granite4:micro` (or `shipsafe setup --pull`). |
| `Ollama is not reachable` | Start the Ollama app, or `ollama serve`. |
| Tools do not appear in Bob | Check `.bob/mcp.json` points at a Python that has ShipSafe installed; `shipsafe connect bob --python <path>` sets it. |
| `pip install` fails on Python 3.14 | Use Python 3.13 or older (CrewAI does not support 3.14 yet). |
