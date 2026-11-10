import axios from 'axios';

const API_BASE = '/api';

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const SentinelApi = {
  getHealth: () => apiClient.get('/health').then(r => r.data),
  getDb2Status: () => apiClient.get('/db2/status').then(r => r.data),
  getDashboardSummary: () => apiClient.get('/dashboard/summary').then(r => r.data),
  getEvents: (params?: any) => apiClient.get('/events', { params }).then(r => r.data),
  getAlerts: () => apiClient.get('/alerts').then(r => r.data),
  getIncidents: () => apiClient.get('/incidents').then(r => r.data),
  getIncidentDetail: (id: string) => apiClient.get(`/incidents/${id}`).then(r => r.data),
  investigateIncident: (id: string) => apiClient.post(`/incidents/${id}/investigate`).then(r => r.data),
  getApprovals: () => apiClient.get('/approvals').then(r => r.data),
  approveAction: (id: string, reviewer = 'Security DBA', notes?: string) =>
    apiClient.post(`/approvals/${id}/approve`, { reviewer, notes }).then(r => r.data),
  rejectAction: (id: string, reviewer = 'Security DBA', notes?: string) =>
    apiClient.post(`/approvals/${id}/reject`, { reviewer, notes }).then(r => r.data),
  generateDemoEvents: () => apiClient.post('/demo/generate-events').then(r => r.data),
  runDemoDetection: () => apiClient.post('/demo/run-detection').then(r => r.data),
  resetDemo: () => apiClient.post('/demo/reset').then(r => r.data),
};
