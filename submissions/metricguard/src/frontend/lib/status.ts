import { CircleAlert, CircleHelp, ShieldAlert, ShieldCheck, ShieldX, type LucideIcon } from "lucide-react";
import type { ValidationStatus } from "@/lib/api/types";

export interface StatusStyle {
  label: string;
  icon: LucideIcon;
  /** Tailwind classes: text color, soft background, border */
  tone: string;
  bar: string;
  headline: string;
  /** What the status honestly means, per API contract §2 */
  meaning: string;
}

export const STATUS: Record<ValidationStatus, StatusStyle> = {
  VERIFIED: {
    label: "Verified", icon: ShieldCheck,
    tone: "text-ok bg-ok-soft border-ok/25", bar: "bg-ok",
    headline: "All verification checks passed",
    meaning: "Approved metrics, governed SQL, executed on IBM Db2 and reconciled against independent control queries.",
  },
  EXECUTED_WITH_WARNINGS: {
    label: "Executed with warnings", icon: ShieldAlert,
    tone: "text-warn bg-warn-soft border-warn/30", bar: "bg-warn",
    headline: "Executed, with warnings to review",
    meaning: "The governed SQL ran and the numbers are correct for the plan, but at least one check raised a warning.",
  },
  AMBIGUOUS: {
    label: "Needs clarification", icon: CircleHelp,
    tone: "text-amb bg-amb-soft border-amb/25", bar: "bg-amb",
    headline: "This question has more than one valid reading",
    meaning: "Nothing was executed. Pick an interpretation or rephrase the question.",
  },
  BLOCKED: {
    label: "Blocked", icon: ShieldX,
    tone: "text-bad bg-bad-soft border-bad/25", bar: "bg-bad",
    headline: "This request was rejected before execution",
    meaning: "No SQL was executed against your data.",
  },
  EXECUTION_FAILED: {
    label: "Execution failed", icon: CircleAlert,
    tone: "text-fail bg-fail-soft border-fail/30", bar: "bg-fail",
    headline: "The query did not complete",
    meaning: "The plan was valid, but IBM Db2 did not return a result. No numbers are shown.",
  },
};

export const isExecuted = (s: ValidationStatus) => s === "VERIFIED" || s === "EXECUTED_WITH_WARNINGS";
