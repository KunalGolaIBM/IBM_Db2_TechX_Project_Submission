# ShipSafe for IBM Bob

ShipSafe keeps code written by AI assistants production-ready. It works in **IBM Bob**, **VS Code** and any
editor that can install a VS Code extension, and it shares one MCP server with Bob's agent, so the editor and
the agent always get the same answers.

## What you get

- **Problems on save.** Python, JavaScript and TypeScript files are checked when you save them: SQL built
  from runtime values, shell commands, `eval`, unsafe deserialization, leaked keys, XSS sinks, Bandit findings.
  Each problem names the team policy it breaks, retrieved from IBM Db2 vector search.
- **Verified quick fix.** "ShipSafe: fix with Granite (verified)" asks a CrewAI crew running on local IBM
  Granite to fix the file, re-checks the result with the same rules and shows you a diff before anything changes.
- **SQL check on your real database.** Select a statement and run *ShipSafe: Check selected SQL against Db2*.
  Db2 prepares it (nothing runs) and reports syntax errors and unknown tables or columns with suggestions.
- **Project memory.** *Remember a project decision* and *Recall project decisions* store and search decisions
  in a Db2 vector table, so the next session (yours or Bob's) starts with them.
- **Team standards.** *Ask the team standards* answers from your policies with citations.
- **One-click Bob setup.** *Connect to IBM Bob* writes `.bob/mcp.json` and `.bob/rules/shipsafe.md` so Bob
  calls ShipSafe on its own before writing files.
- **Native MCP in VS Code.** On VS Code 1.101+ the extension registers the ShipSafe MCP server automatically.

## Requirements

1. IBM Db2 12.1 (the free IBM Db2 Developer Extension can create one for you).
2. Ollama with `granite4:micro` and `granite-embedding:30m`.
3. The ShipSafe Python package, then `shipsafe setup` once to save the connection to `~/.shipsafe/.env`.

## Settings

| Setting | Default | Purpose |
|---|---|---|
| `shipsafe.pythonPath` | empty | Interpreter that has ShipSafe installed. Empty: use `shipsafe-mcp` from PATH. |
| `shipsafe.envFile` | empty | Settings file with the Db2 and Ollama connection (defaults to `~/.shipsafe/.env`). |
| `shipsafe.checkOnSave` | `true` | Check supported files on save. |
| `shipsafe.citePolicies` | `true` | Attach the matching policy to each problem. |

Everything runs locally: your code goes to your own Db2 and your own Ollama, nowhere else.
