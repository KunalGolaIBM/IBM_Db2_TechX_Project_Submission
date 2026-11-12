// Runs the extension's own onboarding code outside VS Code, the way a new user's first start does:
// find a Python 3.11-3.13, install the ShipSafe engine from the live site into a private venv,
// start the MCP server the sidebar talks to, and check a dangerous and a safe file.
// Usage (after `npm run compile`): node scripts/platform-smoke.js <empty folder for the engine>
const path = require("path");
const fs = require("fs");
const engine = require("../out/engine.js");
const { McpClient } = require("../out/mcpClient.js");

const BAD = [
  "import subprocess",
  "API_KEY = \"sk_live_9f8e7d6c5b4a3f2e1d\"",
  "def run(cmd):",
  "    subprocess.run(cmd, shell=True)",
  "def find(conn, order_id):",
  "    return conn.execute(f\"SELECT * FROM ORDERS WHERE ID = '{order_id}'\")",
  "",
].join("\n");
const GOOD = ["def add(a: int, b: int) -> int:", "    return a + b", ""].join("\n");

function fail(msg) {
  console.error(`FAIL: ${msg}`);
  process.exit(1);
}

(async () => {
  const dir = path.resolve(process.argv[2] || "engine");
  fs.mkdirSync(dir, { recursive: true });
  console.log(`platform ${process.platform} ${process.arch}, node ${process.version}`);

  const py = await engine.findPython();
  if (!py) fail("no Python 3.11-3.13 found");
  console.log(`python ${py.version} at ${py.executable}`);

  const t0 = Date.now();
  const venv = path.join(dir, "venv");
  const res = await engine.installEngine(py, venv, engine.WHEEL_URL, (l) => console.log(`  | ${l}`));
  if (!res.ok) fail(`engine install: ${res.error}`);
  const vpy = engine.venvPython(venv);
  const version = await engine.engineVersion(vpy);
  console.log(`engine ${version} installed in ${Math.round((Date.now() - t0) / 1000)} s`);
  if (version !== engine.ENGINE_VERSION) fail(`expected ${engine.ENGINE_VERSION}, got ${version}`);

  const client = new McpClient({ command: vpy, args: ["-m", "shipsafe.mcp_server"], cwd: dir, env: { SHIPSAFE_WORKSPACE: dir } },
    () => {}, "platform-smoke", engine.ENGINE_VERSION);
  try {
    const tools = await client.listTools();
    console.log(`MCP tools (${tools.length}): ${tools.join(", ")}`);
    if (tools.length < 11) fail("expected 11 MCP tools");
    const bad = await client.callTool("shipsafe_check_code", { code: BAD, filename: "orders.py" }, 300_000);
    const rules = (bad.issues || []).map((i) => `${i.rule_id || i.rule}:${i.severity}`);
    console.log(`dangerous file -> ${bad.verdict} [${rules.join(", ")}]`);
    if (bad.verdict !== "block") fail("dangerous file was not blocked");
    const good = await client.callTool("shipsafe_check_code", { code: GOOD, filename: "util.py" }, 120_000);
    console.log(`safe file -> ${good.verdict}`);
    if (good.verdict !== "clean") fail("safe file was not clean");
  } finally {
    client.dispose();
  }
  console.log("PASS");
  process.exit(0);
})().catch((e) => fail(e && e.stack ? e.stack : String(e)));
