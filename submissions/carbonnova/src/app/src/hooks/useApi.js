/**
 * CarbonNova — react-query hooks wrapping the API client.
 * Handles loading, error, refetch and cache invalidation conventions in one
 * place so every page can render proper loading / error / empty states.
 */
import {
  useQuery, useMutation, useQueryClient,
} from '@tanstack/react-query';
import api from '../lib/api';

// --- meta -------------------------------------------------------------------
export const useHealth = (opts) =>
  useQuery({ queryKey: ['health'], queryFn: () => api.health(), refetchInterval: 30000, ...opts });

export const useAiStatus = (opts) =>
  useQuery({ queryKey: ['ai-status'], queryFn: ({ signal }) => api.aiStatus(signal), staleTime: 60000, ...opts });

export const useActivity = (limit = 50, opts) =>
  useQuery({ queryKey: ['activity', limit], queryFn: () => api.activity(limit), refetchInterval: 20000, ...opts });

// --- projects ---------------------------------------------------------------
export const useProjects = (owner, opts) =>
  useQuery({
    queryKey: ['projects', owner || 'all'],
    queryFn: () => api.listProjects(owner),
    refetchInterval: 30000,
    ...opts,
  });

export const useProject = (id, opts) =>
  useQuery({
    queryKey: ['project', id],
    queryFn: () => api.getProject(id),
    enabled: Boolean(id),
    ...opts,
  });

export const useCreateProject = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.createProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  });
};

export const useUpdateProject = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }) => api.updateProject(id, payload),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ['projects'] });
      qc.invalidateQueries({ queryKey: ['project', vars.id] });
    },
  });
};

export const useDeleteProject = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id) => api.deleteProject(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['projects'] });
      qc.invalidateQueries({ queryKey: ['devices'] });
    },
  });
};

// --- monitoring -------------------------------------------------------------
export const useReadings = (projectId, { range = '24h', metric, enabled = true } = {}) =>
  useQuery({
    queryKey: ['readings', projectId, range, metric || 'all'],
    queryFn: ({ signal }) => api.getReadings(projectId, { range, metric }, signal),
    enabled: Boolean(projectId) && enabled,
    refetchInterval: 60000, // keep demo dashboards fresh
    staleTime: 15000,
  });

export const useDevices = (opts) =>
  useQuery({
    queryKey: ['devices'],
    queryFn: () => api.listDevices(),
    refetchInterval: 60000,
    ...opts,
  });

// --- carbon engine ----------------------------------------------------------
export const useCarbon = (projectId, range = '7d', enabled = true) =>
  useQuery({
    queryKey: ['carbon', projectId, range],
    queryFn: () => api.getCarbon(projectId, range),
    enabled: Boolean(projectId) && enabled,
    staleTime: 60000,
  });

// --- AI ---------------------------------------------------------------------
export const useAiAsk = () =>
  useMutation({
    mutationFn: ({ projectId, question, history }) => api.aiAsk(projectId, question, history),
    retry: false, // surface errors immediately; user clicks Retry
  });

export const useNvidiaAsk = () =>
  useMutation({
    mutationFn: ({ projectId, question, history }) => api.nvidiaAsk(projectId, question, history),
    retry: false, // surface errors immediately; user clicks Retry
  });

export const useAiPreset = () =>
  useMutation({
    mutationFn: ({ projectId, preset, history }) => api.aiPreset(projectId, preset, history),
    retry: false,
  });

// --- reports ----------------------------------------------------------------
export const useReports = (projectId, enabled = true) =>
  useQuery({
    queryKey: ['reports', projectId],
    queryFn: () => api.listReports(projectId),
    enabled: Boolean(projectId) && enabled,
  });

export const useDownloadPdf = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, includeAiSummary, range }) => api.downloadPdf(projectId, { includeAiSummary, range }),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['reports', vars.projectId] }),
  });
};

export const useDownloadCsv = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, kind, range }) => api.downloadCsv(projectId, kind, range),
    onSuccess: (_d, vars) => qc.invalidateQueries({ queryKey: ['reports', vars.projectId] }),
  });
};
