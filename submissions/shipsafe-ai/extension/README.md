# ShipSafe for IBM Bob

**Your AI writes the code. ShipSafe makes it shippable.**

ShipSafe checks every file your AI assistant is about to write, fixes what it finds with local
**IBM Granite** (a fix only counts if it passes the same checks again), validates SQL on your real
**IBM Db2**, and keeps your team's policies and decisions in Db2 vector tables. It works in **IBM Bob**,
**VS Code** and any MCP-capable AI IDE. **Shippy**, the ShipSafe guide, sets everything up for you.

![IBM Bob's agent calls ShipSafe before it writes a file: recall, Db2 schema, SQL validated on Db2, code check clean, then the write](https://shipsafe-bob.vercel.app/media/bob-agent-checks-before-writing.png)

*Real IBM Bob session: before writing `repository.py`, Bob recalled team decisions, read the Db2 schema,
validated both SQL statements on Db2 and checked the code with ShipSafe. Only then did it write the file.*

## Why

AI assistants write whole files in seconds. Code that compiles can still ship SQL built from strings,
hard-coded keys, `shell=True` and wrong database calls, and scanners only catch it later in CI.
Prompt files and "skills" ask the model to be careful; ShipSafe **checks what it actually wrote**.

## What you get

| | |
|---|---|
| **Checks before writing** | Bob, Copilot agent mode and Claude Code call `shipsafe_check_code` with the file they are about to write: `clean`, `warn` or `block` in about half a second (Python syntax-tree rules, secrets, Bandit, JS/TS rules). |
| **Shippy's safety net** | Every file saved or written to disk, by you or by an agent, is checked too, even if the agent skipped ShipSafe. Problems show in the Problems panel and the Findings view. |
| **Verified Granite fixes** | A CrewAI crew on local IBM Granite fixes the file; the fix is re-checked with the same rules and shown as a diff. |
| **SQL checked by Db2** | Statements are prepared on your real Db2 (never run): Db2 reports unknown tables and columns, with "did you mean CLIENT?" suggestions from the live catalog. |
| **Team brain in IBM Db2** | Team policies and project decisions live in Db2 `VECTOR` tables; your agent recalls them at the start of each task, and every check and fix is recorded per IDE. |
| **Enforced in Claude Code** | *Connect to Claude Code* also installs a pre-write hook: a blocked file cannot be written. |

<p>
<img alt="Shippy's sidebar: setup checklist with the engine and IBM Db2 connected" src="https://shipsafe-bob.vercel.app/media/shippy-sidebar.png" width="300">
<img alt="Bob validates its SQL on IBM Db2 before writing code" src="https://shipsafe-bob.vercel.app/media/bob-agent-sql-on-db2.png" width="300">
</p>

## Get started

1. Install the extension and open a project folder (trust the folder when asked).
2. Click the **ShipSafe** shield in the activity bar. Shippy offers to install the ShipSafe engine:
   it finds Python 3.11–3.13 (or offers to install 3.13) and installs the engine into a private folder
   (a few minutes the first time; about 8 minutes on our test machine).
3. **Connect IBM Db2**: use your own Db2 12.1, or let Shippy start Db2 Community Edition in Docker.
4. **Set up IBM Granite**: Shippy installs or starts Ollama and downloads `granite4:micro` and
   `granite-embedding:30m`, with a progress bar.
5. In IBM Bob, click **Connect** next to "IBM Bob uses ShipSafe", or use **Ask Bob (guarded)** from the
   sidebar. In VS Code, agent mode already sees the ShipSafe MCP server.

Prefer the terminal? `pip install https://shipsafe-bob.vercel.app/downloads/shipsafe-3.1.0-py3-none-any.whl`,
then `shipsafe setup` and `shipsafe connect bob` (or `claude`, `cursor`, `vscode`).

## Make it yours

Every switch changes what ShipSafe does; open them from the sidebar's gear or *ShipSafe: Open settings*.

| Setting | What it does |
|---|---|
| `shipsafe.checkOnSave` / `checkOnType` / `checkOnTypeDelay` | When files are checked |
| `shipsafe.languages`, `shipsafe.exclude` | Which files are checked |
| `shipsafe.minimumSeverity`, `shipsafe.blockAt` | What is shown, and what blocks |
| `shipsafe.ignoredRules` | Rules to stop reporting (the quick fix *Stop reporting X* adds to it) |
| `shipsafe.bandit`, `shipsafe.citePolicies` | Deeper Python scan; Db2 policy citations |
| `shipsafe.fix.maxRounds`, `shipsafe.fix.autoApplyVerified` | Granite fix rounds; apply verified fixes without asking |
| `shipsafe.granite.chatModel` / `embedModel` / `host` | Which models and which Ollama |
| `shipsafe.notifyOn`, `shipsafe.statusBar`, `shipsafe.mascot` | Notifications, status bar, Shippy |
| `shipsafe.autoSetup`, `shipsafe.autoConnectAgent`, `shipsafe.engineSource`, `shipsafe.pythonPath`, `shipsafe.envFile` | How the engine is installed and found |

## Privacy

Everything runs on your machine: Granite in Ollama, the engine in a private Python environment, and Db2
wherever you run it. Database passwords stay in `~/.shipsafe/.env`, never in settings or project files.
No telemetry.

Project, docs and source: [shipsafe-bob.vercel.app](https://shipsafe-bob.vercel.app) ·
[GitHub](https://github.com/ddevSharma/IBM_Db2_TechX_Project_Submission/tree/submission/shipsafe-ai/submissions/shipsafe-ai)
