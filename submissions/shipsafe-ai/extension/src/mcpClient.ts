import { ChildProcessWithoutNullStreams, spawn } from "child_process";

/** How to start the ShipSafe MCP server. */
export interface ServerCommand {
  command: string;
  args: string[];
  cwd?: string;
  env?: NodeJS.ProcessEnv;
}

interface Pending {
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
  timer: NodeJS.Timeout;
}

export interface ToolResult {
  isError?: boolean;
  content: { type: string; text?: string }[];
}

/**
 * Minimal Model Context Protocol client over stdio (newline-delimited JSON-RPC 2.0).
 * The extension uses the very same server and tools as IBM Bob, so the editor and
 * the AI agent always get identical verdicts.
 */
export class McpClient {
  private proc?: ChildProcessWithoutNullStreams;
  private nextId = 1;
  private buffer = "";
  private pending = new Map<number, Pending>();
  private ready?: Promise<void>;

  constructor(private readonly server: ServerCommand, private readonly log: (line: string) => void,
              private readonly clientName = "shipsafe-vscode", private readonly clientVersion = "3.0.0") {}

  start(): Promise<void> {
    if (this.ready) {
      return this.ready;
    }
    this.ready = new Promise<void>((resolve, reject) => {
      const proc = spawn(this.server.command, this.server.args, {
        cwd: this.server.cwd,
        env: { ...process.env, ...this.server.env, PYTHONIOENCODING: "utf-8", PYTHONUNBUFFERED: "1" },
        shell: false,
        windowsHide: true,
      });
      this.proc = proc;
      proc.stdout.setEncoding("utf8");
      proc.stdout.on("data", (chunk: string) => this.onData(chunk));
      proc.stderr.setEncoding("utf8");
      proc.stderr.on("data", (chunk: string) => chunk.split(/\r?\n/).filter(Boolean).forEach((l) => this.log(l)));
      proc.on("error", (err) => {
        this.failAll(err);
        this.ready = undefined;
        reject(err);
      });
      proc.on("exit", (code) => {
        this.failAll(new Error(`ShipSafe server exited with code ${code}`));
        this.ready = undefined;
        this.proc = undefined;
      });
      this.request("initialize", {
        protocolVersion: "2025-06-18",
        capabilities: {},
        clientInfo: { name: this.clientName, version: this.clientVersion },
      }, 30_000)
        .then(() => {
          this.notify("notifications/initialized", {});
          resolve();
        })
        .catch((err: Error) => {
          this.ready = undefined;
          reject(err);
        });
    });
    return this.ready;
  }

  async callTool(name: string, args: Record<string, unknown>, timeoutMs = 120_000): Promise<unknown> {
    await this.start();
    const result = (await this.request("tools/call", { name, arguments: args }, timeoutMs)) as ToolResult;
    const text = (result.content || []).map((c) => c.text || "").join("\n");
    if (result.isError) {
      throw new Error(text || `Tool ${name} failed`);
    }
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  }

  async listTools(): Promise<string[]> {
    await this.start();
    const res = (await this.request("tools/list", {}, 30_000)) as { tools: { name: string }[] };
    return res.tools.map((t) => t.name);
  }

  dispose(): void {
    this.failAll(new Error("ShipSafe client stopped"));
    this.proc?.kill();
    this.proc = undefined;
    this.ready = undefined;
  }

  private request(method: string, params: unknown, timeoutMs: number): Promise<unknown> {
    const proc = this.proc;
    if (!proc) {
      return Promise.reject(new Error("ShipSafe server is not running"));
    }
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`ShipSafe did not answer ${method} within ${Math.round(timeoutMs / 1000)} s`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
    });
  }

  private notify(method: string, params: unknown): void {
    this.proc?.stdin.write(JSON.stringify({ jsonrpc: "2.0", method, params }) + "\n");
  }

  private onData(chunk: string): void {
    this.buffer += chunk;
    let newline: number;
    while ((newline = this.buffer.indexOf("\n")) >= 0) {
      const line = this.buffer.slice(0, newline).trim();
      this.buffer = this.buffer.slice(newline + 1);
      if (!line) {
        continue;
      }
      let msg: { id?: number; result?: unknown; error?: { message: string } };
      try {
        msg = JSON.parse(line);
      } catch {
        this.log(`[non-JSON output] ${line.slice(0, 200)}`);
        continue;
      }
      if (typeof msg.id !== "number") {
        continue; // server notification (logging, progress)
      }
      const waiter = this.pending.get(msg.id);
      if (!waiter) {
        continue;
      }
      clearTimeout(waiter.timer);
      this.pending.delete(msg.id);
      if (msg.error) {
        waiter.reject(new Error(msg.error.message));
      } else {
        waiter.resolve(msg.result);
      }
    }
  }

  private failAll(err: Error): void {
    for (const [id, waiter] of this.pending) {
      clearTimeout(waiter.timer);
      waiter.reject(err);
      this.pending.delete(id);
    }
  }
}
