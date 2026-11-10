const API_BASE = '/api';

export async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  const response = await fetch(url, {
    ...options,
    headers
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Network request failed' }));
    throw new Error(errorData.detail || `HTTP Error ${response.status}`);
  }

  return response.json();
}

export const SentinelApi = {
  // Dashboard & System Status
  getDashboardStats: () => apiRequest('/dashboard/stats'),
  getHealth: () => apiRequest('/health'),

  // Monitoring
  getUsers: () => apiRequest('/monitoring/users'),
  getLogins: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiRequest(`/monitoring/logins${query ? `?${query}` : ''}`);
  },
  getAccessLogs: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiRequest(`/monitoring/access-logs${query ? `?${query}` : ''}`);
  },
  getAlerts: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiRequest(`/monitoring/alerts${query ? `?${query}` : ''}`);
  },

  // Incidents & Agentic AI
  getIncidents: () => apiRequest('/incidents'),
  getIncidentDetails: (incidentId) => apiRequest(`/incidents/${incidentId}`),
  investigateAccount: (userId, lookbackHours = 24) => 
    apiRequest('/incidents/investigate', {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, lookback_hours: lookbackHours })
    }),
  simulateAttack: (targetUserId = 'USR-101') => 
    apiRequest('/incidents/simulate-attack', {
      method: 'POST',
      body: JSON.stringify({ target_user_id: targetUserId })
    }),
  getIncidentReport: (incidentId) => apiRequest(`/incidents/${incidentId}/report`),

  // Response Management & Human Approval
  getRecommendations: (status = null) => {
    const query = status ? `?status=${encodeURIComponent(status)}` : '';
    return apiRequest(`/responses/recommendations${query}`);
  },
  actOnRecommendation: (recId, action, adminName = 'Cyber Commander Administrator', notes = '') => 
    apiRequest(`/responses/${recId}/action`, {
      method: 'POST',
      body: JSON.stringify({ action, admin_name: adminName, notes })
    }),

  // Auth
  login: (username, password) => 
    apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    })
};

