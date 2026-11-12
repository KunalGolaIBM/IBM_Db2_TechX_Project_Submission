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
  if (flavour === "claude") {
    entry.type = "stdio";
  }
  return entry;
}

/** Merge ShipSafe into an existing MCP config JSON text, keeping every other server untouched. */
export function mergeMcpConfig(existing: string | undefined, entry: McpEntry): string {
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
  (servers as Record<string, unknown>)[SERVER_NAME] = { ...previous, ...entry };
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
  writeFile(mcpFile, mergeMcpConfig(existing, mcpEntry(server, "bob")));
  writeFile(rulesFile, BOB_RULES);
  return [mcpFile, rulesFile];
}

/** Writes .mcp.json (Claude Code project scope) and CLAUDE.md guidance when absent. */
export function connectClaude(workspace: string, server: ServerCommand): string[] {
  const mcpFile = path.join(workspace, ".mcp.json");
  const existing = fs.existsSync(mcpFile) ? fs.readFileSync(mcpFile, "utf8") : undefined;
  writeFile(mcpFile, mergeMcpConfig(existing, mcpEntry(server, "claude")));
  return [mcpFile];
}
