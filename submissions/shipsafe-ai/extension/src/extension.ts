import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";
import { connectBob, connectClaude } from "./connect";
import { CheckResult, diagnosticLevel, diagnosticMessage, isMissingServer, isSupportedLanguage, markdownReport, statusText } from "./format";
import { McpClient, ServerCommand } from "./mcpClient";

let client: McpClient | undefined;
let output: vscode.OutputChannel;
let diagnostics: vscode.DiagnosticCollection;
let status: vscode.StatusBarItem;
const lastResults = new Map<string, CheckResult>();

function workspaceFolder(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

/** Resolve how to launch the ShipSafe MCP server from the settings. */
export function serverCommand(): ServerCommand {
  const cfg = vscode.workspace.getConfiguration("shipsafe");
  const python = (cfg.get<string>("pythonPath") || "").trim();
  const envFile = (cfg.get<string>("envFile") || "").trim();
  const env: NodeJS.ProcessEnv = {};
  const ws = workspaceFolder();
  if (ws) {
    env.SHIPSAFE_WORKSPACE = ws;
  }
  if (envFile) {
    env.SHIPSAFE_ENV_FILE = envFile.replace(/^~(?=$|[\\/])/, os.homedir());
  }
  if (python) {
    return { command: python, args: ["-m", "shipsafe.mcp_server"], cwd: ws, env };
  }
  return { command: process.platform === "win32" ? "shipsafe-mcp.exe" : "shipsafe-mcp", args: [], cwd: ws, env };
}

function getClient(): McpClient {
  if (!client) {
    client = new McpClient(serverCommand(), (line) => output.appendLine(line));
  }
  return client;
}

async function call<T>(tool: string, args: Record<string, unknown>, title: string, timeoutMs?: number): Promise<T> {
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

const INSTALL_URL = "https://shipsafe-bob.vercel.app/#start";
let missingServerShown = false;

function reportError(action: string, err: unknown): void {
  const message = err instanceof Error ? err.message : String(err);
  output.appendLine(`[${action}] ${message}`);
  if (isMissingServer(message)) {
    client?.dispose();
    client = undefined;
    if (missingServerShown) {
      return; // one prompt per session, not one per save
    }
    missingServerShown = true;
    void vscode.window.showWarningMessage(
      "ShipSafe needs its Python package (Python 3.11-3.13). Run: pip install " +
        "https://shipsafe-bob.vercel.app/downloads/shipsafe-3.0.0-py3-none-any.whl  then `shipsafe setup`. " +
        "If it is installed in a virtual environment, set shipsafe.pythonPath to that interpreter.",
      "Install guide", "Set Python path", "Show log",
    ).then((pick) => {
      if (pick === "Install guide") {
        void vscode.env.openExternal(vscode.Uri.parse(INSTALL_URL));
      } else if (pick === "Set Python path") {
        void vscode.commands.executeCommand("workbench.action.openSettings", "shipsafe.pythonPath");
      } else if (pick) {
        output.show();
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

// --------------------------------------------------------------- checking
async function checkDocument(doc: vscode.TextDocument, quiet = false): Promise<CheckResult | undefined> {
  if (doc.uri.scheme !== "file" || !isSupportedLanguage(doc.languageId)) {
    return undefined;
  }
  try {
    const result = await call<CheckResult>("shipsafe_check_code", { code: doc.getText(), filename: relPath(doc) },
      `checking ${path.basename(doc.fileName)}`);
    lastResults.set(doc.uri.toString(), result);
    diagnostics.set(doc.uri, result.issues.map((issue) => {
      const line = Math.max(0, Math.min(issue.line - 1, doc.lineCount - 1));
      const range = doc.lineAt(line).range;
      const d = new vscode.Diagnostic(range, diagnosticMessage(issue), diagnosticLevel(issue.severity));
      d.source = "ShipSafe";
      d.code = issue.rule_id;
      return d;
    }));
    status.text = statusText(result.verdict, result.issues.length);
    status.tooltip = result.summary;
    return result;
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
  try {
    const result = await call<FixResult>("shipsafe_fix_code", { code: doc.getText(), filename: relPath(doc) },
      `fixing ${path.basename(doc.fileName)} with Granite`, 600_000);
    if (!result.rounds) {
      void vscode.window.showInformationMessage(`ShipSafe: ${result.message}`);
      return;
    }
    if (!result.fixed_code) {
      void vscode.window.showWarningMessage(`ShipSafe: ${result.message}`);
      return;
    }
    const proposed = await vscode.workspace.openTextDocument({ language: doc.languageId, content: result.fixed_code });
    await vscode.commands.executeCommand("vscode.diff", doc.uri, proposed.uri,
      `${path.basename(doc.fileName)} ↔ ShipSafe fix (${result.verified ? "verified" : "NOT verified"})`);
    const choice = await vscode.window.showInformationMessage(
      `${result.message} (${result.rounds} round(s), ${result.model})`,
      { modal: !result.verified }, ...(result.verified ? ["Apply fix"] : ["Apply anyway"]), "Discard");
    if (choice === "Apply fix" || choice === "Apply anyway") {
      const edit = new vscode.WorkspaceEdit();
      edit.replace(doc.uri, new vscode.Range(0, 0, doc.lineCount, 0), result.fixed_code);
      await vscode.workspace.applyEdit(edit);
      await checkDocument(doc, true);
    }
  } catch (err) {
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
    const action = new vscode.CodeAction("ShipSafe: fix with Granite (verified)", vscode.CodeActionKind.QuickFix);
    action.command = { command: "shipsafe.fixFile", title: "Fix", arguments: [doc.uri] };
    action.diagnostics = ours;
    action.isPreferred = true;
    return [action];
  }
}

// ------------------------------------------------------------- activation
export function activate(context: vscode.ExtensionContext): void {
  output = vscode.window.createOutputChannel("ShipSafe");
  diagnostics = vscode.languages.createDiagnosticCollection("shipsafe");
  status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 50);
  status.text = "$(shield) ShipSafe";
  status.command = "shipsafe.sessionReport";
  status.show();
  context.subscriptions.push(output, diagnostics, status);

  const editorDoc = (uri?: vscode.Uri) =>
    uri ? vscode.workspace.openTextDocument(uri) : Promise.resolve(vscode.window.activeTextEditor?.document);

  const register = (id: string, fn: (...args: any[]) => unknown) =>
    context.subscriptions.push(vscode.commands.registerCommand(id, fn));

  register("shipsafe.checkFile", async (uri?: vscode.Uri) => {
    const doc = await editorDoc(uri);
    if (doc) {
      const r = await checkDocument(doc);
      if (r) {
        void vscode.window.showInformationMessage(`ShipSafe: ${r.summary}`);
      }
    }
  });
  register("shipsafe.fixFile", async (uri?: vscode.Uri) => {
    const doc = await editorDoc(uri);
    if (doc) {
      await fixDocument(doc);
    }
  });
  register("shipsafe.checkSql", async () => {
    const editor = vscode.window.activeTextEditor;
    const sql = editor?.document.getText(editor.selection).trim();
    if (!sql) {
      void vscode.window.showWarningMessage("Select a SQL statement first.");
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
      void vscode.window.showInformationMessage("ShipSafe: saved to project memory in IBM Db2.");
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
    try {
      const r = await call("shipsafe_readiness_check", { workspace: ".", profile: "pre-pr" }, "running readiness check", 600_000);
      await showMarkdown("Readiness check", r);
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
  register("shipsafe.restart", () => {
    client?.dispose();
    client = undefined;
    void vscode.window.showInformationMessage("ShipSafe server restarted.");
  });
  const connect = (target: "bob" | "claude") => () => {
    const ws = workspaceFolder();
    if (!ws) {
      void vscode.window.showWarningMessage("Open a folder first.");
      return;
    }
    const server = serverCommand();
    const files = target === "bob" ? connectBob(ws, server) : connectClaude(ws, server);
    void vscode.window.showInformationMessage(
      `ShipSafe connected to ${target === "bob" ? "IBM Bob" : "Claude Code"}: ${files.map((f) => path.relative(ws, f)).join(", ")}`);
  };
  register("shipsafe.connectBob", connect("bob"));
  register("shipsafe.connectClaude", connect("claude"));

  context.subscriptions.push(
    vscode.languages.registerCodeActionsProvider(
      ["python", "javascript", "typescript", "javascriptreact", "typescriptreact"].map((language) => ({ language, scheme: "file" })),
      new FixActionProvider(), { providedCodeActionKinds: FixActionProvider.kinds }),
    vscode.workspace.onDidSaveTextDocument((doc) => {
      if (vscode.workspace.getConfiguration("shipsafe").get<boolean>("checkOnSave", true)) {
        void checkDocument(doc, true);
      }
    }),
    vscode.workspace.onDidCloseTextDocument((doc) => {
      diagnostics.delete(doc.uri);
      lastResults.delete(doc.uri.toString());
    }),
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration("shipsafe")) {
        client?.dispose();
        client = undefined;
      }
    }),
    { dispose: () => client?.dispose() },
  );

  // Native MCP registration (VS Code 1.101+): agent mode sees ShipSafe without any config file.
  const lm = (vscode as any).lm;
  if (lm?.registerMcpServerDefinitionProvider && (vscode as any).McpStdioServerDefinition) {
    const Def = (vscode as any).McpStdioServerDefinition;
    context.subscriptions.push(lm.registerMcpServerDefinitionProvider("shipsafe.mcp", {
      provideMcpServerDefinitions: () => {
        const s = serverCommand();
        const env: Record<string, string> = {};
        for (const [k, v] of Object.entries(s.env || {})) {
          if (typeof v === "string") {
            env[k] = v;
          }
        }
        return [new Def("ShipSafe", s.command, s.args, env, "3.0.0")];
      },
    }));
  }

  const homeEnv = path.join(os.homedir(), ".shipsafe", ".env");
  if (!fs.existsSync(homeEnv) && !vscode.workspace.getConfiguration("shipsafe").get<string>("envFile")) {
    output.appendLine(`No ${homeEnv} found. Run \`shipsafe setup\` once to store the Db2 and Ollama connection.`);
  }
}

export function deactivate(): void {
  client?.dispose();
}
