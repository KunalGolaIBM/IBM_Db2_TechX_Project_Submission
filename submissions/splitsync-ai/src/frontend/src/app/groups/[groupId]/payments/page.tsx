'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useFetch } from '@/hooks/use-api';
import { AppShell } from '@/components/layout/app-shell';
import { QRDisplay } from '@/components/payments/qr-display';
import { PaymentStatus } from '@/components/payments/payment-status';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Spinner } from '@/components/ui/spinner';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { formatPaise } from '@/lib/utils';
import type { Group, PaymentEvent } from '@/lib/types';

export default function GroupPaymentsPage() {
  const params = useParams();
  const groupId = typeof params?.groupId === 'string' ? params.groupId : '';

  const { data: group } = useFetch<Group>(groupId ? `/api/v1/groups/${groupId}` : null);
  const {
    data: payments,
    error: paymentsError,
    isLoading: isPaymentsLoading,
    refetch: refetchPayments,
  } = useFetch<PaymentEvent[]>(groupId ? `/api/v1/groups/${groupId}/payments` : null);

  return (
    <AppShell title={group ? `${group.name} - Payments` : 'Group Payments'}>
      <div className="space-y-8">
        {/* Breadcrumb Navigation */}
        <div className="flex items-center space-x-2 text-sm text-slate-500">
          <Link href="/groups" className="hover:text-slate-800 transition-colors">
            Groups
          </Link>
          <span>/</span>
          <Link
            href={`/groups/${groupId}`}
            className="hover:text-slate-800 transition-colors font-medium text-slate-700"
          >
            {group?.name || 'Group'}
          </Link>
          <span>/</span>
          <span className="text-slate-900 font-semibold">Payments</span>
        </div>

        {/* Section 1: QR & Payment Simulation */}
        <div>
          <QRDisplay groupId={groupId} onPaymentSuccess={() => refetchPayments()} />
        </div>

        {/* Section 2: Payment Events History */}
        <Card className="border-slate-200">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg font-bold text-slate-900">
                Payment History
              </CardTitle>
              <p className="text-xs text-slate-500 mt-1">
                Verified digital payment credits recorded to the group pool
              </p>
            </div>
            <button
              onClick={() => refetchPayments()}
              className="text-xs font-semibold text-primary-600 hover:text-primary-700 transition-colors flex items-center gap-1"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
          </CardHeader>

          <CardContent className="p-0">
            {isPaymentsLoading ? (
              <div className="flex h-48 items-center justify-center">
                <Spinner size="lg" />
              </div>
            ) : paymentsError ? (
              <div className="p-6">
                <ErrorState
                  title="Failed to load payments"
                  message={paymentsError.message}
                  onRetry={() => refetchPayments()}
                />
              </div>
            ) : !payments || payments.length === 0 ? (
              <div className="p-8">
                <EmptyState
                  title="No payments recorded yet"
                  description="Scan the QR code above or use the demo payment simulator to make your first contribution."
                />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Amount</TableHead>
                    <TableHead>Payer</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Status & Source</TableHead>
                    <TableHead>Payment Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {payments.map((payment) => (
                    <TableRow key={payment.payment_id}>
                      <TableCell className="font-bold text-slate-900 text-base">
                        {formatPaise(payment.amount_minor)}
                      </TableCell>
                      <TableCell>
                        <span className="font-medium text-slate-800">
                          {payment.member_name || payment.member_id || 'Group Member'}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-800 uppercase">
                          {payment.provider}
                        </span>
                      </TableCell>
                      <TableCell>
                        <PaymentStatus
                          status={payment.status}
                          providerTxnId={payment.provider_txn_id}
                          source={payment.source}
                        />
                      </TableCell>
                      <TableCell className="text-xs text-slate-500">
                        {payment.paid_at || payment.created_at}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
