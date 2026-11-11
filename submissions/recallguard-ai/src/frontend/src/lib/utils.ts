import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const fmt = (n: number | null | undefined) => (n ?? 0).toLocaleString("en-IN");

export function fmtDate(s?: string | null, withTime = true) {
  if (!s) return "—";
  const d = new Date(s.length === 10 ? `${s}T00:00:00` : s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleString("en-IN", withTime ? { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" } : { day: "2-digit", month: "short", year: "numeric" });
}

export function timeAgo(s?: string | null) {
  if (!s) return "";
  const diff = (Date.now() - new Date(s).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export const humanize = (s: string) => s.replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

export const RISK_TONE: Record<string, "red" | "amber" | "cyan" | "emerald" | "slate"> = {
  CRITICAL: "red", HIGH: "amber", MODERATE: "cyan", MEDIUM: "amber", LOW: "emerald",
};

export const STATUS_TONE: Record<string, "red" | "amber" | "cyan" | "emerald" | "slate" | "violet"> = {
  REPORTED: "slate", INVESTIGATING: "cyan", EVIDENCE_REVIEW: "cyan", RECALL_RECOMMENDED: "violet", PENDING_APPROVAL: "amber",
  APPROVED: "emerald", REJECTED: "red", EXECUTING: "violet", COMPLETED: "emerald", SUPERSEDED: "slate",
};
