'use client';

import * as React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatPaise, formatDate } from '@/lib/utils';
import { api, ApiError } from '@/lib/api-client';
import type { PendingApprovalItem } from '@/lib/types';

export interface ApprovalCardProps {
  item: PendingApprovalItem;
  groupId: string;
  currentUserId?: string;
  myMemberId?: string;
  onDecided?: () => void;
}

export function ApprovalCard({
  item,
  groupId,
  currentUserId,
  myMemberId,
  onDecided,
}: ApprovalCardProps) {
  const [comment, setComment] = React.useState<string>('');
  const [isDeciding, setIsDeciding] = React.useState<boolean>(false);
  const [error, setError] = React.useState<string | null>(null);

  // Self-approval restriction rule
  const isSelfSubmission = Boolean(
    (currentUserId && item.submitter_user_id && item.submitter_user_id === currentUserId) ||
    (myMemberId && item.submitter_member_id && item.submitter_member_id === myMemberId)
  );

  const approvalId = item.approval_id || item.entity_id;

  const handleDecision = async (decision: 'APPROVED' | 'REJECTED') => {
    if (isSelfSubmission) return;

    setIsDeciding(true);
    setError(null);

    try {
      await api.post(`/api/v1/groups/${groupId}/approvals/${approvalId}/decide`, {
        decision,
        comment: comment.trim() || undefined,
      });

      if (onDecided) {
        onDecided();
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || 'Failed to submit approval decision');
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setIsDeciding(false);
    }
  };

  const isCashExpense = item.entity_type?.toUpperCase().includes('EXPENSE');

  return (
    <Card className="border-slate-200 overflow-hidden shadow-sm">
      <CardContent className="p-5 space-y-4">
        {/* Top Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div
              className={`p-2.5 rounded-lg shrink-0 ${
                isCashExpense ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'
              }`}
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant={isCashExpense ? 'warning' : 'success'} className="uppercase text-[10px] font-bold">
                  {isCashExpense ? 'Cash Expense' : 'Cash Contribution'}
                </Badge>
                <span className="text-xs text-slate-500">
                  Submitted {formatDate(item.created_at)}
                </span>
              </div>
              <h4 className="text-base font-bold text-slate-900 mt-1">
                {item.description || (isCashExpense ? 'Cash expense verification' : 'Physical cash contribution')}
              </h4>
              <p className="text-xs text-slate-600 mt-0.5">
                Submitted by: <strong className="font-semibold text-slate-800">{item.submitter_name}</strong>
              </p>
            </div>
          </div>

          <div className="text-right shrink-0">
            <span className="text-lg font-bold text-slate-900">
              {formatPaise(item.amount_minor)}
            </span>
          </div>
        </div>

        {/* Self-approval Notice */}
        {isSelfSubmission && (
          <div className="rounded-md bg-amber-50 p-2.5 text-xs font-medium text-amber-800 border border-amber-200 flex items-center gap-2">
            <svg className="w-4 h-4 text-amber-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>You cannot approve your own submission. Another group member must review this.</span>
          </div>
        )}

        {/* Decision Error Message */}
        {error && (
          <div className="rounded-md bg-rose-50 p-2.5 text-xs font-medium text-rose-700 border border-rose-200">
            {error}
          </div>
        )}

        {/* Comment and Decision Controls */}
        <div className="pt-2 border-t border-slate-100 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <input
            type="text"
            placeholder="Add optional note or comment..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            disabled={isSelfSubmission || isDeciding}
            className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:bg-slate-100 disabled:text-slate-400"
          />

          <div className="flex items-center gap-2 justify-end shrink-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={isSelfSubmission || isDeciding}
              isLoading={isDeciding}
              onClick={() => handleDecision('REJECTED')}
              className="border-rose-300 text-rose-700 hover:bg-rose-50"
            >
              Reject
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={isSelfSubmission || isDeciding}
              isLoading={isDeciding}
              onClick={() => handleDecision('APPROVED')}
              className="bg-emerald-600 hover:bg-emerald-700 focus:ring-emerald-500"
            >
              Approve
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
