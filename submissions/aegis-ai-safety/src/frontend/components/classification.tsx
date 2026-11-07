import { AlertTriangle, CheckCircle2, CircleHelp, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Classification } from "@/lib/types";

export const CLASSIFICATION_META: Record<
  Classification,
  {
    label: string;
    short: string;
    description: string;
    badge: "supported" | "contradicted" | "insufficient" | "error";
    textClass: string;
    borderClass: string;
    bgClass: string;
    dotClass: string;
    chartColor: string;
    Icon: typeof CheckCircle2;
  }
> = {
  SUPPORTED: {
    label: "Supported",
    short: "Supported",
    description: "A retrieved passage explicitly entails the claim.",
    badge: "supported",
    textClass: "text-supported",
    borderClass: "border-supported/35",
    bgClass: "bg-supported/10",
    dotClass: "bg-supported",
    chartColor: "hsl(var(--supported))",
    Icon: CheckCircle2,
  },
  CONTRADICTED: {
    label: "Contradicted",
    short: "Contradicted",
    description: "A retrieved passage explicitly conflicts with the claim.",
    badge: "contradicted",
    textClass: "text-contradicted",
    borderClass: "border-contradicted/35",
    bgClass: "bg-contradicted/10",
    dotClass: "bg-contradicted",
    chartColor: "hsl(var(--contradicted))",
    Icon: XCircle,
  },
  INSUFFICIENT_EVIDENCE: {
    label: "Insufficient evidence",
    short: "Insufficient",
    description: "The evidence does not establish the claim either way. This does not mean the claim is false.",
    badge: "insufficient",
    textClass: "text-insufficient",
    borderClass: "border-insufficient/35",
    bgClass: "bg-insufficient/10",
    dotClass: "bg-insufficient",
    chartColor: "hsl(var(--insufficient))",
    Icon: CircleHelp,
  },
  VERIFICATION_ERROR: {
    label: "Verification error",
    short: "Error",
    description: "The automated verification did not produce a usable judgment.",
    badge: "error",
    textClass: "text-verror",
    borderClass: "border-verror/35",
    bgClass: "bg-verror/10",
    dotClass: "bg-verror",
    chartColor: "hsl(var(--verror))",
    Icon: AlertTriangle,
  },
};

export function ClassificationBadge({
  classification,
  className,
}: {
  classification: Classification | null;
  className?: string;
}) {
  if (!classification) {
    return (
      <Badge variant="default" className={className}>
        Pending
      </Badge>
    );
  }
  const meta = CLASSIFICATION_META[classification];
  const Icon = meta.Icon;
  return (
    <Badge variant={meta.badge} className={cn("gap-1", className)}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {meta.label}
    </Badge>
  );
}

export function ClassificationLegend({ columns = 2 }: { columns?: 1 | 2 }) {
  return (
    <div className={cn("grid gap-3", columns === 2 ? "sm:grid-cols-2" : "grid-cols-1")}>
      {(Object.keys(CLASSIFICATION_META) as Classification[]).map((key) => {
        const meta = CLASSIFICATION_META[key];
        const Icon = meta.Icon;
        return (
          <div key={key} className="flex items-start gap-2.5">
            <span className={cn("mt-0.5 rounded-md border p-1", meta.borderClass, meta.bgClass)}>
              <Icon className={cn("h-3.5 w-3.5", meta.textClass)} aria-hidden="true" />
            </span>
            <div>
              <p className={cn("text-xs font-medium", meta.textClass)}>{meta.label}</p>
              <p className="mt-0.5 text-[11px] leading-4 text-muted">{meta.description}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
