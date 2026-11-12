/**
 * Everything ShipSafe needs outside VS Code, found or installed for the user:
 * a Python 3.11-3.13, the ShipSafe engine in a private virtual environment,
 * Ollama with the Granite models, and the shared settings file (~/.shipsafe/.env).
 * No `vscode` import: the UI lives in onboarding.ts, so this is unit tested.
 */
import { spawn } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

export const ENGINE_VERSION = "3.1.0";
export const SITE = "https://shipsafe-bob.vercel.app";
export const WHEEL_URL = `${SITE}/downloads/shipsafe-${ENGINE_VERSION}-py3-none-any.whl`;
export const MIN_PY = [3, 11];
export const MAX_PY = [3, 13];

export type LineSink = (line: string) => void;

export interface RunResult {
  code: number;
  stdout: string;
}

/** Run a program without a shell; stream its output lines; resolve with the exit code (-1 if it could not start). */
export function run(command: string, args: string[], opts: { onLine?: LineSink; env?: NodeJS.ProcessEnv; timeoutMs?: number;
  signal?: AbortSignal; cwd?: string } = {}): Promise<RunResult> {
  return new Promise((resolve) => {
    let stdout = "";
    let settled = false;
    const done = (code: number) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        resolve({ code, stdout });
      }
    };
    let proc: ReturnType<typeof spawn>;
    try {
      proc = spawn(command, args, { cwd: opts.cwd, env: { ...process.env, ...opts.env, PYTHONIOENCODING: "utf-8" },
        shell: false, windowsHide: true });
    } catch {
      resolve({ code: -1, stdout: "" });
      return;
    }
    const timer = setTimeout(() => {
      proc.kill();
      done(-2);
    }, opts.timeoutMs ?? 30_000);
    opts.signal?.addEventListener("abort", () => {
      proc.kill();
      done(-3);
    });
    let partial = "";
    const onData = (chunk: Buffer, keep: boolean) => {
      const text = partial + chunk.toString("utf8");
      const lines = text.split(/\r?\n/);
      partial = lines.pop() || "";
      for (const line of lines) {
        if (keep) {
          stdout += line + "\n";
        }
        if (line.trim()) {
          opts.onLine?.(line);
        }
      }
    };
    proc.stdout?.on("data", (c: Buffer) => onData(c, true));
    proc.stderr?.on("data", (c: Buffer) => onData(c, false));
    proc.on("error", () => done(-1));
    proc.on("close", (code) => {
      if (partial) {
        stdout += partial;
        opts.onLine?.(partial);
      }
      done(code ?? -1);
    });
  });
}

// ------------------------------------------------------------------ Python
export interface PythonInfo {
  command: string;
  args: string[];
  version: string;
  executable: string;
}

/** Interpreters to try, best first. Includes the default install folders, so a fresh install is found
 *  even before the editor's PATH is refreshed. */
export function pythonCandidates(platform = process.platform, env: NodeJS.ProcessEnv = process.env): { command: string; args: string[] }[] {
  const out: { command: string; args: string[] }[] = [];
  const minors = [13, 12, 11];
  if (platform === "win32") {
    for (const m of minors) {
      out.push({ command: "py", args: [`-3.${m}`] });
    }
    const local = env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
    for (const m of minors) {
      out.push({ command: path.join(local, "Programs", "Python", `Python3${m}`, "python.exe"), args: [] });
    }
    for (const m of minors) {
      out.push({ command: path.join(env.ProgramFiles || "C:\\Program Files", `Python3${m}`, "python.exe"), args: [] });
    }
    out.push({ command: "python", args: [] }, { command: "python3", args: [] });
  } else {
    for (const m of minors) {
      out.push({ command: `python3.${m}`, args: [] });
    }
    for (const dir of ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]) {
      for (const m of minors) {
        out.push({ command: `${dir}/python3.${m}`, args: [] });
      }
    }
    out.push({ command: "python3", args: [] }, { command: "python", args: [] });
  }
  return out;
}

/** "3.13|C:\\...\\python.exe" -> version check. */
export function parseProbe(stdout: string): { version: string; executable: string } | undefined {
  const m = /^(\d+)\.(\d+)\|(.+)$/m.exec(stdout.trim());
  if (!m) {
    return undefined;
  }
  const v = [Number(m[1]), Number(m[2])];
  const cmp = (a: number[], b: number[]) => a[0] - b[0] || a[1] - b[1];
  if (cmp(v, MIN_PY) < 0 || cmp(v, MAX_PY) > 0) {
    return undefined;
  }
  return { version: `${v[0]}.${v[1]}`, executable: m[3].trim() };
}

const PROBE = "import sys;print('%d.%d|%s' % (sys.version_info[0], sys.version_info[1], sys.executable))";

