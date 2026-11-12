import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";
import { connectBob, connectClaude } from "./connect";
import { ENGINE_VERSION, SITE } from "./engine";
import { FindingsProvider } from "./findingsTree";
import { agentLabel, bobTaskPrompt, CheckResult, diagnosticLevel, diagnosticMessage, isMissingServer, markdownReport, statusText } from "./format";
import { HealthItem, HomeState, HomeViewProvider } from "./homeView";
import { Mood } from "./mascot";
import { McpClient, ServerCommand } from "./mcpClient";
import { Setup } from "./onboarding";
import { applyPrefs, engineEnv, matchesGlob, normalizePrefs, Prefs, rank, severityCounts } from "./prefs";

let client: McpClient | undefined;
let output: vscode.OutputChannel;
let diagnostics: vscode.DiagnosticCollection;
let status: vscode.StatusBarItem;
let setup: Setup;
let home: HomeViewProvider;
let findings: FindingsProvider;
const lastResults = new Map<string, CheckResult>();
const rawResults = new Map<string, CheckResult>();
const stats = { checks: 0, blocked: 0, fixed: 0 };
let busy: { mood: Mood; say: string } | undefined;
let lastEvent: { mood: Mood; say: string } | undefined;
let extContext: vscode.ExtensionContext;
let agentRows: { name: string; checks: number; blocked: number; fixed: number }[] | null = null;
let canAskBob = false;
const BOB_SEND = "bob-code.sendMessageWithHiddenPrompt";
const mcpChanged = new vscode.EventEmitter<void>();

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));

