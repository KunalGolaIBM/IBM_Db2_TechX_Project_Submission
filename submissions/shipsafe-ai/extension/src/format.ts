/** Pure helpers shared by the extension and its unit tests (no `vscode` import here). */

export interface Issue {
  rule_id: string;
  severity: string;
  category: string;
  title: string;
  line: number;
  snippet: string;
  why: string;
  fix: string;
  sources: string[];
  policy?: { doc_id: string; title: string; section: string; excerpt: string } | null;
}

export interface CheckResult {
  verdict: "clean" | "warn" | "block";
  language: string;
  issues: Issue[];
  duration_ms: number;
  summary: string;
}

/** 0 = Error, 1 = Warning, 2 = Information (matches vscode.DiagnosticSeverity). */
export function diagnosticLevel(severity: string): 0 | 1 | 2 {
  if (severity === "critical" || severity === "high") {
    return 0;
  }
  return severity === "medium" ? 1 : 2;
}

export function diagnosticMessage(issue: Issue): string {
  let text = `${issue.title}. ${issue.fix}`;
  if (issue.policy) {
    text += ` [${issue.policy.doc_id}: ${issue.policy.title}]`;
  }
  return text;
}

export function statusText(verdict: string | undefined, count: number): string {
  if (verdict === "block") {
    return `$(error) ShipSafe: ${count} blocking`;
  }
  if (verdict === "warn") {
    return `$(warning) ShipSafe: ${count} warning${count === 1 ? "" : "s"}`;
  }
  if (verdict === "clean") {
    return "$(shield) ShipSafe: clean";
  }
  return "$(shield) ShipSafe";
}

const SUPPORTED = new Set(["python", "javascript", "typescript", "javascriptreact", "typescriptreact"]);

export function isSupportedLanguage(languageId: string): boolean {
  return SUPPORTED.has(languageId);
}

export function markdownReport(title: string, body: unknown): string {
  if (typeof body === "string") {
    return `# ${title}\n\n${body}\n`;
  }
  return `# ${title}\n\n\`\`\`json\n${JSON.stringify(body, null, 2)}\n\`\`\`\n`;
}

/** True when the error means the ShipSafe Python package is not installed where the extension looks for it. */
export function isMissingServer(message: string): boolean {
  return /\bENOENT\b|No module named ['"]?shipsafe|exited with code 9009\b|is not recognized as an internal/i.test(message);
}

/** Friendly name for the MCP client recorded with each check in Db2 (GUARD_EVENTS.CLIENT). */
export function agentLabel(client: string, inBob = false): string {
  const c = (client || "").toLowerCase();
  if (c === "mcp-use") {
    // IBM Bob's agent talks MCP through the mcp-use library and reports that name.
    return inBob ? "IBM Bob agent" : "MCP agent (mcp-use)";
  }
  if (c.includes("shipsafe-vscode")) {
    return "Shippy (files you or an agent saved)";
  }
  if (c.includes("bob")) {
    return "IBM Bob agent";
  }
  if (c.includes("claude")) {
    return "Claude Code";
  }
  if (c.includes("cursor")) {
    return "Cursor";
  }
  if (c.includes("copilot") || c.includes("visual studio code") || c === "vscode") {
    return "VS Code agent mode";
  }
  if (c === "cli") {
    return "CLI / git hook";
  }
  return client || "unknown";
}

/** The prompt Shippy hands to IBM Bob: the user's task plus the ShipSafe workflow. */
export function bobTaskPrompt(task: string): string {
  return `${task.trim()}\n\nWork the ShipSafe way (rules in .bob/rules/shipsafe.md): call shipsafe_recall first; ` +
    "call shipsafe_check_code with the complete content of every file BEFORE writing it and never write a file whose verdict is block " +
    "(fix it or use shipsafe_fix_code and only use verified fixes); validate every SQL statement with shipsafe_check_sql; " +
    "finish with shipsafe_readiness_check (profile quick) and report what ShipSafe caught.";
}
