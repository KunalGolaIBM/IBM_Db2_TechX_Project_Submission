import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
export const useDashboard = () => useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard, refetchInterval: 15_000 });
export const useIncidents = () => useQuery({ queryKey: ["incidents"], queryFn: api.incidents });
export const useIncident = (id?: string) => useQuery({ queryKey: ["incident", id], queryFn: () => api.incident(id!), enabled: !!id });
export const useInvestigation = (id?: string, live = false) =>
  useQuery({
    queryKey: ["investigation", id],
    queryFn: () => api.investigation(id!),
    enabled: !!id,
    retry: false,
    refetchInterval: (q) => (live || (q.state.data && q.state.data.status !== "COMPLETED" && q.state.data.status !== "FAILED") ? 800 : false),
  });
export const useTrace = (ref?: string) => useQuery({ queryKey: ["trace", ref], queryFn: () => api.trace(ref!), enabled: !!ref, retry: false });
export const useImpact = (ref?: string) => useQuery({ queryKey: ["impact", ref], queryFn: () => api.impact(ref!), enabled: !!ref, retry: false });
export const useCatalog = () => useQuery({ queryKey: ["catalog"], queryFn: api.catalog, staleTime: 60_000 });
export const useRecalls = () => useQuery({ queryKey: ["recalls"], queryFn: api.recalls });
export const useRecall = (id?: string) => useQuery({ queryKey: ["recall", id], queryFn: () => api.recall(id!), enabled: !!id });
export const useEvidence = (incidentId?: string) => useQuery({ queryKey: ["evidence", incidentId ?? "all"], queryFn: () => api.evidence(incidentId) });
export const useAudit = (ref?: string) => useQuery({ queryKey: ["audit", ref ?? "all"], queryFn: () => api.auditLogs(ref) });

/** Invalidate everything that a workflow step can change. */
export function useRefreshAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries();
}

export function useRecallDecision(recallId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kind, comment }: { kind: "approve" | "reject"; comment: string }) =>
      kind === "approve" ? api.approve(recallId, comment) : api.reject(recallId, comment),
    onSuccess: (data) => {
      qc.setQueryData(["recall", recallId], data);
      qc.invalidateQueries();
    },
  });
}