function workspaceFolder(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

/** Read every ShipSafe setting into validated preferences. */
export function prefs(): Prefs {
  const c = vscode.workspace.getConfiguration("shipsafe");
  return normalizePrefs({
    checkOnSave: c.get("checkOnSave"), checkOnType: c.get("checkOnType"), checkOnTypeDelayMs: c.get("checkOnTypeDelay"),
    languages: c.get("languages"), minimumSeverity: c.get("minimumSeverity"), blockAt: c.get("blockAt"),
    ignoredRules: c.get("ignoredRules"), exclude: c.get("exclude"), bandit: c.get("bandit"), citePolicies: c.get("citePolicies"),
    fixMaxRounds: c.get("fix.maxRounds"), fixAutoApplyVerified: c.get("fix.autoApplyVerified"),
    chatModel: c.get("granite.chatModel"), embedModel: c.get("granite.embedModel"), ollamaHost: c.get("granite.host"),
    notifyOn: c.get("notifyOn"), statusBar: c.get("statusBar"), mascot: c.get("mascot"),
  });
}

/** How to launch the ShipSafe MCP server (the same server IBM Bob talks to). */
export function serverCommand(): ServerCommand {
  const cfg = vscode.workspace.getConfiguration("shipsafe");
  const envFile = (cfg.get<string>("envFile") || "").trim();
  const env: NodeJS.ProcessEnv = { ...engineEnv(prefs()) };
  const ws = workspaceFolder();
  if (ws) {
    env.SHIPSAFE_WORKSPACE = ws;
  }
  if (envFile) {
    env.SHIPSAFE_ENV_FILE = envFile.replace(/^~(?=$|[\\/])/, os.homedir());
  }
  const e = setup?.engine;
  if (e) {
    return { command: e.command, args: e.args, cwd: ws, env };
  }
  const python = (cfg.get<string>("pythonPath") || "").trim();
  if (python) {
    return { command: python, args: ["-m", "shipsafe.mcp_server"], cwd: ws, env };
  }
  return { command: process.platform === "win32" ? "shipsafe-mcp.exe" : "shipsafe-mcp", args: [], cwd: ws, env };
}

function getClient(): McpClient {
  if (!client) {
    client = new McpClient(serverCommand(), (line) => output.appendLine(line), "shipsafe-vscode", ENGINE_VERSION);
  }
  return client;
}

function restartServer(): void {
  client?.dispose();
  client = undefined;
}

async function call<T>(tool: string, args: Record<string, unknown>, title: string, timeoutMs?: number): Promise<T> {
  if (!vscode.workspace.isTrusted) {
    void vscode.window.showInformationMessage("ShipSafe runs once you trust this folder.", "Trust folder")
      .then((x) => x && vscode.commands.executeCommand("workbench.trust.manage"));
    throw new Error("This folder is in Restricted Mode; trust it to let ShipSafe run.");
  }
  if (!setup.engine) {
    throw new Error("ENOENT: the ShipSafe engine is not installed yet");
  }
  return vscode.window.withProgress(
    { location: vscode.ProgressLocation.Window, title: `ShipSafe: ${title}` },
    async () => (await getClient().callTool(tool, args, timeoutMs)) as T,
  );
}

function relPath(doc: vscode.TextDocument): string {
  return vscode.workspace.asRelativePath(doc.uri, false);
}

async function showMarkdown(title: string, body: unknown): Promise<void> {
  const doc = await vscode.workspace.openTextDocument({ language: "markdown", content: markdownReport(title, body) });
  await vscode.commands.executeCommand("markdown.showPreviewToSide", doc.uri);
}

let missingServerShown = false;

function reportError(action: string, err: unknown): void {
  const message = err instanceof Error ? err.message : String(err);
  output.appendLine(`[${action}] ${message}`);
  if (isMissingServer(message)) {
    restartServer();
    void setup.resolveEngine();
    if (missingServerShown) {
      return;
    }
    missingServerShown = true;
    void vscode.window.showWarningMessage("Shippy needs the ShipSafe engine first. Install it now? (one click; a few minutes the first time)",
      "Install", "Open ShipSafe").then((pick) => {
      if (pick === "Install") {
        void setup.installEngine().then(afterEngineReady);
      } else if (pick) {
        void vscode.commands.executeCommand("shipsafe.home.focus");
      }
    });
    return;
  }
  void vscode.window.showErrorMessage(`ShipSafe could not ${action}: ${message}`, "Show log").then((pick) => {
    if (pick) {
      output.show();
    }
  });
}

// --------------------------------------------------------------- home panel state
function health(): HealthItem[] {
  const ws = workspaceFolder();
  const agentName = setup.isBob() ? "IBM Bob" : "AI agent";
  const agentOk = setup.isBob() ? setup.agentConnected(ws) : true;
  if (!vscode.workspace.isTrusted) {
    return [{ id: "engine", label: "Trust this folder", state: "missing", optional: false,
      detail: "VS Code opened it in Restricted Mode, which pauses extensions. Trust it and Shippy sets everything up.",
      action: { label: "Trust", command: "shipsafe.trustFolder" } }];
  }
  return [
    { id: "engine", label: "ShipSafe engine", state: setup.engineState, detail: setup.engineDetail, optional: false,
      action: setup.engineState === "missing" ? { label: "Install", command: "shipsafe.installEngine" } : undefined },
    { id: "db2", label: "IBM Db2 (the brain)", state: setup.db2State, detail: setup.db2Detail, optional: false,
      action: setup.db2State === "missing" && setup.engine ? { label: "Connect", command: "shipsafe.setupDb2" } : undefined },
    { id: "granite", label: "IBM Granite (local AI)", state: setup.graniteState, detail: setup.graniteDetail, optional: false,
      action: setup.graniteState === "missing" ? { label: "Set up", command: "shipsafe.setupGranite" } : undefined },
    { id: "agent", label: `${agentName} uses ShipSafe`, state: !ws ? "unknown" : agentOk ? "ok" : "missing", optional: false,
      detail: !ws ? "Open a folder to connect the agent." : setup.isBob()
        ? (agentOk ? "Bob checks code with ShipSafe before writing it." : "Let Bob's agent call ShipSafe while it codes.")
        : "Registered for agent mode automatically (MCP).",
      action: ws && !agentOk ? { label: "Connect", command: "shipsafe.connectBob" } : undefined },
  ];
}

function currentFile() {
  const doc = vscode.window.activeTextEditor?.document;
  const r = doc && lastResults.get(doc.uri.toString());
  if (!doc || !r) {
    return undefined;
  }
  return { name: path.basename(doc.fileName), verdict: r.verdict, summary: r.summary,
    issues: r.issues.map((i) => ({ line: i.line, severity: i.severity, title: i.title, rule: i.rule_id })) };
}

function homeState(): HomeState {
  const p = prefs();
  const file = currentFile();
  let mood: Mood = "happy";
  let say: string;
  if (busy) {
    ({ mood, say } = busy);
  } else if (!vscode.workspace.isTrusted) {
    mood = "sleepy";
    say = "Hi, I'm <b>Shippy</b>! This folder is in <b>Restricted Mode</b>, so I'm paused. Click <b>Trust</b> below and I'll set everything up.";
  } else if (setup.engineState === "missing") {
    say = "Hi, I'm <b>Shippy</b>! I check AI-written code before it ships. First I need my engine: click <b>Install</b> (a few minutes the first time, all local).";
  } else if (setup.engineState === "working") {
    mood = "thinking";
    say = esc(setup.engineDetail);
  } else if (lastEvent) {
    ({ mood, say } = lastEvent);
  } else if (file?.verdict === "block") {
    mood = "alert";
    const blocking = file.issues.filter((i) => rank(i.severity) >= rank(p.blockAt)).length;
    say = `I stopped <b>${esc(file.name)}</b>: <b>${blocking}</b> blocking issue${blocking === 1 ? "" : "s"}` +
      `${file.issues.length > blocking ? ` (+${file.issues.length - blocking} minor)` : ""}. Want Granite to fix them?`;
  } else if (file?.verdict === "clean") {
    mood = "celebrate";
    say = `<b>${esc(file.name)}</b> is clean. Ship it!`;
  } else if (setup.db2State === "unknown" || setup.db2State === "working" || setup.graniteState === "unknown") {
    mood = "thinking";
    say = "Checking your setup: IBM Db2, Granite and your AI agent...";
  } else if (setup.db2State === "missing") {
    mood = "alert";
    say = "Connect <b>IBM Db2</b>: it is my brain. Team policies, project memory, SQL validation and the audit trail all live in Db2.";
  } else if (setup.graniteState === "missing") {
    say = "Db2 is connected. Add <b>IBM Granite</b> for verified AI fixes and answers about your team standards.";
  } else {
    say = "All set. I check files when you save, and your AI agent asks me before it writes code.";
  }
  return {
    mascot: p.mascot, mood, say, health: health(), file, stats: { ...stats }, agentName: setup.isBob() ? "IBM Bob" : "VS Code",
    agents: setup.db2State === "ok" ? agentRows || [] : null, canAskBob: canAskBob || setup.isBob(),
    toggles: [
      { key: "checkOnSave", label: "Check when I save", value: p.checkOnSave },
      { key: "checkOnType", label: "Check as I type", value: p.checkOnType },
      { key: "citePolicies", label: "Cite team policies (Db2)", value: p.citePolicies },
      { key: "bandit", label: "Deep Python scan (Bandit)", value: p.bandit },
      { key: "fix.autoApplyVerified", label: "Apply verified fixes without asking", value: p.fixAutoApplyVerified },
      { key: "mascot", label: "Show Shippy", value: p.mascot },
    ],
  };
}

function refreshUi(): void {
  home?.refresh();
  findings?.refresh();
}

function say(mood: Mood, text: string, forMs = 0): void {
  lastEvent = { mood, say: text };
  refreshUi();
  if (forMs) {
    setTimeout(() => {
      if (lastEvent?.say === text) {
        lastEvent = undefined;
        refreshUi();
      }
    }, forMs);
  }
}

// --------------------------------------------------------------- checking
function shouldCheck(doc: vscode.TextDocument, p: Prefs): boolean {
  if (doc.uri.scheme !== "file" || !p.languages.includes(doc.languageId)) {
    return false;
  }
  const rel = relPath(doc);
  return !p.exclude.some((g) => matchesGlob(rel, g));
}

async function checkDocument(doc: vscode.TextDocument, quiet = false): Promise<CheckResult | undefined> {
  const p = prefs();
  if (!shouldCheck(doc, p)) {
    if (!quiet) {
      void vscode.window.showInformationMessage(`ShipSafe skips this file (language "${doc.languageId}" or an exclude pattern in your settings).`);
    }
    return undefined;
  }
  try {
    const raw = await call<CheckResult>("shipsafe_check_code", { code: doc.getText(), filename: relPath(doc) },
      `checking ${path.basename(doc.fileName)}`);
    rawResults.set(doc.uri.toString(), raw);
    return publish(doc, raw, p);
  } catch (err) {
    status.text = "$(shield) ShipSafe: offline";
    if (!quiet) {
      reportError("check the file", err);
    } else {
      output.appendLine(`[check] ${err instanceof Error ? err.message : String(err)}`);
    }
    return undefined;
  }
}

function publish(doc: vscode.TextDocument, raw: CheckResult, p: Prefs, counted = true): CheckResult {
  const result = applyPrefs(raw, p);
  const key = doc.uri.toString();
  const before = lastResults.get(key)?.verdict;
  lastResults.set(key, result);
  diagnostics.set(doc.uri, result.issues.map((issue) => {
    const line = Math.max(0, Math.min(issue.line - 1, doc.lineCount - 1));
    const d = new vscode.Diagnostic(doc.lineAt(line).range, diagnosticMessage(issue), diagnosticLevel(issue.severity));
    d.source = "ShipSafe";
    d.code = issue.rule_id;
    return d;
  }));
  const blocking = result.issues.filter((i) => rank(i.severity) >= rank(p.blockAt)).length;
  status.text = statusText(result.verdict, result.verdict === "block" ? blocking : result.issues.length);
  status.tooltip = `${result.summary}\nClick to open ShipSafe.`;
  if (counted) {
    stats.checks++;
    if (result.verdict === "block") {
      stats.blocked++;
    }
    lastEvent = undefined;
    if (result.verdict === "block" && (p.notifyOn === "block" || p.notifyOn === "warn") && before !== "block") {
      void vscode.window.showWarningMessage(`ShipSafe blocked ${path.basename(doc.fileName)}: ${severityCounts(result.issues)}.`,
        "Fix with Granite", "Show").then((x) => {
        if (x === "Fix with Granite") {
          void fixDocument(doc);
        } else if (x) {
          void vscode.commands.executeCommand("workbench.actions.view.problems");
        }
      });
    } else if (result.verdict === "warn" && p.notifyOn === "warn" && before !== "warn") {
      void vscode.window.showInformationMessage(`ShipSafe: ${result.summary}`);
    }
  }
  refreshUi();
  if (counted) {
    setTimeout(() => void refreshAgents(), 1500);
  }
  return result;
}

/** Re-apply settings (severity floor, ignored rules) to the results we already have, without re-running checks. */
async function reapplyPrefs(): Promise<void> {
  const p = prefs();
  for (const [key, raw] of rawResults) {
    const doc = vscode.workspace.textDocuments.find((d) => d.uri.toString() === key);
    if (doc) {
      publish(doc, raw, p, false);
    }
  }
  status[p.statusBar ? "show" : "hide"]();
}

interface FixResult {
  verified: boolean;
  fixed_code: string | null;
  diff: string;
  rounds: number;
  message: string;
  plan: string;
  model: string;
}

async function fixDocument(doc: vscode.TextDocument): Promise<void> {
  busy = { mood: "thinking", say: `Granite is fixing <b>${esc(path.basename(doc.fileName))}</b>; every fix is re-checked before I show it.` };
  refreshUi();
  try {
    const result = await call<FixResult>("shipsafe_fix_code", { code: doc.getText(), filename: relPath(doc) },
      `fixing ${path.basename(doc.fileName)} with Granite`, 600_000);
    busy = undefined;
    if (!result.rounds) {
      say("celebrate", esc(result.message), 8000);
      return;
    }
    if (!result.fixed_code) {
      say("alert", esc(result.message), 10000);
      void vscode.window.showWarningMessage(`ShipSafe: ${result.message}`);
      return;
    }
    const apply = async () => {
      const edit = new vscode.WorkspaceEdit();
      edit.replace(doc.uri, new vscode.Range(0, 0, doc.lineCount, 0), result.fixed_code!);
      await vscode.workspace.applyEdit(edit);
      stats.fixed++;
      say("celebrate", `Fixed and verified in ${result.rounds} round(s) by ${esc(result.model)}. Undo with Ctrl+Z if you disagree.`, 10000);
      await checkDocument(doc, true);
    };
    if (result.verified && prefs().fixAutoApplyVerified) {
      await apply();
      return;
    }
    const proposed = await vscode.workspace.openTextDocument({ language: doc.languageId, content: result.fixed_code });
    await vscode.commands.executeCommand("vscode.diff", doc.uri, proposed.uri,
      `${path.basename(doc.fileName)} ↔ ShipSafe fix (${result.verified ? "verified" : "NOT verified"})`);
    say(result.verified ? "celebrate" : "alert", result.verified
      ? "Granite's fix passed every check. Review the diff and apply it." : "This fix did NOT pass every check. Review it carefully.");
    const choice = await vscode.window.showInformationMessage(
      `${result.message} (${result.rounds} round(s), ${result.model})`,
      { modal: !result.verified }, ...(result.verified ? ["Apply fix"] : ["Apply anyway"]), "Discard");
    if (choice === "Apply fix" || choice === "Apply anyway") {
      await apply();
    }
  } catch (err) {
    busy = undefined;
    refreshUi();
    reportError("fix the file", err);
  }
}

class FixActionProvider implements vscode.CodeActionProvider {
  static readonly kinds = [vscode.CodeActionKind.QuickFix];

  provideCodeActions(doc: vscode.TextDocument, _range: vscode.Range, ctx: vscode.CodeActionContext): vscode.CodeAction[] {
    const ours = ctx.diagnostics.filter((d) => d.source === "ShipSafe");
    if (!ours.length) {
      return [];
    }
    const fix = new vscode.CodeAction("ShipSafe: fix with Granite (verified)", vscode.CodeActionKind.QuickFix);
    fix.command = { command: "shipsafe.fixFile", title: "Fix", arguments: [doc.uri] };
    fix.diagnostics = ours;
    fix.isPreferred = true;
    const rules = [...new Set(ours.map((d) => String(d.code)))];
    const ignores = rules.map((rule) => {
      const a = new vscode.CodeAction(`ShipSafe: stop reporting ${rule} (my settings)`, vscode.CodeActionKind.QuickFix);
      a.command = { command: "shipsafe.ignoreRule", title: "Ignore", arguments: [rule] };
      return a;
    });
    return [fix, ...ignores];
  }
}

// --------------------------------------------------------------- engine lifecycle
async function afterEngineReady(): Promise<void> {
  if (!setup.engine) {
    return;
  }
  restartServer();
  mcpChanged.fire();
  await setup.refreshGranite();
  // The engine can take a while to start on a busy laptop: an unanswered status is "starting", not "no Db2".
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const st = await call<{ db2: { connected?: boolean; version?: string; host?: string; port?: number; database?: string } }>(
        "shipsafe_status", {}, "checking Db2", 90_000);
      setup.setDb2(st.db2);
      break;
    } catch (err) {
      output.appendLine(`[status] attempt ${attempt}: ${err instanceof Error ? err.message : err}`);
      if (attempt === 3) {
        setup.setDb2(undefined);
      } else {
        setup.db2State = "working";
        setup.db2Detail = "ShipSafe engine is starting...";
        refreshUi();
        restartServer();
        await new Promise((r) => setTimeout(r, 5000));
      }
    }
  }
  if (setup.db2State === "missing" && !extContext.globalState.get("shipsafe.db2Asked")) {
    await extContext.globalState.update("shipsafe.db2Asked", true);
    const pick = await vscode.window.showWarningMessage(
      "ShipSafe runs on IBM Db2: team policies (Db2 vectors), project memory, SQL validation on the real database and the audit trail. Connect Db2 now?",
      "Connect IBM Db2", "Later");
    if (pick) {
      void vscode.commands.executeCommand("shipsafe.setupDb2");
    }
  }
  await maybeConnectAgent();
  void refreshAgents();
  const doc = vscode.window.activeTextEditor?.document;
  if (doc && shouldCheck(doc, prefs())) {
    void checkDocument(doc, true);
  }
}

