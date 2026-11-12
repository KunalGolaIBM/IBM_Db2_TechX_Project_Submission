import * as fs from "fs";
import * as path from "path";
import { ServerCommand } from "./mcpClient";

export const SERVER_NAME = "shipsafe";

/** Rules that make IBM Bob use ShipSafe while it codes (.bob/rules/shipsafe.md). */
export const BOB_RULES = `# ShipSafe: keep every change production-ready

ShipSafe is connected as an MCP server. Use it on every coding task:

1. **Start of a task:** call \`shipsafe_recall\` with a short description of the task and follow any
   decisions or conventions it returns.
2. **Before writing or editing a source file:** call \`shipsafe_check_code\` with the complete new
   file content and the file path.
   - \`block\`: do not write the file. Fix the listed issues yourself or call \`shipsafe_fix_code\`,
     then check again. Only use \`fixed_code\` when \`verified\` is true.
   - \`warn\`: write the file and mention the warnings in your summary.
3. **SQL for IBM Db2:** call \`shipsafe_db2_schema\` to see the real tables, and validate every
   statement with \`shipsafe_check_sql\` before using it. Always use \`?\` parameter markers.
4. **Team rules:** when unsure how something must be done here, call \`shipsafe_ask_standards\`.
5. **Decisions:** when the user decides something that should hold for later work (a library choice,
   a naming rule, an API contract), save it with \`shipsafe_remember\`.
6. **Before you say the task is done:** call \`shipsafe_readiness_check\` with profile \`quick\` and
   report the verdict.

Never hardcode secrets; read them from environment variables.
`;

export interface McpEntry {
  command: string;
  args: string[];
  env?: Record<string, string>;
  type?: string;
  [key: string]: unknown;
}

export function mcpEntry(server: ServerCommand, flavour: "bob" | "claude"): McpEntry {
  const entry: McpEntry = { command: server.command, args: server.args };
  const env: Record<string, string> = {};
  for (const [k, v] of Object.entries(server.env || {})) {
    if (typeof v === "string" && k.startsWith("SHIPSAFE_")) {
      env[k] = v;
    }
  }
  if (Object.keys(env).length) {
    entry.env = env;
  }
  if (flavour === "bob") {
    // Bob starts MCP servers outside the project and expands ${workspaceFolder} in env itself.
    entry.env = { ...(entry.env || {}), SHIPSAFE_WORKSPACE: "${workspaceFolder}" };
  }
  if (flavour === "claude") {
    entry.type = "stdio";
  }
  return entry;
}

/** Merge ShipSafe into an existing MCP config JSON text, keeping every other server untouched. */
export function mergeMcpConfig(existing: string | undefined, entry: McpEntry, defaults: Record<string, unknown> = {}): string {
  let config: { mcpServers?: Record<string, unknown>; [key: string]: unknown } = {};
  if (existing && existing.trim()) {
    const parsed = JSON.parse(existing);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      config = parsed;
    } else {
      throw new Error("Existing MCP config is not a JSON object");
    }
  }
  const servers = (config.mcpServers && typeof config.mcpServers === "object") ? config.mcpServers : {};
  const previous = (servers as Record<string, Record<string, unknown>>)[SERVER_NAME] || {};
  // Keep user-set options such as "alwaysAllow" or "disabled"; refresh command, args and env.
  (servers as Record<string, unknown>)[SERVER_NAME] = { ...defaults, ...previous, ...entry };
  config.mcpServers = servers;
  return JSON.stringify(config, null, 2) + "\n";
}

function writeFile(file: string, text: string): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text, "utf8");
}

/** Writes .bob/mcp.json and .bob/rules/shipsafe.md. Returns the files written. */
export function connectBob(workspace: string, server: ServerCommand): string[] {
  const mcpFile = path.join(workspace, ".bob", "mcp.json");
  const rulesFile = path.join(workspace, ".bob", "rules", "shipsafe.md");
  const existing = fs.existsSync(mcpFile) ? fs.readFileSync(mcpFile, "utf8") : undefined;
  // Bob cancels MCP tool calls after 60 s unless told otherwise; Granite fixes can take longer.
  writeFile(mcpFile, mergeMcpConfig(existing, mcpEntry(server, "bob"), { timeout: 600_000 }));
  writeFile(rulesFile, BOB_RULES);
  return [mcpFile, rulesFile];
}

/** The command Claude Code runs before every Write/Edit: `shipsafe guard-hook` from the same engine. */
export function hookCommand(server: ServerCommand): string {
  const q = (p: string) => `"${p.split("\\").join("/")}"`;
  const exe = /shipsafe-mcp(\.exe)?$/i;
  if (exe.test(server.command)) {
    return `${q(server.command.replace(exe, (_m: string, ext?: string) => `shipsafe${ext || ""}`))} guard-hook`;
  }
  return `${q(server.command)} -m shipsafe.cli guard-hook`;
}

/** Add ShipSafe's PreToolUse hook to .claude/settings.json, keeping every other setting and hook. */
export function mergeHookSettings(existing: string | undefined, command: string): string {
  const config = existing && existing.trim() ? JSON.parse(existing) : {};
  if (!config || typeof config !== "object" || Array.isArray(config)) {
    throw new Error(".claude/settings.json is not a JSON object");
  }
  config.hooks = config.hooks && typeof config.hooks === "object" ? config.hooks : {};
  const pre = (Array.isArray(config.hooks.PreToolUse) ? config.hooks.PreToolUse : [])
    .filter((h: { hooks?: { command?: string }[] }) => !(h.hooks || []).some((x) => String(x.command || "").includes("guard-hook")));
  pre.push({ matcher: "Write|Edit|MultiEdit", hooks: [{ type: "command", command, timeout: 120 }] });
  config.hooks.PreToolUse = pre;
  return JSON.stringify(config, null, 2) + "\n";
}

/** Writes .mcp.json (Claude Code project scope) and the pre-write hook in .claude/settings.json. */
export function connectClaude(workspace: string, server: ServerCommand): string[] {
  const mcpFile = path.join(workspace, ".mcp.json");
  const existing = fs.existsSync(mcpFile) ? fs.readFileSync(mcpFile, "utf8") : undefined;
  writeFile(mcpFile, mergeMcpConfig(existing, mcpEntry(server, "claude")));
  const settings = path.join(workspace, ".claude", "settings.json");
  const current = fs.existsSync(settings) ? fs.readFileSync(settings, "utf8") : undefined;
  writeFile(settings, mergeHookSettings(current, hookCommand(server)));
  return [mcpFile, settings];
}
