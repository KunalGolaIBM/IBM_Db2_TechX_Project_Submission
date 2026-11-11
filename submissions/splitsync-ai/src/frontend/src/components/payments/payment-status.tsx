'use client';

import * as React from 'react';
import { StatusBadge } from '@/components/ui/status-badge';
import { Badge } from '@/components/ui/badge';
import { formatDateTime } from '@/lib/utils';

export interface PaymentStatusProps {
  status: string;
  timestamp?: string;
  providerTxnId?: string;
  source?: string;
  className?: string;
}

export function PaymentStatus({
  status,
  timestamp,
  providerTxnId,
  source = 'DEMO',
  className = '',
}: PaymentStatusProps) {
  const isDemo = source.toUpperCase() === 'DEMO';

  return (
    <div className={`flex flex-col space-y-1 ${className}`}>
      <div className="flex items-center gap-2">
        <StatusBadge status={status} />
        <Badge
          variant={isDemo ? 'warning' : 'success'}
          className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0"
        >
          {source}
        </Badge>
      </div>

      {providerTxnId && (
        <span className="text-[11px] font-mono text-slate-500 truncate max-w-[180px]" title={providerTxnId}>
          Txn: {providerTxnId}
        </span>
      )}

      {timestamp && (
        <span className="text-[11px] text-slate-400">
          {formatDateTime(timestamp)}
        </span>
      )}
    </div>
  );
}