let agentsBusy = false;
async function refreshAgents(): Promise<void> {
  if (!setup.engine || setup.db2State !== "ok" || agentsBusy) {
    return;
  }
  agentsBusy = true;
  try {
    const r = await getClient().callTool("shipsafe_session_report", { since_minutes: 1440 }, 60_000) as {
      by_client: { CLIENT: string; CHECKS: number; BLOCKED: number; VERIFIED_FIXES: number }[] };
    const merged = new Map<string, { name: string; checks: number; blocked: number; fixed: number }>();
    for (const row of r.by_client || []) {
      const name = agentLabel(row.CLIENT, setup.isBob());
      const m = merged.get(name) || { name, checks: 0, blocked: 0, fixed: 0 };
      m.checks += row.CHECKS || 0;
      m.blocked += row.BLOCKED || 0;
      m.fixed += row.VERIFIED_FIXES || 0;
      merged.set(name, m);
    }
    agentRows = [...merged.values()].sort((a, b) => b.checks - a.checks);
    home?.refresh();
  } catch (err) {
    output.appendLine(`[agents] ${err instanceof Error ? err.message : err}`);
  } finally {
    agentsBusy = false;
  }
}

/** Bob's agent registers its commands after it activates, so look (and wake it) at the moment of use. */
async function bobAvailable(): Promise<boolean> {
  if (!canAskBob) {
    const bob = vscode.extensions.all.find((e) => /(^|\.)bob-code$/i.test(e.id));
    if (bob && !bob.isActive) {
      try {
        await bob.activate();
      } catch {
        // Bob reports its own activation errors
      }
    }
    canAskBob = (await vscode.commands.getCommands(true)).includes(BOB_SEND);
  }
  return canAskBob;
}

