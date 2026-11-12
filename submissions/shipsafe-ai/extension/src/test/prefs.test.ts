import { strict as assert } from "assert";
import * as fs from "fs";
import * as http from "http";
import * as os from "os";
import * as path from "path";
import { test } from "node:test";
import * as engine from "../engine";
import { CheckResult, Issue } from "../format";
import { mascotSvg } from "../mascot";
import { applyPrefs, DEFAULT_PREFS, engineEnv, isIgnored, matchesGlob, normalizePrefs, severityCounts } from "../prefs";

const issue = (rule_id: string, severity: string, line = 1): Issue => ({ rule_id, severity, category: "security", title: rule_id,
  line, snippet: "", why: "", fix: "", sources: ["shipsafe_code_rules"] });
const result = (issues: Issue[]): CheckResult => ({ verdict: "block", language: "python", issues, duration_ms: 5, summary: "" });

test("settings are validated and clamped", () => {
  const p = normalizePrefs({ minimumSeverity: "bogus", blockAt: "critical", fixMaxRounds: 99, checkOnTypeDelayMs: 1,
    ignoredRules: [" b404-blacklist ", 7, ""], languages: "python", notifyOn: "loud", mascot: false, ollamaHost: "http://h:1/" });
  assert.equal(p.minimumSeverity, "low");
  assert.equal(p.blockAt, "critical");
  assert.equal(p.fixMaxRounds, 5);
  assert.equal(p.checkOnTypeDelayMs, 300);
  assert.deepEqual(p.ignoredRules, ["B404-BLACKLIST"]);
  assert.deepEqual(p.languages, DEFAULT_PREFS.languages);
  assert.equal(p.notifyOn, "block");
  assert.equal(p.mascot, false);
  assert.equal(p.ollamaHost, "http://h:1");
});

test("severity floor, ignored rules and block threshold change the verdict", () => {
  const r = result([issue("SQLI-DYNAMIC", "critical", 6), issue("B404-BLACKLIST", "low", 1), issue("CMD-SHELL", "high", 9)]);
  assert.equal(applyPrefs(r, DEFAULT_PREFS).verdict, "block");
  const onlyLow = applyPrefs(r, { ...DEFAULT_PREFS, ignoredRules: ["SQLI-DYNAMIC", "CMD-*"] });
  assert.equal(onlyLow.verdict, "warn");
  assert.deepEqual(onlyLow.issues.map((i) => i.rule_id), ["B404-BLACKLIST"]);
  assert.match(onlyLow.summary, /2 hidden by your ShipSafe settings/);
  const strict = applyPrefs(result([issue("X", "medium")]), { ...DEFAULT_PREFS, blockAt: "medium" });
  assert.equal(strict.verdict, "block");
  const quiet = applyPrefs(result([issue("B404", "low")]), { ...DEFAULT_PREFS, minimumSeverity: "medium" });
  assert.equal(quiet.verdict, "clean");
  assert.equal(quiet.issues.length, 0);
});

test("ignore entries match exact ids or prefixes", () => {
  assert.ok(isIgnored("b404-blacklist", ["B404-BLACKLIST"]));
  assert.ok(isIgnored("B602-SUBPROCESS", ["B6*"]));
  assert.ok(!isIgnored("SQLI-DYNAMIC", ["SQL"]));
});

test("engine env carries behaviour settings and only explicit model overrides", () => {
  assert.deepEqual(engineEnv(DEFAULT_PREFS), { SHIPSAFE_BANDIT: "true", SHIPSAFE_CITE_POLICIES: "true", SHIPSAFE_FIX_ROUNDS: "3" });
  const env = engineEnv({ ...DEFAULT_PREFS, bandit: false, chatModel: "granite3.3:8b", ollamaHost: "http://gpu:11434" });
  assert.equal(env.SHIPSAFE_BANDIT, "false");
  assert.equal(env.SHIPSAFE_CHAT_MODEL, "granite3.3:8b");
  assert.equal(env.OLLAMA_HOST, "http://gpu:11434");
  assert.ok(!("DB2_PASSWORD" in env));
});

test("exclude globs", () => {
  assert.ok(matchesGlob("web/node_modules/x/index.js", "**/node_modules/**"));
  assert.ok(matchesGlob("node_modules/x.js", "**/node_modules/**"));
  assert.ok(matchesGlob("src\\gen\\a.py", "src/gen/*.py"));
  assert.ok(matchesGlob("tests/test_a.py", "**/test_*.py"));
  assert.ok(!matchesGlob("src/app.py", "**/node_modules/**"));
  assert.ok(!matchesGlob("src/gen/sub/a.py", "src/gen/*.py"));
});

test("severity counts", () => {
  assert.equal(severityCounts([issue("a", "low"), issue("b", "critical"), issue("c", "low")]), "1 critical, 2 low");
});

