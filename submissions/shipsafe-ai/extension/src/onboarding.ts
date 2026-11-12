/** Guided, mostly automatic setup: engine, Granite, Db2 and the AI agent connection. */
import * as crypto from "crypto";
import * as fs from "fs";
import * as net from "net";
import * as path from "path";
import * as vscode from "vscode";
import * as engine from "./engine";
import { SERVER_NAME } from "./connect";

export type State = "ok" | "missing" | "working" | "unknown";

export interface EngineCmd {
  command: string;
  args: string[];
  source: "setting" | "managed" | "path";
  version?: string;
}

/** Run a shell command in a visible terminal task and wait for its exit code. */
export async function runVisible(name: string, commandLine: string): Promise<number | undefined> {
  const task = new vscode.Task({ type: "shipsafe" }, vscode.TaskScope.Global, name, "ShipSafe",
    new vscode.ShellExecution(commandLine));
  task.presentationOptions = { reveal: vscode.TaskRevealKind.Always, panel: vscode.TaskPanelKind.Dedicated, clear: true };
  const exec = await vscode.tasks.executeTask(task);
  return new Promise((resolve) => {
    const sub = vscode.tasks.onDidEndTaskProcess((e) => {
      if (e.execution === exec) {
        sub.dispose();
        resolve(e.exitCode);
      }
    });
  });
}

function portFree(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const srv = net.createServer().once("error", () => resolve(false)).once("listening", () => srv.close(() => resolve(true)));
    srv.listen(port, "127.0.0.1");
  });
}

export class Setup {
  engine?: EngineCmd;
  engineState: State = "unknown";
  engineDetail = "Looking for the ShipSafe engine...";
  graniteState: State = "unknown";
  graniteDetail = "Not checked yet";
  db2State: State = "unknown";
  db2Detail = "Not checked yet";
  private installing?: Promise<boolean>;
  output?: vscode.OutputChannel;

  constructor(private readonly ctx: vscode.ExtensionContext, private readonly log: (line: string) => void,
              private readonly changed: () => void) {}

  get venvDir(): string {
    return path.join(this.ctx.globalStorageUri.fsPath, "engine");
  }

  private cfg() {
    return vscode.workspace.getConfiguration("shipsafe");
  }

  /** Settings file values (shared with Bob and the CLI). */
  sharedEnv(): Record<string, string> {
    const file = (this.cfg().get<string>("envFile") || "").trim() || engine.sharedEnvFile();
    try {
      return engine.parseEnv(fs.readFileSync(file, "utf8"));
    } catch {
      return {};
    }
  }

  ollamaHost(): string {
    return ((this.cfg().get<string>("granite.host") || "").trim() || this.sharedEnv().OLLAMA_HOST || "http://localhost:11434").replace(/\/+$/, "");
  }

  models(): { chat: string; embed: string } {
    const env = this.sharedEnv();
    return {
      chat: (this.cfg().get<string>("granite.chatModel") || "").trim() || env.SHIPSAFE_CHAT_MODEL || "granite4:micro",
      embed: (this.cfg().get<string>("granite.embedModel") || "").trim() || env.SHIPSAFE_EMBED_MODEL || "granite-embedding:30m",
    };
  }

  // ------------------------------------------------------------ engine
  /** Find the engine: the pythonPath setting, our private environment, then `shipsafe-mcp` on PATH. */
  async resolveEngine(): Promise<EngineCmd | undefined> {
    this.engineState = "working";
    this.engineDetail = "Looking for the ShipSafe engine...";
    this.changed();
    const python = (this.cfg().get<string>("pythonPath") || "").trim();
    let found: EngineCmd | undefined;
    if (python) {
      const v = await engine.engineVersion(python);
      found = v ? { command: python, args: ["-m", "shipsafe.mcp_server"], source: "setting", version: v } : undefined;
      if (!found) {
        this.log(`shipsafe.pythonPath (${python}) cannot import shipsafe.`);
      }
    }
    if (!found) {
      const py = engine.venvPython(this.venvDir);
      if (fs.existsSync(py)) {
        const v = await engine.engineVersion(py);
        if (v) {
          found = { command: py, args: ["-m", "shipsafe.mcp_server"], source: "managed", version: v };
        }
      }
    }
    if (!found) {
      const exe = engine.findOnPath("shipsafe-mcp");
      if (exe) {
        found = { command: exe, args: [], source: "path" };
      }
    }
    this.engine = found;
    this.engineState = found ? "ok" : "missing";
    this.engineDetail = found
      ? `ShipSafe ${found.version || ""} (${found.source === "managed" ? "private environment" : found.source === "path" ? "from PATH" : "your Python"})`.replace("  ", " ")
      : "Needed for every check. One click; installs into a private folder.";
    this.changed();
    return found;
  }

