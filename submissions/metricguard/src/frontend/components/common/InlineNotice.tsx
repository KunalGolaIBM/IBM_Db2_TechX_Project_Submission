import clsx from "clsx";
import type { LucideIcon } from "lucide-react";

type Tone = "neutral" | "warn" | "bad" | "info";
const TONES: Record<Tone, string> = {
  neutral: "border-line bg-surface text-ink-2",
  info: "border-accent/25 bg-accent-soft text-accent-ink",
  warn: "border-warn/30 bg-warn-soft text-warn",
  bad: "border-bad/25 bg-bad-soft text-bad",
};

export function InlineNotice({ tone = "neutral", icon: Icon, title, children, action, role, testId }: {
  tone?: Tone; icon?: LucideIcon; title?: string; children?: React.ReactNode; action?: React.ReactNode; role?: "alert" | "status"; testId?: string;
}) {
  return (
    <div role={role} data-testid={testId} className={clsx("flex items-start gap-3 rounded-xl border px-4 py-3", TONES[tone])}>
      {Icon && <Icon aria-hidden className="mt-0.5 size-5 shrink-0" strokeWidth={2} />}
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold leading-snug">{title}</p>}
        {children && <div className={clsx("text-[15px] leading-relaxed", title && "mt-0.5", tone === "neutral" ? "" : "text-ink-2")}>{children}</div>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