test("python probe accepts 3.11-3.13 only", () => {
  assert.deepEqual(engine.parseProbe("3.13|C:\\Py\\python.exe\n"), { version: "3.13", executable: "C:\\Py\\python.exe" });
  assert.equal(engine.parseProbe("3.14|/usr/bin/python3"), undefined);
  assert.equal(engine.parseProbe("3.10|/usr/bin/python3"), undefined);
  assert.equal(engine.parseProbe("garbage"), undefined);
  const win = engine.pythonCandidates("win32", { LOCALAPPDATA: "C:\\L" });
  assert.deepEqual(win[0], { command: "py", args: ["-3.13"] });
  assert.ok(win.some((c) => c.command === path.join("C:\\L", "Programs", "Python", "Python313", "python.exe")));
  assert.equal(engine.pythonCandidates("linux", {})[0].command, "python3.13");
});

test("install commands per platform", () => {
  assert.match(engine.pythonInstallCommand("win32")!, /^winget install .*Python\.Python\.3\.13/);
  assert.equal(engine.pythonInstallCommand("darwin", true), "brew install python@3.13");
  assert.equal(engine.pythonInstallCommand("linux"), undefined);
  assert.match(engine.ollamaInstallCommand("linux")!, /ollama\.com\/install\.sh/);
  assert.equal(engine.ollamaInstallCommand("darwin", false), undefined);
});

test("version compare and pip progress", () => {
  assert.ok(engine.isOlder("3.0.0", "3.1.0"));
  assert.ok(!engine.isOlder("3.1.0", "3.1.0"));
  assert.ok(!engine.isOlder("3.10.0", "3.9.9"));
  assert.equal(engine.pipProgress("Collecting crewai>=0.80"), "getting crewai");
  assert.equal(engine.pipProgress("Installing collected packages: a, b"), "installing packages");
  assert.equal(engine.pipProgress("  Using cached x.whl"), undefined);
  assert.match(engine.WHEEL_URL, /shipsafe-3\.1\.0-py3-none-any\.whl$/);
});

test("shared env file is merged in place and stays private", () => {
  assert.deepEqual(engine.parseEnv("# c\nA=1\nB = 'two'\n\nbad line\n"), { A: "1", B: "two" });
  const merged = engine.mergeEnvText("# keep me\nDB2_HOST=old\nOTHER=x\n", { DB2_HOST: "db", DB2_PORT: "50000" });
  assert.equal(merged, "# keep me\nDB2_HOST=db\nOTHER=x\nDB2_PORT=50000\n");
  assert.match(engine.mergeEnvText("", { A: "1" }), /^# ShipSafe connection settings.*\nA=1\n$/s);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "shipsafe-env-"));
  const file = path.join(dir, "sub", ".env");
  engine.writeSharedEnv({ DB2_PASSWORD: "s3cret" }, file);
  engine.writeSharedEnv({ DB2_HOST: "h" }, file);
  assert.deepEqual(engine.parseEnv(fs.readFileSync(file, "utf8")), { DB2_PASSWORD: "s3cret", DB2_HOST: "h" });
  if (process.platform !== "win32") {
    assert.equal(fs.statSync(file).mode & 0o777, 0o600);
  }
});

test("finds programs on PATH and builds the Db2 container command", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "shipsafe-path-"));
  const exe = path.join(dir, process.platform === "win32" ? "shipsafe-mcp.exe" : "shipsafe-mcp");
  fs.writeFileSync(exe, "");
  assert.equal(engine.findOnPath("shipsafe-mcp", `${dir}${path.delimiter}/nowhere`), exe);
  assert.equal(engine.findOnPath("not-a-tool-xyz", dir), undefined);
  const args = engine.db2DockerArgs("pw123", 50001);
  assert.deepEqual(args.slice(0, 4), ["run", "-d", "--name", "shipsafe-db2"]);
  assert.ok(args.includes("50001:50000") && args.includes("LICENSE=accept") && args.includes("DB2INST1_PASSWORD=pw123"));
  assert.equal(engine.venvPython("/v", "linux"), path.join("/v", "bin", "python"));
});

test("run streams output and reports exit codes", async () => {
  const lines: string[] = [];
  const ok = await engine.run(process.execPath, ["-e", "console.log('a');console.error('b');console.log('c')"], { onLine: (l) => lines.push(l) });
  assert.equal(ok.code, 0);
  assert.equal(ok.stdout, "a\nc\n");
  assert.deepEqual(lines.sort(), ["a", "b", "c"]);
  assert.equal((await engine.run(process.execPath, ["-e", "process.exit(3)"])).code, 3);
  assert.equal((await engine.run("definitely-not-a-program-xyz", [])).code, -1);
  assert.equal((await engine.run(process.execPath, ["-e", "setTimeout(()=>{},5000)"], { timeoutMs: 200 })).code, -2);
});