/** Hand a task to IBM Bob's agent together with the ShipSafe workflow (Shippy -> Bob). */
async function askBob(task?: string, confirm = false): Promise<void> {
  if (!(await bobAvailable())) {
    void vscode.window.showInformationMessage("Ask Bob works inside IBM Bob. In other editors, ask your AI agent directly; ShipSafe is already connected.");
    return;
  }
  const ws = workspaceFolder();
  if (!ws) {
    void vscode.window.showWarningMessage("Open a project folder first.");
    return;
  }
  task = task?.trim() || (await vscode.window.showInputBox({ title: "Ask Bob, guarded by ShipSafe", ignoreFocusOut: true,
    prompt: "What should Bob build? Bob checks every file with ShipSafe before writing it.",
    placeHolder: "Add a function that returns an order and its total from the ORDERS table in Db2" }))?.trim();
  if (!task) {
    return;
  }
  if (confirm) {
    const ok = await vscode.window.showWarningMessage(`A link asks Bob to do this task:\n\n"${task.slice(0, 300)}"`, { modal: true }, "Send to Bob");
    if (ok !== "Send to Bob") {
      return;
    }
  }
  if (!setup.agentConnected(ws)) {
    if (!setup.engine) {
      void vscode.window.showWarningMessage("Install the ShipSafe engine first.");
      return;
    }
    connectBob(ws, serverCommand());
    refreshUi();
  }
  say("thinking", "I handed the task to <b>Bob</b>. Every file Bob wants to write comes to me first.", 20000);
  await vscode.commands.executeCommand(BOB_SEND, "ShipSafe", bobTaskPrompt(task));
}

