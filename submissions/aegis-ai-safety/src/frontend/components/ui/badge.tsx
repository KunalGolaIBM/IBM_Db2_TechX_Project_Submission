import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2 py-0.5 font-mono text-[10px] font-medium uppercase tracking-wider transition-colors",
  {
    variants: {
      variant: {
        default: "border-border bg-panel-2 text-muted",
        supported: "border-supported/30 bg-supported/10 text-supported",
        contradicted: "border-contradicted/30 bg-contradicted/10 text-contradicted",
        insufficient: "border-insufficient/30 bg-insufficient/10 text-insufficient",
        error: "border-verror/30 bg-verror/10 text-verror",
        accent: "border-accent/30 bg-accent-soft text-accent",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