test("Ollama status and model pull over the real HTTP API shape", async () => {
  const server = http.createServer((req, res) => {
    if (req.url === "/api/tags") {
      res.end(JSON.stringify({ models: [{ name: "granite4:micro" }, { name: "granite-embedding:30m" }] }));
    } else if (req.url === "/api/pull") {
      res.write(JSON.stringify({ status: "pulling manifest" }) + "\n");
      res.write(JSON.stringify({ status: "downloading", total: 200, completed: 100 }) + "\n");
      res.end(JSON.stringify({ status: "success", total: 200, completed: 200 }) + "\n");
    }
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const host = `http://127.0.0.1:${(server.address() as { port: number }).port}`;
  try {
    const models = await engine.ollamaModels(host);
    assert.ok(models && engine.hasModel(models, "granite4:micro") && !engine.hasModel(models, "granite3.3"));
    const seen: (number | undefined)[] = [];
    await engine.pullModel(host, "granite4:micro", (pct) => seen.push(pct));
    assert.deepEqual(seen, [undefined, 50, 100]);
  } finally {
    server.close();
  }
  assert.equal(await engine.ollamaModels("http://127.0.0.1:9", 500), undefined);
});

test("Shippy renders every mood as standalone SVG", () => {
  for (const mood of ["happy", "alert", "thinking", "celebrate", "sleepy"] as const) {
    const svg = mascotSvg(mood, 100);
    assert.match(svg, /^<svg [^>]*width="100" height="112"/);
    assert.ok(svg.endsWith("</svg>") && !svg.includes("undefined"));
  }
});

test("agent names from Db2 are readable and Bob gets the ShipSafe workflow", async () => {
  const { agentLabel, bobTaskPrompt } = await import("../format");
  assert.equal(agentLabel("shipsafe-vscode"), "Shippy (files you or an agent saved)");
  assert.equal(agentLabel("IBM Bob"), "IBM Bob agent");
  assert.equal(agentLabel("claude-code"), "Claude Code");
  assert.equal(agentLabel("Visual Studio Code"), "VS Code agent mode");
  assert.equal(agentLabel("cli"), "CLI / git hook");
  assert.equal(agentLabel("pytest"), "pytest");
  assert.equal(agentLabel("mcp-use", true), "IBM Bob agent");
  assert.equal(agentLabel("mcp-use"), "MCP agent (mcp-use)");
  const prompt = bobTaskPrompt("  Add an order lookup ");
  assert.ok(prompt.startsWith("Add an order lookup\n\n"));
  for (const tool of ["shipsafe_recall", "shipsafe_check_code", "shipsafe_fix_code", "shipsafe_check_sql", "shipsafe_readiness_check"]) {
    assert.ok(prompt.includes(tool), tool);
  }
});

test("Claude Code gets a pre-write hook; Bob gets the workspace and a long timeout", async () => {
  const { hookCommand, mergeHookSettings, connectBob, connectClaude } = await import("../connect");
  assert.equal(hookCommand({ command: "C:\\Py\\python.exe", args: [] }), '"C:/Py/python.exe" -m shipsafe.cli guard-hook');
  assert.equal(hookCommand({ command: "/v/bin/shipsafe-mcp", args: [] }), '"/v/bin/shipsafe" guard-hook');
  assert.equal(hookCommand({ command: "C:\\S\\shipsafe-mcp.exe", args: [] }), '"C:/S/shipsafe.exe" guard-hook');
  const merged = JSON.parse(mergeHookSettings(JSON.stringify({ model: "m", hooks: { PreToolUse: [{ matcher: "Bash", hooks: [{ type: "command", command: "mine" }] }] } }), "X guard-hook"));
  const again = JSON.parse(mergeHookSettings(JSON.stringify(merged), "Y guard-hook"));
  assert.equal(again.model, "m");
  assert.equal(again.hooks.PreToolUse.length, 2);
  assert.equal(again.hooks.PreToolUse[1].hooks[0].command, "Y guard-hook");
  assert.throws(() => mergeHookSettings("[1]", "c"));
  const ws = fs.mkdtempSync(path.join(os.tmpdir(), "shipsafe-conn-"));
  const server = { command: "/py", args: ["-m", "shipsafe.mcp_server"], env: { SHIPSAFE_WORKSPACE: ws } };
  connectBob(ws, server);
  const bob = JSON.parse(fs.readFileSync(path.join(ws, ".bob", "mcp.json"), "utf8")).mcpServers.shipsafe;
  assert.equal(bob.timeout, 600000);
  assert.equal(bob.env.SHIPSAFE_WORKSPACE, "${workspaceFolder}");
  const files = connectClaude(ws, server);
  assert.ok(files.some((f) => f.endsWith(path.join(".claude", "settings.json"))));
});
