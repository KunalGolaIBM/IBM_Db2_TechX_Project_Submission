import * as React from 'react';
import { Badge } from './badge';

export interface StatusBadgeProps {
  status: string;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const normalized = status.toLowerCase();

  let variant: 'default' | 'success' | 'warning' | 'danger' | 'info' = 'default';

  if (['approved', 'completed', 'settled', 'active', 'success'].includes(normalized)) {
    variant = 'success';
  } else if (['pending', 'pending_approval', 'draft', 'in_progress'].includes(normalized)) {
    variant = 'warning';
  } else if (['rejected', 'failed', 'cancelled', 'voided'].includes(normalized)) {
    variant = 'danger';
  } else if (['cash', 'upi', 'admin', 'member'].includes(normalized)) {
    variant = 'info';
  }

  // Format label: "pending_approval" -> "Pending Approval"
  const formattedLabel = status
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');

  return (
    <Badge variant={variant} className={className}>
      {formattedLabel}
    </Badge>
  );
}