export async function findPython(): Promise<PythonInfo | undefined> {
  for (const c of pythonCandidates()) {
    if (path.isAbsolute(c.command) && !fs.existsSync(c.command)) {
      continue;
    }
    const r = await run(c.command, [...c.args, "-c", PROBE], { timeoutMs: 15_000 });
    const info = r.code === 0 ? parseProbe(r.stdout) : undefined;
    if (info) {
      return { command: c.command, args: c.args, ...info };
    }
  }
  return undefined;
}

/** How a user installs Python 3.13 on this platform (undefined: point them at python.org). */
export function pythonInstallCommand(platform = process.platform, hasBrew = false): string | undefined {
  if (platform === "win32") {
    return "winget install -e --id Python.Python.3.13 --scope user --accept-package-agreements --accept-source-agreements";
  }
  if (platform === "darwin" && hasBrew) {
    return "brew install python@3.13";
  }
  return undefined;
}

// ------------------------------------------------------------------ engine
export function venvPython(venvDir: string, platform = process.platform): string {
  return platform === "win32" ? path.join(venvDir, "Scripts", "python.exe") : path.join(venvDir, "bin", "python");
}

/** The ShipSafe version importable by this interpreter, or undefined. */
export async function engineVersion(python: string, args: string[] = []): Promise<string | undefined> {
  const r = await run(python, [...args, "-c", "import shipsafe;print(shipsafe.__version__)"], { timeoutMs: 60_000 });
  const v = r.stdout.trim().split(/\r?\n/).pop();
  return r.code === 0 && v && /^\d+\.\d+/.test(v) ? v : undefined;
}

export function isOlder(version: string, than: string): boolean {
  const a = version.split(".").map(Number);
  const b = than.split(".").map(Number);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if ((a[i] || 0) !== (b[i] || 0)) {
      return (a[i] || 0) < (b[i] || 0);
    }
  }
  return false;
}

/** Find `shipsafe-mcp` on PATH (a user who installed the package with pip themselves). */
export function findOnPath(name: string, envPath = process.env.PATH || "", platform = process.platform): string | undefined {
  const exts = platform === "win32" ? [".exe", ".cmd", ""] : [""];
  for (const dir of envPath.split(path.delimiter).filter(Boolean)) {
    for (const ext of exts) {
      const full = path.join(dir, name + ext);
      try {
        if (fs.statSync(full).isFile()) {
          return full;
        }
      } catch {
        // not here
      }
    }
  }
  return undefined;
}

/** Create (or reuse) a private virtual environment and install the engine into it. */
export async function installEngine(base: PythonInfo, venvDir: string, source: string, onLine: LineSink,
                                    signal?: AbortSignal): Promise<{ ok: boolean; error?: string }> {
  const py = venvPython(venvDir);
  if (!fs.existsSync(py)) {
    onLine(`Creating a private Python ${base.version} environment in ${venvDir}`);
    const r = await run(base.command, [...base.args, "-m", "venv", venvDir], { onLine, timeoutMs: 180_000, signal });
    if (r.code !== 0 || !fs.existsSync(py)) {
      return { ok: false, error: process.platform === "linux"
        ? `Could not create a virtual environment. Install the venv module (e.g. sudo apt install python${base.version}-venv) and retry.`
        : "Could not create a virtual environment with " + base.executable };
    }
  }
  onLine(`Installing ShipSafe ${ENGINE_VERSION} and its AI frameworks (first time takes a few minutes)`);
  const r = await run(py, ["-m", "pip", "install", "--disable-pip-version-check", "--upgrade", source],
    { onLine, timeoutMs: 1_800_000, signal });
  if (r.code !== 0) {
    return { ok: false, error: r.code === -3 ? "Cancelled." : "pip could not install ShipSafe; see the ShipSafe log." };
  }
  return { ok: true };
}

/** Short progress text from a pip output line. */
export function pipProgress(line: string): string | undefined {
  const m = /^(Collecting|Downloading|Installing collected packages|Successfully installed|Building wheel for)\s*(\S*)/.exec(line.trim());
  if (!m) {
    return undefined;
  }
  if (m[1] === "Collecting") {
    return `getting ${m[2].split(/[<>=!;\[]/)[0]}`;
  }
  if (m[1] === "Installing collected packages") {
    return "installing packages";
  }
  if (m[1] === "Successfully installed") {
    return "done";
  }
  return undefined;
}

