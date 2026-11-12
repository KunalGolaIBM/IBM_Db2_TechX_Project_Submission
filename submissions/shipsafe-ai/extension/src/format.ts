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
