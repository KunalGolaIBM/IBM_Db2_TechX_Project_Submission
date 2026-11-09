import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('claimguard_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: attach system headers
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    const customError = {
      message: error.response?.data?.detail || error.message || 'An unexpected error occurred',
      status: error.response?.status,
      data: error.response?.data,
    };
    return Promise.reject(customError);
  }
);

export const apiClient = {
  // System Health
  getHealth: () => api.get('/health'),
  getDbHealth: () => api.get('/db/health'),

  // Authentication
  login: (username, password) => api.post('/auth/login', { username, password }),
  getProfile: () => api.get('/auth/me'),

  // Dashboard
  getDashboardStats: () => api.get('/dashboard/stats'),

  // Claims
  getClaims: (status) => api.get('/claims', { params: status ? { status } : {} }),
  getClaim: (id) => api.get(`/claims/${id}`),
  submitClaim: (data) => api.post('/claims', data),
  submitDecision: (id, decision) => api.put(`/claims/${id}/decision`, decision),
  uploadDocument: (claimId, file, documentType = 'MEDICAL_BILL') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);
    return api.post(`/claims/${claimId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // Verification & AI Agents
  triggerVerification: (claimId) => api.post(`/verification/${claimId}`),
  getVerificationStatus: (claimId) => api.get(`/verification/${claimId}`),
  getReport: (claimId) => api.get(`/reports/${claimId}`),

  // Fraud Alerts & Audit Logs
  getFraudAlerts: (resolved) => api.get('/fraud/alerts', { params: resolved !== undefined ? { resolved } : {} }),
  resolveAlert: (alertId, resolution_notes) => api.post(`/fraud/alerts/${alertId}/resolve`, { resolution_notes }),
  getAuditLogs: (limit = 50) => api.get('/audit-logs', { params: { limit } }),

  // Policies & Customers
  getPolicies: () => api.get('/policies'),
  getPolicy: (id) => api.get(`/policies/${id}`),
  getCustomers: () => api.get('/customers'),
  getCustomer: (id) => api.get(`/customers/${id}`),
};

export default api;
