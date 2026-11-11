import clsx from "clsx";
import { STATUS } from "@/lib/status";
import type { ValidationStatus } from "@/lib/api/types";

export function StatusBadge({ status, size = "md", className }: { status: ValidationStatus; size?: "sm" | "md"; className?: string }) {
  const s = STATUS[status];
  const Icon = s.icon;
  return (
    <span
      data-testid="status-badge"
      data-status={status}
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border font-medium whitespace-nowrap",
        size === "sm" ? "px-2 py-0.5 text-[13px]" : "px-3 py-1 text-sm",
        s.tone, className,
      )}
    >
      <Icon aria-hidden className={size === "sm" ? "size-3.5" : "size-4"} strokeWidth={2.25} />
      {s.label}
    </span>
  );
}
