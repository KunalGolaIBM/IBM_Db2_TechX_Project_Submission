"""The MCP server, exercised two ways:

1. End to end over stdio with the official MCP client, exactly as IBM Bob launches it.
2. Every tool function in-process against the live Db2 test schema and Granite.
"""

import asyncio
import json
import os
import sys

import pytest

from shipsafe import mcp_server
from tests.conftest import FIXTURES, TEST_SCHEMA

EXPECTED_TOOLS = {
    "shipsafe_check_code", "shipsafe_check_files", "shipsafe_fix_code", "shipsafe_check_sql", "shipsafe_db2_schema",
    "shipsafe_ask_standards", "shipsafe_remember", "shipsafe_recall", "shipsafe_readiness_check",
    "shipsafe_session_report", "shipsafe_status",
}


def test_stdio_end_to_end_like_bob(db2_schema):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = {**os.environ, "DB2_SCHEMA": TEST_SCHEMA, "SHIPSAFE_WORKSPACE": str(FIXTURES)}
    params = StdioServerParameters(command=sys.executable, args=["-m", "shipsafe.mcp_server"], env=env)

    async def run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                tools = {t.name for t in (await session.list_tools()).tools}
                res = await session.call_tool("shipsafe_check_code", {
                    "code": "import subprocess\nsubprocess.run(cmd, shell=True)\n", "filename": "deploy.py"})
                sql = await session.call_tool("shipsafe_check_sql", {"sql": "DELETE FROM GUARD_EVENTS"})
                return init, tools, json.loads(res.content[0].text), json.loads(sql.content[0].text)

    init, tools, check, sql = asyncio.run(run())
    assert init.serverInfo.name == "shipsafe"
    assert "shipsafe_check_code" in (init.instructions or "")
    assert tools == EXPECTED_TOOLS
    assert check["verdict"] == "block" and check["issues"][0]["rule_id"] == "CMD-SHELL"
    assert check["issues"][0]["policy"]["doc_id"] == "POL-SEC-004"  # cited from Db2 vectors
    assert sql["verdict"] == "block" and sql["issues"][0]["code"] == "NO-WHERE"


@pytest.fixture()
def tools(services, monkeypatch):
    monkeypatch.setattr(mcp_server, "_services", services)
    return mcp_server


def call(fn, **kw):
    return json.loads(fn(**kw))


def test_tool_registry():
    names = {t.name for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert names == EXPECTED_TOOLS


def test_check_tools(tools):
    r = call(tools.shipsafe_check_code, code="x = eval(user)\n", filename="a.py")
    assert r["verdict"] == "block" and r["issues"][0]["rule_id"] == "CODE-EVAL"
    files = call(tools.shipsafe_check_files, paths=["vulnerable_project/src/api.py", "clean_project/src/service.py",
                                                   "missing.py"])
    assert files["verdict"] == "block"
    assert files["files"][2] == {"filename": "missing.py", "error": "not a file"}
    with pytest.raises(PermissionError):
        call(tools.shipsafe_check_files, paths=["../../etc/passwd"])


def test_sql_and_schema_tools(tools):
    assert call(tools.shipsafe_check_sql, sql="SELECT 1 FROM SYSIBM.SYSDUMMY1")["verdict"] == "clean"
    schema = call(tools.shipsafe_db2_schema, tables=["AUDIT_LOG"])
    assert schema["tables"][0]["table"] == "AUDIT_LOG"


def test_memory_and_standards_tools(tools):
    saved = call(tools.shipsafe_remember, text="API errors use RFC 7807 problem+json", kind="convention",
                 project="mcp-test", tags=["api"])
    assert saved["stored"]
    hits = call(tools.shipsafe_recall, query="how should errors be returned", project="mcp-test")
    assert hits[0]["text"].startswith("API errors")
    ans = call(tools.shipsafe_ask_standards, question="Where must secrets be stored?", category="secrets")
    assert ans["citations"][0]["doc_id"] == "POL-SEC-002"


def test_readiness_report_and_status_tools(tools):
    r = call(tools.shipsafe_readiness_check, workspace="vulnerable_project", profile="quick")
    assert r["status"] == "BLOCKED" and r["persisted_in_db2"]
    assert r["risk"]["runs"] >= 1 and r["risk"]["trend"] in ("new", "steady", "improving", "worsening")
    report = call(tools.shipsafe_session_report, since_minutes=60)
    assert any(row["CHECKS"] >= 1 for row in report["by_client"])
    st = call(tools.shipsafe_status)
    assert st["db2"]["connected"] and st["ollama"]["chat_model_ready"]


def test_fix_tool_on_clean_code(tools):
    r = call(tools.shipsafe_fix_code, code="def ok():\n    return 1\n", filename="ok.py")
    assert r["verified"] and r["rounds"] == 0


def test_client_name_fallback():
    assert mcp_server._client(None) == "unknown"
