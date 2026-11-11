'use client';

import { useFetch } from './use-api';
import type { Group, GroupSummary } from '@/lib/types';

export function useGroups() {
  return useFetch<Group[]>('/api/v1/groups');
}

export function useGroup(groupId: string | null) {
  return useFetch<Group>(groupId ? `/api/v1/groups/${groupId}` : null);
}

export function useGroupSummary(groupId: string | null) {
  return useFetch<GroupSummary>(groupId ? `/api/v1/groups/${groupId}/summary` : null);
}
