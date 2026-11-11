'use client';

import * as React from 'react';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { StatusBadge } from '@/components/ui/status-badge';
import { Button } from '@/components/ui/button';
import { formatDate, getInitials } from '@/lib/utils';
import type { GroupMember } from '@/lib/types';

export interface MemberListProps {
  members: GroupMember[];
  currentUserId?: string;
  isAdmin?: boolean;
  onRemove?: (memberId: string, memberName: string) => void;
}

export function MemberList({
  members,
  currentUserId,
  isAdmin = false,
  onRemove,
}: MemberListProps) {
  if (members.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        No members found in this group.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden shadow-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Member</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Joined</TableHead>
            {isAdmin && onRemove && <TableHead className="text-right">Actions</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {members.map((member) => {
            const isCurrentUser = Boolean(currentUserId && member.user_id === currentUserId);
            const isMemberAdmin = member.role.toLowerCase() === 'admin';

            return (
              <TableRow key={member.group_member_id}>
                <TableCell>
                  <div className="flex items-center space-x-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
                      {getInitials(member.display_name)}
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5 font-medium text-slate-900">
                        <span>{member.display_name}</span>
                        {isCurrentUser && (
                          <Badge variant="info" className="text-[10px] px-1.5 py-0">
                            You
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="text-slate-600">
                  {member.email || '—'}
                </TableCell>
                <TableCell>
                  <Badge
                    variant={isMemberAdmin ? 'info' : 'default'}
                    className="uppercase text-[11px] font-semibold"
                  >
                    {member.role}
                  </Badge>
                </TableCell>
                <TableCell>
                  <StatusBadge status={member.status} />
                </TableCell>
                <TableCell className="text-slate-500 text-xs">
                  {formatDate(member.joined_at)}
                </TableCell>
                {isAdmin && onRemove && (
                  <TableCell className="text-right">
                    {!isCurrentUser ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-rose-600 hover:text-rose-700 hover:bg-rose-50 h-8 px-2"
                        onClick={() => onRemove(member.group_member_id, member.display_name)}
                      >
                        Remove
                      </Button>
                    ) : (
                      <span className="text-xs text-slate-400 italic">Self</span>
                    )}
                  </TableCell>
                )}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