async function maybeConnectAgent(): Promise<void> {
  const ws = workspaceFolder();
  const mode = vscode.workspace.getConfiguration("shipsafe").get<string>("autoConnectAgent", "ask");
  if (!ws || !setup.isBob() || setup.agentConnected(ws) || mode === "never" || !setup.engine) {
    return;
  }
  const key = "shipsafe.agentAsked";
  if (mode === "always") {
    void vscode.commands.executeCommand("shipsafe.connectBob");
    return;
  }
  if (extContext.workspaceState.get(key)) {
    return;
  }
  await extContext.workspaceState.update(key, true);
  const pick = await vscode.window.showInformationMessage(
    "Let IBM Bob use ShipSafe in this folder? Bob will check code before writing it, validate SQL on Db2 and recall team decisions.",
    "Connect Bob", "Not now");
  if (pick === "Connect Bob") {
    void vscode.commands.executeCommand("shipsafe.connectBob");
  }
}

async function firstRun(context: vscode.ExtensionContext): Promise<void> {
  const found = await setup.resolveEngine();
  if (!context.globalState.get("shipsafe.welcomed")) {
    await context.globalState.update("shipsafe.welcomed", true);
    void vscode.commands.executeCommand("shipsafe.home.focus");
  }
  if (found) {
    if (setup.needsUpgrade()) {
      output.appendLine(`Upgrading the private ShipSafe engine ${found.version} -> ${ENGINE_VERSION}`);
      await setup.installEngine();
    }
    await afterEngineReady();
    return;
  }
  await setup.refreshGranite();
  const mode = vscode.workspace.getConfiguration("shipsafe").get<string>("autoSetup", "ask");
  if (mode === "auto") {
    if (await setup.installEngine()) {
      await afterEngineReady();
    }
  } else if (mode === "ask" && !context.globalState.get("shipsafe.neverAskEngine")) {
    const pick = await vscode.window.showInformationMessage(
      "Hi, I'm Shippy from ShipSafe! I need to install my engine once (Python package in a private folder; a few minutes the first time). Do it now?",
      "Install now", "Later", "Don't ask again");
    if (pick === "Install now") {
      if (await setup.installEngine()) {
        await afterEngineReady();
      }
    } else if (pick === "Don't ask again") {
      await context.globalState.update("shipsafe.neverAskEngine", true);
    }
  }
}

const DEMO = `"""ShipSafe demo: this file has the mistakes AI assistants often make. Save it and watch the Problems panel."""
import subprocess

import ibm_db

API_KEY = "sk_live_9f8e7d6c5b4a3210"


def get_order(conn, order_id):
    sql = f"SELECT ID, TOTAL FROM ORDERS WHERE ID = '{order_id}'"
    return ibm_db.fetch_assoc(ibm_db.exec_immediate(conn, sql))


def deploy(cmd):
    return subprocess.run(cmd, shell=True)
`;

