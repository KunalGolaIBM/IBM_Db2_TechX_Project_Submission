# AsOf as an MCP server

Any agent that speaks the Model Context Protocol can call AsOf before it answers a customer: an IDE assistant,
a desktop assistant, watsonx Orchestrate, or your own LangGraph or CrewAI app. The agent sends its draft and the
date from the booking or account system; AsOf checks every policy claim against the clause version in force on
that date in IBM Db2 and returns what the agent may send.

| Tool | What it does | AsOf endpoint | Role (ASOF_AUTH=users) |
|---|---|---|---|
| `check_answer` | Checks a draft; returns the decision, `send_this`, the clauses each claim was checked against, and a ledger receipt | `POST /api/gate` | checker |
| `policy_in_force` | The version of every clause that applied on a date | `GET /api/policy/timeline` | any |
| `change_impact` | Released and help-centre answers a policy change made stale | `GET /api/impact/{clause}` | auditor |
| `verify_receipt` | Whether the ledger still holds the decision a receipt was issued for | `POST /api/ledger/receipt` | auditor |

The server is a thin client of AsOf's HTTP API. It holds no Db2 credentials and no model key, so every call goes
through the same validation, roles, rate limits, fail-closed check and hash-chained ledger as any other caller.
Its instructions tell the agent to check before stating a policy, never to guess the date, and to send only
`send_this`.

## Run it

It has its own small virtualenv (the MCP SDK and httpx; no Db2 driver, torch or LangChain):

```bash
python3.12 -m venv .venv-mcp
.venv-mcp/bin/pip install -r mcp_server/requirements-mcp.txt
```

With AsOf running (`python src/main.py`), point an MCP client at it. For a desktop client's JSON configuration:

```json
{
  "mcpServers": {
    "asof": {
      "command": "/absolute/path/to/asof/.venv-mcp/bin/python",
      "args": ["/absolute/path/to/asof/mcp_server/asof_mcp.py"],
      "env": { "ASOF_URL": "http://127.0.0.1:8000", "ASOF_MCP_TOKEN": "your AsOf API token" }
    }
  }
}
```

`ASOF_MCP_TOKEN` is needed only when AsOf requires tokens. With per-user tokens, give the agent its own user:
`python -m asof.users add support-agent --roles checker` (add `auditor` for `change_impact` and `verify_receipt`).
The token is sent only to `ASOF_URL`, in the Authorization header; it is never logged or returned.

## Tests

```bash
.venv-mcp/bin/python -m pytest -q mcp_server/tests
ASOF_MCP_LIVE_URL=http://127.0.0.1:8000 .venv-mcp/bin/python -m pytest -q mcp_server/tests   # plus one live check
```

The tests drive the server through a real MCP client session: in memory against a stand-in AsOf API, as a stdio
subprocess (the way an agent launches it), and, when `ASOF_MCP_LIVE_URL` is set, against a running AsOf, where the
check is recorded in the ledger and its receipt verified.