// ------------------------------------------------------------------ Granite via Ollama
/** Installed model names, or undefined when Ollama is not answering. */
export async function ollamaModels(host: string, timeoutMs = 3000): Promise<string[] | undefined> {
  try {
    const res = await fetch(`${host}/api/tags`, { signal: AbortSignal.timeout(timeoutMs) });
    if (!res.ok) {
      return undefined;
    }
    const body = (await res.json()) as { models?: { name: string }[] };
    return (body.models || []).map((m) => m.name);
  } catch {
    return undefined;
  }
}

export function hasModel(installed: string[], wanted: string): boolean {
  const w = wanted.includes(":") ? wanted : `${wanted}:latest`;
  return installed.some((n) => n === w || n === wanted);
}

/** Pull a model through the Ollama HTTP API, reporting percent done. */
export async function pullModel(host: string, name: string, onProgress: (pct: number | undefined, status: string) => void,
                                signal?: AbortSignal): Promise<void> {
  const res = await fetch(`${host}/api/pull`, { method: "POST", body: JSON.stringify({ name, stream: true }), signal });
  if (!res.ok || !res.body) {
    throw new Error(`Ollama could not pull ${name} (HTTP ${res.status})`);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() || "";
    for (const line of lines.filter(Boolean)) {
      const ev = JSON.parse(line) as { status?: string; total?: number; completed?: number; error?: string };
      if (ev.error) {
        throw new Error(ev.error);
      }
      onProgress(ev.total ? Math.round(((ev.completed || 0) / ev.total) * 100) : undefined, ev.status || "");
    }
  }
}

export function ollamaExecutable(platform = process.platform, env: NodeJS.ProcessEnv = process.env): string | undefined {
  const onPath = findOnPath("ollama", env.PATH || "", platform);
  if (onPath) {
    return onPath;
  }
  const guesses = platform === "win32"
    ? [path.join(env.LOCALAPPDATA || "", "Programs", "Ollama", "ollama.exe")]
    : ["/usr/local/bin/ollama", "/opt/homebrew/bin/ollama", "/usr/bin/ollama", "/Applications/Ollama.app/Contents/Resources/ollama"];
  return guesses.find((g) => g && fs.existsSync(g));
}

export function ollamaInstallCommand(platform = process.platform, hasBrew = false): string | undefined {
  if (platform === "win32") {
    return "winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements";
  }
  if (platform === "darwin") {
    return hasBrew ? "brew install ollama" : undefined;
  }
  return "curl -fsSL https://ollama.com/install.sh | sh";
}

/** Start `ollama serve` in the background (detached, survives the editor). */
export function startOllama(exe: string): void {
  const p = spawn(exe, ["serve"], { detached: true, stdio: "ignore", windowsHide: true, shell: false });
  p.on("error", () => undefined);
  p.unref();
}

// ------------------------------------------------------------------ shared settings file
export function sharedEnvFile(): string {
  return path.join(os.homedir(), ".shipsafe", ".env");
}

export function parseEnv(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) {
      continue;
    }
    const i = line.indexOf("=");
    out[line.slice(0, i).trim()] = line.slice(i + 1).trim().replace(/^(['"])(.*)\1$/, "$2");
  }
  return out;
}

/** Update KEY=VALUE lines in place (keeping comments and other keys), add missing ones, keep the file private. */
export function mergeEnvText(existing: string, values: Record<string, string>): string {
  const left = new Map(Object.entries(values));
  const lines = existing ? existing.replace(/\r\n/g, "\n").replace(/\n$/, "").split("\n") : [
    "# ShipSafe connection settings (shared by the editor extension, IBM Bob and the CLI). Keep this file private."];
  const out = lines.map((line) => {
    const m = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=/.exec(line);
    if (m && left.has(m[1])) {
      const v = left.get(m[1])!;
      left.delete(m[1]);
      return `${m[1]}=${v}`;
    }
    return line;
  });
  for (const [k, v] of left) {
    out.push(`${k}=${v}`);
  }
  return out.join("\n") + "\n";
}

export function writeSharedEnv(values: Record<string, string>, file = sharedEnvFile()): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const existing = fs.existsSync(file) ? fs.readFileSync(file, "utf8") : "";
  fs.writeFileSync(file, mergeEnvText(existing, values), { encoding: "utf8", mode: 0o600 });
  try {
    fs.chmodSync(file, 0o600);
  } catch {
    // Windows keeps the file in the user's profile, which is already private
  }
}

/** Docker command that starts IBM Db2 Community Edition for ShipSafe. */
export function db2DockerArgs(password: string, port: number): string[] {
  return ["run", "-d", "--name", "shipsafe-db2", "--privileged=true", "-p", `${port}:50000`,
    "-e", "LICENSE=accept", "-e", `DB2INST1_PASSWORD=${password}`, "-e", "DBNAME=TESTDB",
    "-v", "shipsafe-db2-data:/database", "icr.io/db2_community/db2"];
}
