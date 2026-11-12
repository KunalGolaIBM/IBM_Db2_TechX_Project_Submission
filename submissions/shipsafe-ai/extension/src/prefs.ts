/** User preferences and the pure logic that applies them (no `vscode` import, so it is unit tested). */
import { CheckResult, Issue } from "./format";

export type Severity = "low" | "medium" | "high" | "critical";
export const SEVERITIES: Severity[] = ["low", "medium", "high", "critical"];

export interface Prefs {
  checkOnSave: boolean;
  checkOnType: boolean;
  checkOnTypeDelayMs: number;
  languages: string[];
  minimumSeverity: Severity;
  blockAt: Severity;
  ignoredRules: string[];
  exclude: string[];
  bandit: boolean;
  citePolicies: boolean;
  fixMaxRounds: number;
  fixAutoApplyVerified: boolean;
  chatModel: string;
  embedModel: string;
  ollamaHost: string;
  notifyOn: "block" | "warn" | "never";
  statusBar: boolean;
  mascot: boolean;
}

export const DEFAULT_PREFS: Prefs = {
  checkOnSave: true,
  checkOnType: false,
  checkOnTypeDelayMs: 1500,
  languages: ["python", "javascript", "typescript", "javascriptreact", "typescriptreact"],
  minimumSeverity: "low",
  blockAt: "high",
  ignoredRules: [],
  exclude: ["**/node_modules/**", "**/.venv/**", "**/venv/**", "**/dist/**", "**/build/**"],
  bandit: true,
  citePolicies: true,
  fixMaxRounds: 3,
  fixAutoApplyVerified: false,
  chatModel: "",   // empty: the engine's default (granite4:micro) or the value in ~/.shipsafe/.env
  embedModel: "",
  ollamaHost: "",
  notifyOn: "block",
  statusBar: true,
  mascot: true,
};

export function rank(severity: string): number {
  const i = SEVERITIES.indexOf(severity as Severity);
  return i < 0 ? 0 : i;
}

/** Turn a raw settings object (any shape) into complete, valid preferences. */
export function normalizePrefs(raw: Partial<Record<keyof Prefs, unknown>>): Prefs {
  const p: Prefs = { ...DEFAULT_PREFS };
  const bool = (k: keyof Prefs) => {
    if (typeof raw[k] === "boolean") {
      (p as any)[k] = raw[k];
    }
  };
  (["checkOnSave", "checkOnType", "bandit", "citePolicies", "fixAutoApplyVerified", "statusBar", "mascot"] as const).forEach(bool);
  const sev = (v: unknown, d: Severity): Severity => (SEVERITIES.includes(v as Severity) ? (v as Severity) : d);
  p.minimumSeverity = sev(raw.minimumSeverity, p.minimumSeverity);
  p.blockAt = sev(raw.blockAt, p.blockAt);
  const list = (v: unknown, d: string[]) =>
    Array.isArray(v) ? v.filter((x): x is string => typeof x === "string" && x.trim() !== "").map((x) => x.trim()) : d;
  p.languages = list(raw.languages, p.languages);
  p.ignoredRules = list(raw.ignoredRules, p.ignoredRules).map((r) => r.toUpperCase());
  p.exclude = list(raw.exclude, p.exclude);
  const num = (v: unknown, d: number, lo: number, hi: number) =>
    typeof v === "number" && Number.isFinite(v) ? Math.min(hi, Math.max(lo, Math.round(v))) : d;
  p.checkOnTypeDelayMs = num(raw.checkOnTypeDelayMs, p.checkOnTypeDelayMs, 300, 10_000);
  p.fixMaxRounds = num(raw.fixMaxRounds, p.fixMaxRounds, 1, 5);
  const str = (v: unknown, d: string) => (typeof v === "string" ? v.trim() : d);
  p.chatModel = str(raw.chatModel, p.chatModel);
  p.embedModel = str(raw.embedModel, p.embedModel);
  p.ollamaHost = str(raw.ollamaHost, p.ollamaHost).replace(/\/+$/, "");
  p.notifyOn = raw.notifyOn === "warn" || raw.notifyOn === "never" ? raw.notifyOn : "block";
  return p;
}

/** True when a rule id matches an ignore entry (exact id, or a prefix ending in `*`, e.g. `B4*`). */
export function isIgnored(ruleId: string, ignored: string[]): boolean {
  const id = ruleId.toUpperCase();
  return ignored.some((r) => (r.endsWith("*") ? id.startsWith(r.slice(0, -1)) : id === r));
}

/** Apply the user's severity floor, ignore list and block threshold to a server result. */
export function applyPrefs(result: CheckResult, prefs: Prefs): CheckResult {
  const issues: Issue[] = result.issues.filter(
    (i) => rank(i.severity) >= rank(prefs.minimumSeverity) && !isIgnored(i.rule_id, prefs.ignoredRules));
  const worst = Math.max(-1, ...issues.map((i) => rank(i.severity)));
  const verdict = worst >= rank(prefs.blockAt) ? "block" : issues.length ? "warn" : "clean";
  const hidden = result.issues.length - issues.length;
  let summary = verdict === "clean" ? "No issues." : `${issues.length} issue${issues.length === 1 ? "" : "s"}` +
    (verdict === "block" ? `; fix the ${prefs.blockAt}+ issues before writing.` : "; safe to write.");
  if (hidden) {
    summary += ` (${hidden} hidden by your ShipSafe settings)`;
  }
  return { ...result, issues, verdict, summary };
}

/** Environment the ShipSafe engine reads, built from preferences (no secrets: those stay in ~/.shipsafe/.env). */
export function engineEnv(prefs: Prefs): Record<string, string> {
  const env: Record<string, string> = {
    SHIPSAFE_BANDIT: String(prefs.bandit),
    SHIPSAFE_CITE_POLICIES: String(prefs.citePolicies),
    SHIPSAFE_FIX_ROUNDS: String(prefs.fixMaxRounds),
  };
  if (prefs.chatModel) {
    env.SHIPSAFE_CHAT_MODEL = prefs.chatModel;
  }
  if (prefs.embedModel) {
    env.SHIPSAFE_EMBED_MODEL = prefs.embedModel;
  }
  if (prefs.ollamaHost) {
    env.OLLAMA_HOST = prefs.ollamaHost;
  }
  return env;
}

/** Counts per severity, highest first, e.g. "1 critical, 2 low". */
export function severityCounts(issues: Issue[]): string {
  const counts = new Map<string, number>();
  for (const i of issues) {
    counts.set(i.severity, (counts.get(i.severity) || 0) + 1);
  }
  return [...SEVERITIES].reverse().filter((s) => counts.has(s)).map((s) => `${counts.get(s)} ${s}`).join(", ");
}

/** Minimal glob matcher for exclude patterns (`**`, `*`, `?`), on forward-slash paths. */
export function matchesGlob(filePath: string, pattern: string): boolean {
  const p = filePath.replace(/\\/g, "/");
  let re = "";
  for (let i = 0; i < pattern.length; i++) {
    const c = pattern[i];
    if (c === "*") {
      if (pattern[i + 1] === "*") {
        re += ".*";
        i++;
        if (pattern[i + 1] === "/") {
          i++;
          re += "(?:/)?";
        }
      } else {
        re += "[^/]*";
      }
    } else if (c === "?") {
      re += "[^/]";
    } else {
      re += c.replace(/[.+^${}()|[\]\\]/g, "\\$&");
    }
  }
  return new RegExp(`^${re}$`, "i").test(p) || new RegExp(`(?:^|/)${re}$`, "i").test(p);
}
