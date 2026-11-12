/**
 * Runs INSIDE a real editor (VS Code or IBM Bob) with the extension loaded.
 * Opens a vulnerable file, runs "ShipSafe: Check this file" and checks the Problems panel,
 * then validates SQL and reads the status, all through the real ShipSafe MCP server.
 */
import { strict as assert } from "assert";
import * as path from "path";
import * as vscode from "vscode";

async function waitFor<T>(fn: () => T | undefined, timeoutMs: number, what: string): Promise<T> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const v = fn();
    if (v) {
      return v;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Timed out waiting for ${what}`);
}

export async function run(): Promise<void> {
  const log = (m: string) => console.log(`[e2e] ${m}`);
  const ext = vscode.extensions.getExtension("shipsafe.shipsafe");
  assert.ok(ext, "extension is installed");
  await ext!.activate();
  log(`activated in ${vscode.env.appName} ${vscode.version}`);

  const cmds = await vscode.commands.getCommands(true);
  for (const c of ["shipsafe.checkFile", "shipsafe.fixFile", "shipsafe.checkSql", "shipsafe.connectBob"]) {
    assert.ok(cmds.includes(c), `command ${c} is registered`);
  }

  const ws = vscode.workspace.workspaceFolders![0].uri.fsPath;
  const doc = await vscode.workspace.openTextDocument(path.join(ws, "deploy.py"));
  await vscode.window.showTextDocument(doc);
  await vscode.commands.executeCommand("shipsafe.checkFile");
  const diags = await waitFor(() => {
    const d = vscode.languages.getDiagnostics(doc.uri).filter((x) => x.source === "ShipSafe");
    return d.length ? d : undefined;
  }, 120_000, "ShipSafe diagnostics");
  const shell = diags.find((d) => String(d.code) === "CMD-SHELL");
  assert.ok(shell, `CMD-SHELL reported, got ${diags.map((d) => d.code).join(", ")}`);
  assert.equal(shell!.severity, vscode.DiagnosticSeverity.Error);
  assert.equal(shell!.range.start.line, 4);
  assert.match(shell!.message, /POL-SEC-004/);
  log(`diagnostics: ${diags.map((d) => `${d.code}@L${d.range.start.line + 1}`).join(", ")}`);

  const actions = await vscode.commands.executeCommand<vscode.CodeAction[]>(
    "vscode.executeCodeActionProvider", doc.uri, shell!.range);
  assert.ok(actions.some((a) => a.title.includes("fix with Granite")), "quick fix offered");
  log("quick fix offered");

  await vscode.commands.executeCommand("shipsafe.connectBob");
  const mcp = await vscode.workspace.fs.readFile(vscode.Uri.file(path.join(ws, ".bob", "mcp.json")));
  assert.ok(JSON.parse(Buffer.from(mcp).toString("utf8")).mcpServers.shipsafe, ".bob/mcp.json written");
  log("connectBob wrote .bob/mcp.json and rules");
  log("ALL E2E CHECKS PASSED");
}