  /** Engine older than this extension, in our private environment: upgrade quietly in the background. */
  needsUpgrade(): boolean {
    return this.engine?.source === "managed" && !!this.engine.version && engine.isOlder(this.engine.version, engine.ENGINE_VERSION);
  }

  installEngine(): Promise<boolean> {
    this.installing ??= this.doInstall().finally(() => (this.installing = undefined));
    return this.installing;
  }

  private async doInstall(): Promise<boolean> {
    this.engineState = "working";
    this.engineDetail = "Finding Python 3.11-3.13...";
    this.changed();
    let py = await engine.findPython();
    if (!py) {
      const cmd = engine.pythonInstallCommand(process.platform, !!engine.findOnPath("brew"));
      const pick = await vscode.window.showWarningMessage(
        "ShipSafe needs Python 3.11, 3.12 or 3.13 (free). " + (cmd ? `Install Python 3.13 now with:\n${cmd}` : "Install it from python.org, then retry."),
        { modal: true }, ...(cmd ? ["Install Python 3.13"] : ["Open python.org"]));
      if (pick === "Install Python 3.13" && cmd) {
        const code = await runVisible("Install Python 3.13", cmd);
        this.log(`Python install exited with ${code}`);
        py = await engine.findPython();
      } else if (pick) {
        void vscode.env.openExternal(vscode.Uri.parse("https://www.python.org/downloads/"));
      }
      if (!py) {
        this.engineState = "missing";
        this.engineDetail = "Python 3.11-3.13 not found. Install it, then click Install again.";
        this.changed();
        return false;
      }
    }
    const source = (this.cfg().get<string>("engineSource") || "").trim() || engine.WHEEL_URL;
    this.log(`Using Python ${py.version} at ${py.executable}; installing from ${source}`);
    const ok = await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, cancellable: true,
      title: "Shippy is installing the ShipSafe engine" }, async (progress, token) => {
      const abort = new AbortController();
      token.onCancellationRequested(() => abort.abort());
      let n = 0;
      const r = await engine.installEngine(py!, this.venvDir, source, (line) => {
        this.log(line);
        const p = engine.pipProgress(line);
        if (p) {
          n++;
          progress.report({ message: `${p} (${n})` });
          this.engineDetail = `Installing: ${p}`;
          this.changed();
        }
      }, abort.signal);
      if (!r.ok) {
        void vscode.window.showErrorMessage(`ShipSafe engine install failed: ${r.error}`, "Show log").then((x) => x && this.showLog());
      }
      return r.ok;
    });
    await this.resolveEngine();
    if (ok && this.engine) {
      void vscode.window.showInformationMessage(`ShipSafe engine ${this.engine.version || ""} is ready. Save a Python, JS or TS file to see it work.`,
        "Try the demo").then((x) => x && vscode.commands.executeCommand("shipsafe.tryDemo"));
    }
    return ok && !!this.engine;
  }

  showLog(): void {
    this.output?.show(true);
  }

  // ------------------------------------------------------------ Granite
  async refreshGranite(): Promise<void> {
    // Ollama answers slowly while it is busy generating (e.g. during a Granite fix): be patient, retry once.
    const host = this.ollamaHost();
    const models = (await engine.ollamaModels(host, 8000)) ?? (await engine.ollamaModels(host, 15000));
    const want = this.models();
    if (!models) {
      this.graniteState = "missing";
      this.graniteDetail = engine.ollamaExecutable() ? "Ollama is installed but not running." : "For verified AI fixes and standards answers. Runs locally, free.";
    } else {
      const missing = [want.chat, want.embed].filter((m) => !engine.hasModel(models, m));
      this.graniteState = missing.length ? "missing" : "ok";
      this.graniteDetail = missing.length ? `Ollama is running; missing ${missing.join(", ")}.` : `${want.chat} + ${want.embed} ready (local)`;
    }
    this.changed();
  }

  async setupGranite(): Promise<void> {
    const host = this.ollamaHost();
    this.graniteState = "working";
    this.graniteDetail = "Checking Ollama...";
    this.changed();
    let models = await engine.ollamaModels(host);
    if (!models) {
      let exe = engine.ollamaExecutable();
      if (!exe) {
        const cmd = engine.ollamaInstallCommand(process.platform, !!engine.findOnPath("brew"));
        const pick = await vscode.window.showInformationMessage(
          "Granite runs locally through Ollama (free, from ollama.com). " + (cmd ? `Install it now with:\n${cmd}` : "Download it from ollama.com."),
          { modal: true }, cmd ? "Install Ollama" : "Open ollama.com");
        if (pick === "Install Ollama" && cmd) {
          this.log(`Ollama install exited with ${await runVisible("Install Ollama", cmd)}`);
          exe = engine.ollamaExecutable();
        } else if (pick) {
          void vscode.env.openExternal(vscode.Uri.parse("https://ollama.com/download"));
        }
      }
      if (exe) {
        this.graniteDetail = "Starting Ollama...";
        this.changed();
        engine.startOllama(exe);
        for (let i = 0; i < 20 && !models; i++) {
          await new Promise((r) => setTimeout(r, 1000));
          models = await engine.ollamaModels(host);
        }
      }
      if (!models) {
        await this.refreshGranite();
        return;
      }
    }
    const want = this.models();
    const missing = [want.chat, want.embed].filter((m) => !engine.hasModel(models!, m));
    if (missing.length) {
      const pick = await vscode.window.showInformationMessage(
        `Download the IBM Granite models ${missing.join(" and ")}? (about 2 GB, one time; they stay on this machine)`, { modal: true }, "Download");
      if (pick) {
        await vscode.window.withProgress({ location: vscode.ProgressLocation.Notification, cancellable: true,
          title: "Shippy is downloading IBM Granite" }, async (progress, token) => {
          const abort = new AbortController();
          token.onCancellationRequested(() => abort.abort());
          for (const m of missing) {
            let last = -1;
            try {
              await engine.pullModel(host, m, (pct, status) => {
                if (pct !== undefined && pct !== last) {
                  progress.report({ message: `${m}: ${pct}%`, increment: 0 });
                  last = pct;
                } else if (pct === undefined) {
                  progress.report({ message: `${m}: ${status}` });
                }
              }, abort.signal);
            } catch (err) {
              void vscode.window.showErrorMessage(`Could not download ${m}: ${err instanceof Error ? err.message : err}`);
              return;
            }
          }
        });
      }
    }
    engine.writeSharedEnv({ OLLAMA_HOST: host, SHIPSAFE_CHAT_MODEL: want.chat, SHIPSAFE_EMBED_MODEL: want.embed });
    await this.refreshGranite();
  }

  // ------------------------------------------------------------ Db2
  setDb2(status: { connected?: boolean; version?: string; host?: string; port?: number; database?: string; error?: string } | undefined): void {
    if (status?.connected === false || !status) {
      this.db2State = "missing";
      this.db2Detail = "Required for team policies (Db2 vectors), memory, SQL validation and the audit trail.";
    } else {
      this.db2State = "ok";
      this.db2Detail = `Connected: ${(status.version || "IBM Db2").replace(/^DB2 /, "Db2 ")} at ${status.host}:${status.port}/${status.database}`;
    }
    this.changed();
  }

  /** Ask how to get a Db2 and store the connection in the shared settings file. Returns true if settings changed. */
  async setupDb2(): Promise<boolean> {
    const hasDocker = !!engine.findOnPath("docker");
    const items: (vscode.QuickPickItem & { id: string })[] = [
      { id: "existing", label: "$(plug) Connect to a Db2 I already have", detail: "Host, port, database, user and password." },
      ...(hasDocker ? [{ id: "docker", label: "$(package) Start IBM Db2 Community Edition in Docker",
        detail: "Free. Downloads about 3 GB once; the first start takes about 5 minutes." }] : []),
      { id: "skip", label: "$(clock) Later", detail: "Until Db2 is connected, only the basic code checks run: no policies, memory, SQL validation or history." },
    ];
    const pick = await vscode.window.showQuickPick(items, { title: "Connect IBM Db2 to ShipSafe", ignoreFocusOut: true });
    if (!pick || pick.id === "skip") {
      return false;
    }
    if (pick.id === "existing") {
      const env = this.sharedEnv();
      const ask = (prompt: string, value: string, password = false) =>
        vscode.window.showInputBox({ title: "IBM Db2 connection", prompt, value, password, ignoreFocusOut: true });
      const host = await ask("Host", env.DB2_HOST || "localhost");
      if (host === undefined) { return false; }
      const port = await ask("Port", env.DB2_PORT || "50000");
      if (port === undefined) { return false; }
      const database = await ask("Database", env.DB2_NAME || "TESTDB");
      if (database === undefined) { return false; }
      const user = await ask("User", env.DB2_USERNAME || "db2inst1");
      if (user === undefined) { return false; }
      const password = await ask("Password (saved only in ~/.shipsafe/.env on this machine)", "", true);
      if (!password) { return false; }
      engine.writeSharedEnv({ DB2_HOST: host, DB2_PORT: port, DB2_NAME: database, DB2_USERNAME: user, DB2_PASSWORD: password });
      return true;
    }
    let port = 50001;
    while (!(await portFree(port)) && port < 50020) {
      port++;
    }
    const password = crypto.randomBytes(12).toString("base64").replace(/[^A-Za-z0-9]/g, "").slice(0, 14) + "9a";
    const ok = await vscode.window.showInformationMessage(
      `Start IBM Db2 Community Edition (container "shipsafe-db2", port ${port}). This accepts the Db2 Community Edition license. Continue?`,
      { modal: true }, "Start Db2");
    if (!ok) {
      return false;
    }
    const existing = await engine.run("docker", ["ps", "-a", "--filter", "name=^shipsafe-db2$", "--format", "{{.Names}}"]);
    if (existing.stdout.includes("shipsafe-db2")) {
      await runVisible("Start Db2", "docker start shipsafe-db2");
      return true; // keeps its original password, already in the settings file
    }
    const code = await runVisible("Start IBM Db2", ["docker", ...engine.db2DockerArgs(password, port)].join(" "));
    if (code !== 0) {
      void vscode.window.showErrorMessage("Docker could not start Db2; see the terminal.");
      return false;
    }
    engine.writeSharedEnv({ DB2_HOST: "localhost", DB2_PORT: String(port), DB2_NAME: "TESTDB", DB2_USERNAME: "db2inst1", DB2_PASSWORD: password });
    void vscode.window.showInformationMessage("Db2 is starting (about 5 minutes the first time). Shippy will connect as soon as it is up.");
    return true;
  }

  // ------------------------------------------------------------ agent
  isBob(): boolean {
    return /bob/i.test(vscode.env.appName);
  }

  agentConnected(ws: string | undefined): boolean {
    if (!ws) {
      return false;
    }
    const files = this.isBob() ? [path.join(ws, ".bob", "mcp.json")] : [path.join(ws, ".vscode", "mcp.json"), path.join(ws, ".mcp.json")];
    return files.some((f) => {
      try {
        return fs.readFileSync(f, "utf8").includes(`"${SERVER_NAME}"`);
      } catch {
        return false;
      }
    });
  }
}
