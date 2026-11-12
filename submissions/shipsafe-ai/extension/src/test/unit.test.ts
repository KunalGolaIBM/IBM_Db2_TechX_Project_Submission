import { strict as assert } from "assert";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { test } from "node:test";
import { BOB_RULES, connectBob, connectClaude, mcpEntry, mergeMcpConfig } from "../connect";
import { diagnosticLevel, diagnosticMessage, isMissingServer, isSupportedLanguage, markdownReport, statusText } from "../format";

const server = { command: "/opt/py/bin/python", args: ["-m", "shipsafe.mcp_server"], env: { SHIPSAFE_ENV_FILE: "/x/.env", PATH: "/bin" } };

test("severity maps to VS Code diagnostic levels", () => {
  assert.equal(diagnosticLevel("critical"), 0);
  assert.equal(diagnosticLevel("high"), 0);
  assert.equal(diagnosticLevel("medium"), 1);
  assert.equal(diagnosticLevel("low"), 2);
  assert.equal(diagnosticLevel("info"), 2);
});

test("diagnostic message names the policy when present", () => {
  const base = { rule_id: "SQLI-DYNAMIC", severity: "critical", category: "security", title: "SQL built from runtime values",
    line: 3, snippet: "", why: "", fix: "Use ? markers.", sources: [] };
  assert.equal(diagnosticMessage(base), "SQL built from runtime values. Use ? markers.");
  const withPolicy = { ...base, policy: { doc_id: "POL-DB2-001", title: "Parameterized SQL", section: "Rule", excerpt: "" } };
  assert.match(diagnosticMessage(withPolicy), /\[POL-DB2-001: Parameterized SQL\]$/);
});

test("status text reflects the verdict", () => {
  assert.match(statusText("block", 2), /2 blocking/);
  assert.match(statusText("warn", 1), /1 warning$/);
  assert.match(statusText("warn", 3), /3 warnings$/);
  assert.match(statusText("clean", 0), /clean/);
  assert.equal(statusText(undefined, 0), "$(shield) ShipSafe");
});

test("supported languages", () => {
  for (const id of ["python", "typescript", "javascriptreact"]) {
    assert.ok(isSupportedLanguage(id));
  }
  assert.ok(!isSupportedLanguage("markdown"));
});

test("markdown report renders strings and objects", () => {
  assert.equal(markdownReport("T", "body"), "# T\n\nbody\n");
  assert.match(markdownReport("T", { a: 1 }), /```json\n\{\n  "a": 1\n\}\n```/);
});

test("mcp entry keeps only ShipSafe env vars and marks Claude as stdio", () => {
  const bob = mcpEntry(server, "bob");
  assert.deepEqual(bob.env, { SHIPSAFE_ENV_FILE: "/x/.env", SHIPSAFE_WORKSPACE: "${workspaceFolder}" });
  assert.deepEqual(mcpEntry(server, "claude").env, { SHIPSAFE_ENV_FILE: "/x/.env" });
  assert.equal(bob.type, undefined);
  assert.equal(mcpEntry(server, "claude").type, "stdio");
  assert.deepEqual(mcpEntry({ command: "c", args: [] }, "bob").env, { SHIPSAFE_WORKSPACE: "${workspaceFolder}" });
  assert.equal(mcpEntry({ command: "c", args: [] }, "claude").env, undefined);
});

test("merge keeps other servers and user options", () => {
  const existing = JSON.stringify({ mcpServers: { other: { command: "x" }, shipsafe: { command: "old", alwaysAllow: ["shipsafe_check_code"] } }, extra: 1 });
  const merged = JSON.parse(mergeMcpConfig(existing, mcpEntry(server, "bob")));
  assert.deepEqual(merged.mcpServers.other, { command: "x" });
  assert.equal(merged.mcpServers.shipsafe.command, "/opt/py/bin/python");
  assert.deepEqual(merged.mcpServers.shipsafe.alwaysAllow, ["shipsafe_check_code"]);
  assert.equal(merged.extra, 1);
  assert.ok(JSON.parse(mergeMcpConfig(undefined, mcpEntry(server, "bob"))).mcpServers.shipsafe);
  assert.ok(JSON.parse(mergeMcpConfig("  ", mcpEntry(server, "bob"))).mcpServers.shipsafe);
  assert.throws(() => mergeMcpConfig("[1,2]", mcpEntry(server, "bob")), /not a JSON object/);
});

test("connectBob and connectClaude write real files", () => {
  const ws = fs.mkdtempSync(path.join(os.tmpdir(), "shipsafe-ext-"));
  try {
    const bobFiles = connectBob(ws, server);
    assert.equal(bobFiles.length, 2);
    const cfg = JSON.parse(fs.readFileSync(path.join(ws, ".bob", "mcp.json"), "utf8"));
    assert.deepEqual(cfg.mcpServers.shipsafe.args, ["-m", "shipsafe.mcp_server"]);
    assert.equal(fs.readFileSync(path.join(ws, ".bob", "rules", "shipsafe.md"), "utf8"), BOB_RULES);
    connectBob(ws, server); // idempotent
    assert.equal(Object.keys(JSON.parse(fs.readFileSync(path.join(ws, ".bob", "mcp.json"), "utf8")).mcpServers).length, 1);
    connectClaude(ws, server);
    assert.equal(JSON.parse(fs.readFileSync(path.join(ws, ".mcp.json"), "utf8")).mcpServers.shipsafe.type, "stdio");
  } finally {
    fs.rmSync(ws, { recursive: true, force: true });
  }
});

test("Bob rules are identical to the Python package copy", () => {
  const pyCopy = path.resolve(__dirname, "..", "..", "..", "src", "shipsafe", "integrations", "bob_rules.md");
  assert.equal(fs.readFileSync(pyCopy, "utf8"), BOB_RULES);
});

test("a missing ShipSafe install is recognised, other failures are not", () => {
  assert.ok(isMissingServer("spawn shipsafe-mcp.exe ENOENT"));
  assert.ok(isMissingServer("ModuleNotFoundError: No module named 'shipsafe'"));
  assert.ok(isMissingServer("ShipSafe server exited with code 9009"));
  assert.ok(!isMissingServer("Timed out waiting for shipsafe_check_code"));
  assert.ok(!isMissingServer("Could not connect to IBM Db2 at 127.0.0.1:50001/TESTDB"));
});