// ------------------------------------------------------------- activation
export function activate(context: vscode.ExtensionContext): void {
  extContext = context;
  output = vscode.window.createOutputChannel("ShipSafe");
  diagnostics = vscode.languages.createDiagnosticCollection("shipsafe");
  status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  status.text = "$(shield) ShipSafe";
  status.command = "shipsafe.home.focus";
  if (prefs().statusBar) {
    status.show();
  }
  setup = new Setup(context, (line) => output.appendLine(line), () => refreshUi());
  setup.output = output;
  home = new HomeViewProvider(homeState, async (key, value) => {
    await vscode.workspace.getConfiguration("shipsafe").update(key, value, vscode.ConfigurationTarget.Global);
  });
  findings = new FindingsProvider(lastResults);
  context.subscriptions.push(output, diagnostics, status,
    vscode.window.registerWebviewViewProvider(HomeViewProvider.id, home, { webviewOptions: { retainContextWhenHidden: true } }),
    vscode.window.registerTreeDataProvider(FindingsProvider.id, findings));

  const editorDoc = (uri?: vscode.Uri) =>
    uri instanceof vscode.Uri ? vscode.workspace.openTextDocument(uri) : Promise.resolve(vscode.window.activeTextEditor?.document);

  const register = (id: string, fn: (...args: any[]) => unknown) =>
    context.subscriptions.push(vscode.commands.registerCommand(id, fn));

  register("shipsafe.checkFile", async (uri?: vscode.Uri) => {
    const doc = await editorDoc(uri);
    if (!doc) {
      void vscode.window.showInformationMessage("Open a file first.");
      return;
    }
    const r = await checkDocument(doc);
    if (r) {
      void vscode.window.showInformationMessage(`ShipSafe: ${r.summary}`);
    }
  });
  register("shipsafe.fixFile", async (arg?: vscode.Uri | { uri: vscode.Uri }) => {
    const uri = arg instanceof vscode.Uri ? arg : (arg as { uri?: vscode.Uri })?.uri;
    const doc = await editorDoc(uri);
    if (doc) {
      await fixDocument(doc);
    }
  });
  register("shipsafe.checkWorkspace", async () => {
    const p = prefs();
    const exts = "py,js,ts,jsx,tsx,mjs,cjs";
    const files = await vscode.workspace.findFiles(`**/*.{${exts}}`, `{${p.exclude.join(",")}}`, 200);
    if (!files.length) {
      void vscode.window.showInformationMessage("No Python, JavaScript or TypeScript files found in this workspace.");
      return;
    }
    busy = { mood: "thinking", say: `Checking ${files.length} file(s)...` };
    refreshUi();
    let blocked = 0;
    await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, title: "ShipSafe: checking workspace", cancellable: true },
      async (progress, token) => {
        for (const [i, f] of files.entries()) {
          if (token.isCancellationRequested) {
            break;
          }
          progress.report({ message: `${i + 1}/${files.length} ${path.basename(f.fsPath)}`, increment: 100 / files.length });
          const doc = await vscode.workspace.openTextDocument(f);
          const r = await checkDocument(doc, true);
          if (r?.verdict === "block") {
            blocked++;
          }
        }
      });
    busy = undefined;
    say(blocked ? "alert" : "celebrate", blocked ? `${blocked} of ${files.length} file(s) have blocking issues. See <b>Findings</b> below.`
      : `Checked ${files.length} file(s): nothing blocking.`, 15000);
    void vscode.commands.executeCommand(`${FindingsProvider.id}.focus`);
  });
  register("shipsafe.checkSql", async () => {
    const editor = vscode.window.activeTextEditor;
    let sql = editor?.document.getText(editor.selection).trim();
    if (!sql) {
      sql = (await vscode.window.showInputBox({ prompt: "SQL statement to validate on IBM Db2 (it is prepared, never run)",
        placeHolder: "SELECT ID, TOTAL FROM ORDERS WHERE CLIENT = ?" }))?.trim();
    }
    if (!sql) {
      return;
    }
    try {
      const r = await call<{ verdict: string }>("shipsafe_check_sql", { sql }, "validating SQL on Db2");
      await showMarkdown(`SQL check: ${r.verdict}`, r);
    } catch (err) {
      reportError("check the SQL", err);
    }
  });
  register("shipsafe.askStandards", async () => {
    const question = await vscode.window.showInputBox({ prompt: "What do you want to know about the team standards?",
      placeHolder: "How must we pass user input to Db2 queries?" });
    if (!question) {
      return;
    }
    try {
      const r = await call<{ answer: string; citations: { doc_id: string; title: string; section: string }[] }>(
        "shipsafe_ask_standards", { question }, "asking Granite", 300_000);
      const cites = r.citations.map((c) => `- **${c.doc_id}** ${c.title} / ${c.section}`).join("\n");
      await showMarkdown(question, `${r.answer}\n\n## Sources (IBM Db2 vector search)\n${cites}`);
    } catch (err) {
      reportError("answer the question", err);
    }
  });
  register("shipsafe.remember", async () => {
    const editor = vscode.window.activeTextEditor;
    const selected = editor?.document.getText(editor.selection).trim();
    const text = await vscode.window.showInputBox({ prompt: "Decision or convention to remember for this project",
      value: selected || "" });
    if (!text) {
      return;
    }
    const kind = await vscode.window.showQuickPick(["decision", "convention", "gotcha", "todo"], { placeHolder: "Kind" });
    try {
      await call("shipsafe_remember", { text, kind: kind || "decision" }, "saving to Db2");
      say("celebrate", "Saved to project memory in IBM Db2. Your AI agent will recall it on the next task.", 8000);
    } catch (err) {
      reportError("save the memory", err);
    }
  });
  register("shipsafe.recall", async () => {
    const query = await vscode.window.showInputBox({ prompt: "What are you working on?" });
    if (!query) {
      return;
    }
    try {
      const hits = await call<{ kind: string; text: string; score: number }[]>("shipsafe_recall", { query }, "searching memory");
      const body = hits.length ? hits.map((h) => `- **${h.kind}** ${h.text} _(score ${h.score})_`).join("\n")
        : "Nothing remembered for this project yet.";
      await showMarkdown(`Project memory: ${query}`, body);
    } catch (err) {
      reportError("search the memory", err);
    }
  });
  register("shipsafe.readiness", async () => {
    const profile = vscode.workspace.getConfiguration("shipsafe").get<string>("readinessProfile", "pre-pr");
    try {
      const r = await call("shipsafe_readiness_check", { workspace: ".", profile }, "running readiness check", 600_000);
      await showMarkdown(`Readiness check (${profile})`, r);
    } catch (err) {
      reportError("run the readiness check", err);
    }
  });
  register("shipsafe.sessionReport", async () => {
    try {
      await showMarkdown("What ShipSafe caught (last 24 h)", await call("shipsafe_session_report", { since_minutes: 1440 }, "reading Db2"));
    } catch (err) {
      reportError("load the report", err);
    }
  });
  register("shipsafe.status", async () => {
    try {
      await showMarkdown("ShipSafe status", await call("shipsafe_status", {}, "checking Db2 and Granite"));
    } catch (err) {
      reportError("read the status", err);
    }
  });
  register("shipsafe.restart", async () => {
    restartServer();
    await setup.resolveEngine();
    await afterEngineReady();
    void vscode.window.showInformationMessage("ShipSafe server restarted.");
  });
  register("shipsafe.installEngine", async () => {
    if (await setup.installEngine()) {
      await afterEngineReady();
    }
  });
  register("shipsafe.setupGranite", async () => {
    await setup.setupGranite();
    restartServer();
  });
  register("shipsafe.setupDb2", async () => {
    if (!(await setup.setupDb2())) {
      return;
    }
    restartServer();
    setup.db2State = "working";
    setup.db2Detail = "Connecting...";
    refreshUi();
    for (let i = 0; i < 40; i++) {
      try {
        const st = await call<{ db2: { connected?: boolean } }>("shipsafe_status", {}, "connecting to Db2", 90_000);
        if (st.db2.connected) {
          setup.setDb2(st.db2);
          say("celebrate", "Connected to IBM Db2. SQL checks, policy citations and team memory are on.", 10000);
          return;
        }
      } catch (err) {
        output.appendLine(`[db2] ${err instanceof Error ? err.message : err}`);
      }
      restartServer();
      await new Promise((r) => setTimeout(r, 15_000));
    }
    setup.setDb2(undefined);
    void vscode.window.showWarningMessage("ShipSafe could not reach Db2 yet. Check the connection and try again.", "Show log")
      .then((x) => x && output.show());
  });
  register("shipsafe.setup", async () => {
    if (!setup.engine && !(await setup.installEngine())) {
      return;
    }
    await afterEngineReady();
    if (setup.db2State !== "ok") {
      await vscode.commands.executeCommand("shipsafe.setupDb2");
    }
    if (setup.graniteState !== "ok") {
      await vscode.commands.executeCommand("shipsafe.setupGranite");
    }
  });
  register("shipsafe.openSettings", () => vscode.commands.executeCommand("workbench.action.openSettings", `@ext:${context.extension.id}`));
  register("shipsafe.walkthrough", () => vscode.commands.executeCommand("workbench.action.openWalkthrough",
    `${context.extension.id}#start`, false));
  register("shipsafe.ignoreRule", async (rule?: string) => {
    if (!rule) {
      return;
    }
    const cfg = vscode.workspace.getConfiguration("shipsafe");
    const list = new Set(cfg.get<string[]>("ignoredRules") || []);
    list.add(rule);
    await cfg.update("ignoredRules", [...list], vscode.ConfigurationTarget.Workspace);
    void vscode.window.showInformationMessage(`ShipSafe will not report ${rule} in this workspace. Undo it in Settings > ShipSafe > Ignored Rules.`);
  });
  register("shipsafe.revealLine", (line: number) => {
    const editor = vscode.window.activeTextEditor;
    if (editor && Number.isFinite(line)) {
      const pos = new vscode.Position(Math.max(0, line - 1), 0);
      editor.selection = new vscode.Selection(pos, pos);
      editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
      void vscode.window.showTextDocument(editor.document, editor.viewColumn);
    }
  });
  register("shipsafe.tryDemo", async () => {
    const dir = path.join(context.globalStorageUri.fsPath, "demo");
    fs.mkdirSync(dir, { recursive: true });
    const file = path.join(dir, "orders_repository.py");
    fs.writeFileSync(file, DEMO, "utf8");
    const doc = await vscode.workspace.openTextDocument(file);
    await vscode.window.showTextDocument(doc);
    if (!setup.engine) {
      void vscode.commands.executeCommand("shipsafe.installEngine");
      return;
    }
    await checkDocument(doc);
  });
  const connect = (target: "bob" | "claude") => () => {
    const ws = workspaceFolder();
    if (!ws) {
      void vscode.window.showWarningMessage("Open a folder first.");
      return;
    }
    if (!setup.engine) {
      void vscode.window.showWarningMessage("Install the ShipSafe engine first.", "Install").then((x) => x && vscode.commands.executeCommand("shipsafe.installEngine"));
      return;
    }
    const files = target === "bob" ? connectBob(ws, serverCommand()) : connectClaude(ws, serverCommand());
    refreshUi();
    void vscode.window.showInformationMessage(
      `ShipSafe connected to ${target === "bob" ? "IBM Bob" : "Claude Code"}: ${files.map((f) => path.relative(ws, f)).join(", ")}. ` +
      "Reload the window so the agent picks it up.", "Reload").then((x) => x && vscode.commands.executeCommand("workbench.action.reloadWindow"));
  };
  register("shipsafe.connectBob", connect("bob"));
  register("shipsafe.askBob", (task?: string) => askBob(typeof task === "string" ? task : undefined));
  canAskBob = false;
  const isBobApp = setup.isBob();
  void vscode.commands.executeCommand("setContext", "shipsafe.canAskBob", isBobApp);
  setTimeout(() => void bobAvailable().then(refreshUi), 8000);
  context.subscriptions.push(vscode.window.registerUriHandler({
    handleUri(uri: vscode.Uri) {
      // <scheme>://<publisher>.shipsafe/ask?task=...  (always confirmed: a web page must not drive the agent silently)
      if (uri.path === "/ask") {
        const task = new URLSearchParams(uri.query).get("task") || undefined;
        void askBob(task, true);
      }
    },
  }));
  const timer = setInterval(() => {
    if (home && setup.db2State === "ok") {
      void refreshAgents();
    }
  }, 60_000);
  context.subscriptions.push({ dispose: () => clearInterval(timer) });

  // Safety net: files written straight to disk (e.g. by an AI agent) are checked too, not only editor saves.
  const recent = new Map<string, number>();
  const onDisk = async (uri: vscode.Uri) => {
    const p = prefs();
    if (!p.checkOnSave || !setup.engine || uri.scheme !== "file") {
      return;
    }
    const key = uri.toString();
    const now = Date.now();
    if (now - (recent.get(key) || 0) < 2000) {
      return;
    }
    recent.set(key, now);
    const doc = await vscode.workspace.openTextDocument(uri);
    if (!doc.isDirty && shouldCheck(doc, p)) {
      await checkDocument(doc, true);
    }
  };
  const watcher = vscode.workspace.createFileSystemWatcher("**/*.{py,js,ts,jsx,tsx,mjs,cjs}");
  context.subscriptions.push(watcher, watcher.onDidChange(onDisk), watcher.onDidCreate(onDisk),
    vscode.workspace.onDidSaveTextDocument((doc) => recent.set(doc.uri.toString(), Date.now())));
  register("shipsafe.connectClaude", connect("claude"));

  const typing = new Map<string, NodeJS.Timeout>();
  context.subscriptions.push(
    vscode.languages.registerCodeActionsProvider(
      ["python", "javascript", "typescript", "javascriptreact", "typescriptreact"].map((language) => ({ language, scheme: "file" })),
      new FixActionProvider(), { providedCodeActionKinds: FixActionProvider.kinds }),
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (prefs().checkOnSave && setup.engine) {
        void checkDocument(doc, true);
      }
    }),
    vscode.workspace.onDidChangeTextDocument((e) => {
      const p = prefs();
      if (!p.checkOnType || !setup.engine || !e.contentChanges.length || !shouldCheck(e.document, p)) {
        return;
      }
      const key = e.document.uri.toString();
      clearTimeout(typing.get(key));
      typing.set(key, setTimeout(() => {
        typing.delete(key);
        void checkDocument(e.document, true);
      }, p.checkOnTypeDelayMs));
    }),
    vscode.window.onDidChangeActiveTextEditor(() => refreshUi()),
    vscode.workspace.onDidCloseTextDocument((doc) => {
      diagnostics.delete(doc.uri);
      lastResults.delete(doc.uri.toString());
      rawResults.delete(doc.uri.toString());
      refreshUi();
    }),
    vscode.workspace.onDidChangeConfiguration(async (e) => {
      if (!e.affectsConfiguration("shipsafe")) {
        return;
      }
      const serverSide = ["pythonPath", "envFile", "bandit", "citePolicies", "fix.maxRounds", "granite"]
        .some((k) => e.affectsConfiguration(`shipsafe.${k}`));
      if (serverSide) {
        restartServer();
        if (e.affectsConfiguration("shipsafe.pythonPath")) {
          await setup.resolveEngine();
        }
        if (e.affectsConfiguration("shipsafe.granite")) {
          void setup.refreshGranite();
        }
      }
      await reapplyPrefs();
      refreshUi();
    }),
    { dispose: () => client?.dispose() },
  );

  // Native MCP registration (VS Code 1.101+): agent mode sees ShipSafe without any config file.
  const lm = (vscode as any).lm;
  if (lm?.registerMcpServerDefinitionProvider && (vscode as any).McpStdioServerDefinition) {
    const Def = (vscode as any).McpStdioServerDefinition;
    context.subscriptions.push(mcpChanged, lm.registerMcpServerDefinitionProvider("shipsafe.mcp", {
      onDidChangeMcpServerDefinitions: mcpChanged.event,
      provideMcpServerDefinitions: () => {
        if (!setup.engine) {
          return [];
        }
        const s = serverCommand();
        const env: Record<string, string> = {};
        for (const [k, v] of Object.entries(s.env || {})) {
          if (typeof v === "string") {
            env[k] = v;
          }
        }
        return [new Def("ShipSafe", s.command, s.args, env, ENGINE_VERSION)];
      },
    }));
  }

  output.appendLine(`ShipSafe ${ENGINE_VERSION} in ${vscode.env.appName}. Guide: ${SITE}`);
  register("shipsafe.trustFolder", () => vscode.commands.executeCommand("workbench.trust.manage"));
  if (vscode.workspace.isTrusted) {
    void firstRun(context);
  } else {
    // Restricted Mode: show Shippy and the one step needed; start for real once the folder is trusted.
    void vscode.commands.executeCommand("shipsafe.home.focus");
    context.subscriptions.push(vscode.workspace.onDidGrantWorkspaceTrust(() => void firstRun(context)));
  }
}

export function deactivate(): void {
  client?.dispose();
}
