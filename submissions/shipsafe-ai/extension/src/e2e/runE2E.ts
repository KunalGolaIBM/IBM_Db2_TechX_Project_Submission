/**
 * Launches a real editor with the extension under development and runs src/e2e/suite.ts inside it.
 *   node out/e2e/runE2E.js                 -> downloads and uses VS Code stable
 *   node out/e2e/runE2E.js "<path to Bob>" -> uses IBM Bob's own executable
 * Requires SHIPSAFE_PYTHON (interpreter with ShipSafe installed) and SHIPSAFE_ENV_FILE (Db2/Ollama settings).
 */
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { runTests } from "@vscode/test-electron";

async function main(): Promise<void> {
  const root = path.resolve(__dirname, "..", "..");
  const workspace = fs.mkdtempSync(path.join(os.tmpdir(), "shipsafe-e2e-ws-"));
  fs.copyFileSync(path.join(root, "e2e-workspace", "deploy.py"), path.join(workspace, "deploy.py"));
  const userData = fs.mkdtempSync(path.join(os.tmpdir(), "shipsafe-e2e-user-"));
  fs.mkdirSync(path.join(userData, "User"), { recursive: true });
  fs.writeFileSync(path.join(userData, "User", "settings.json"), JSON.stringify({
    "shipsafe.pythonPath": process.env.SHIPSAFE_PYTHON,
    "shipsafe.envFile": process.env.SHIPSAFE_ENV_FILE,
    "shipsafe.checkOnSave": false,
    "workbench.startupEditor": "none",
    "security.workspace.trust.enabled": false,
  }, null, 2));
  await runTests({
    vscodeExecutablePath: process.argv[2] || undefined,
    version: process.argv[2] ? undefined : "stable",
    extensionDevelopmentPath: root,
    extensionTestsPath: path.join(__dirname, "suite"),
    launchArgs: [workspace, "--user-data-dir", userData, "--disable-extensions", "--skip-welcome", "--skip-release-notes"],
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
