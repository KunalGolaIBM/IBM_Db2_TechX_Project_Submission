import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { REFRESH_INTERVAL_MS } from '../config'
import type { InvestigationStatus } from '../lib/domain'
import {
  endpoints,
  type ComplaintFilters,
  type HotspotFilters,
  type QueueFilters,
} from './endpoints'
import type {
  ComplaintCreateInput,
  DecisionInput,
  EvidenceCreateInput,
  InvestigationCreateInput,
  RecommendationDraftInput,
  RunRequestInput,
} from './schemas'

export const qk = {
  me: ['me'] as const,
  overview: ['overview'] as const,
  complaints: (f: ComplaintFilters) => ['complaints', f] as const,
  hotspots: (f: HotspotFilters) => ['hotspots', f] as const,
  investigations: (status?: InvestigationStatus) => ['investigations', status ?? 'all'] as const,
  investigation: (id: number) => ['investigation', id] as const,
  evidence: (id: number) => ['investigation', id, 'evidence'] as const,
  audit: (id: number) => ['investigation', id, 'audit'] as const,
  recsOf: (id: number) => ['investigation', id, 'recommendations'] as const,
  queue: (f: QueueFilters) => ['recommendations', f] as const,
}

// ---- reads (previous data is kept while refetching so charts never flash to a skeleton) -------------
export const useOverview = () =>
  useQuery({
    queryKey: qk.overview,
    queryFn: ({ signal }) => endpoints.overview(signal),
    refetchInterval: REFRESH_INTERVAL_MS,
    placeholderData: keepPreviousData,
  })

export const useComplaints = (filters: ComplaintFilters = {}) =>
  useQuery({
    queryKey: qk.complaints(filters),
    queryFn: ({ signal }) => endpoints.complaints(filters, signal),
    placeholderData: keepPreviousData,
  })

export const useHotspots = (filters: HotspotFilters) =>
  useQuery({
    queryKey: qk.hotspots(filters),
    queryFn: ({ signal }) => endpoints.hotspots(filters, signal),
    placeholderData: keepPreviousData,
  })

export const useInvestigations = (status?: InvestigationStatus) =>
  useQuery({
    queryKey: qk.investigations(status),
    queryFn: ({ signal }) => endpoints.investigations(status, signal),
    placeholderData: keepPreviousData,
  })

export const useInvestigation = (id: number) =>
  useQuery({
    queryKey: qk.investigation(id),
    queryFn: ({ signal }) => endpoints.investigation(id, signal),
    // an investigation that is RUNNING is polled until the server finishes
    refetchInterval: (q) => (q.state.data?.status === 'RUNNING' ? 2_000 : false),
  })

export const useEvidence = (id: number) =>
  useQuery({ queryKey: qk.evidence(id), queryFn: ({ signal }) => endpoints.evidence(id, signal) })

export const useAudit = (id: number) =>
  useQuery({ queryKey: qk.audit(id), queryFn: ({ signal }) => endpoints.audit(id, signal) })

export const useInvestigationRecommendations = (id: number) =>
  useQuery({ queryKey: qk.recsOf(id), queryFn: ({ signal }) => endpoints.investigationRecommendations(id, signal) })

export const useRecommendationQueue = (filters: QueueFilters = {}) =>
  useQuery({
    queryKey: qk.queue(filters),
    queryFn: ({ signal }) => endpoints.recommendations(filters, signal),
    placeholderData: keepPreviousData,
  })

// ---- writes (each one invalidates exactly what it can change) ----------------------------------------
function useInvalidate() {
  const client = useQueryClient()
  return (...keys: ReadonlyArray<readonly unknown[]>) =>
    Promise.all(keys.map((queryKey) => client.invalidateQueries({ queryKey })))
}

export function useCreateInvestigation() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (body: InvestigationCreateInput) => endpoints.createInvestigation(body),
    onSuccess: () => invalidate(['investigations'], qk.overview),
  })
}

export function useAttachEvidence(id: number) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (body: EvidenceCreateInput) => endpoints.attachEvidence(id, body),
    onSuccess: () => invalidate(qk.investigation(id)),
  })
}

export function useRunInvestigation(id: number) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (body: RunRequestInput) => endpoints.run(id, body),
    // a failed run still changes state (status FAILED, audit rows), so refresh on error too
    onSettled: () => invalidate(qk.investigation(id), ['investigations'], ['recommendations'], qk.overview),
  })
}

export function useProposeRecommendation(id: number) {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (body: RecommendationDraftInput) => endpoints.proposeRecommendation(id, body),
    onSuccess: () => invalidate(qk.investigation(id), ['investigations'], ['recommendations'], qk.overview),
  })
}

export function useDecideRecommendation() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: ({ id, ...body }: DecisionInput & { id: number }) => endpoints.decide(id, body),
    // also on error: a 409 means someone else changed the state, so the view must refresh
    onSettled: () => invalidate(['recommendations'], ['investigation'], ['investigations'], qk.overview),
  })
}

export function useCreateComplaint() {
  const invalidate = useInvalidate()
  return useMutation({
    mutationFn: (body: ComplaintCreateInput) => endpoints.createComplaint(body),
    onSuccess: () => invalidate(['complaints'], ['hotspots'], qk.overview),
  })
}
