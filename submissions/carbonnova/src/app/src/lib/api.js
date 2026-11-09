/**
 * CarbonNova frontend API client
 * ------------------------------
 * Talks to the Express backend (VITE_API_URL or http://localhost:4000/api).
 * All errors are normalized to ApiError { status, code, message, details,
 * retryable } so the UI can show clear, retryable failures instead of
 * swallowing them. AI answers ALWAYS come from this backend — the frontend
 * never fakes AI output and never touches NEBIUS_API_KEY.
 */
const BASE = (import.meta.env.VITE_API_URL || 'http://localhost:4000/api').replace(/\/$/, '');

export class ApiError extends Error {
  constructor({ status, code, message, details, retryable }) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code || 'UNKNOWN';
    this.details = details || null;
    this.retryable = Boolean(retryable) || status >= 500;
  }
}

async function parseError(res) {
  let body = null;
  try { body = await res.json(); } catch { /* non-JSON error body */ }
  return new ApiError({
    status: res.status,
    code: body?.error || `HTTP_${res.status}`,
    message: body?.message || body?.details?.join?.('; ') || `Request failed (${res.status})`,
    details: body?.details || null,
    retryable: body?.retryable ?? res.status >= 500,
  });
}

async function request(path, { method = 'GET', body, signal } = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: body !== undefined ? { 'content-type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError({
      status: 0,
      code: 'NETWORK_ERROR',
      message: 'Cannot reach the CarbonNova backend. Is the server running on port 4000? (npm run dev:server)',
      retryable: true,
    });
  }
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return null;
  return res.json();
}

async function download(path, { method = 'GET', body, filename } = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      method,
      headers: body !== undefined ? { 'content-type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'Cannot reach the backend to download the report.', retryable: true });
  }
  if (!res.ok) throw await parseError(res);

  const disposition = res.headers.get('content-disposition') || '';
  const match = disposition.match(/filename="?([^"]+)"?/);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || match?.[1] || 'carbonnova-download';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
  return { filename: a.download, size: blob.size, reportId: res.headers.get('x-report-id') };
}

// --- AI assistant endpoints --------------------------------------------------
// Both providers serve NVIDIA Nemotron models, but through different backend
// routes, so each provider keeps its own client function:
//   aiAsk / aiPreset        -> Nebius Token Factory  (/ai/ask, /ai/preset)
//   nvidiaAsk / nvidiaPreset -> NVIDIA Build API    (/ai/nvidia/ask, ...)
// The API keys never leave the backend; these helpers only do the POST.

export const aiAsk = (projectId, question, history = []) =>
  request(`/projects/${projectId}/ai/ask`, { method: 'POST', body: { question, history } });

export const aiPreset = (projectId, preset, history = []) =>
  request(`/projects/${projectId}/ai/preset`, { method: 'POST', body: { preset, history } });

export const nvidiaAsk = (projectId, question, history = []) =>
  request(`/projects/${projectId}/ai/nvidia/ask`, { method: 'POST', body: { question, history } });

export const nvidiaPreset = (projectId, preset, history = []) =>
  request(`/projects/${projectId}/ai/nvidia/preset`, { method: 'POST', body: { preset, history } });

export const api = {
  // --- meta ---
  health: () => request('/health'),
  aiStatus: (signal) => request('/ai/status', { signal }),
  activity: (limit = 50) => request(`/activity?limit=${limit}`),

  // --- projects & saved parcel boundaries ---
  listProjects: (owner) => request(`/projects${owner ? `?owner=${encodeURIComponent(owner)}` : ''}`),
  listParcels: (ownerId = 'user-1') => request(`/parcels?owner_id=${encodeURIComponent(ownerId)}`),
  createParcel: (payload) => request('/parcels', { method: 'POST', body: payload }),
  updateParcel: (id, payload) => request(`/parcels/${encodeURIComponent(id)}`, { method: 'PATCH', body: payload }),
  deleteParcel: (id, ownerId = 'user-1') => request(`/parcels/${encodeURIComponent(id)}?owner_id=${encodeURIComponent(ownerId)}`, { method: 'DELETE' }),
  getProject: (id) => request(`/projects/${id}`),
  createProject: (payload) => request('/projects', { method: 'POST', body: payload }),
  updateProject: (id, payload) => request(`/projects/${id}`, { method: 'PATCH', body: payload }),
  deleteProject: (id) => request(`/projects/${id}`, { method: 'DELETE' }),

  // --- monitoring ---
  getReadings: (projectId, { range = '24h', metric, limit } = {}, signal) =>
    request(`/projects/${projectId}/readings?range=${range}${metric ? `&metric=${metric}` : ''}${limit ? `&limit=${limit}` : ''}`, { signal }),
  listDevices: () => request('/devices'),
  projectDevices: (projectId) => request(`/projects/${projectId}/devices`),

  // --- carbon engine (science, not AI) ---
  getCarbon: (projectId, range = '7d') => request(`/projects/${projectId}/carbon?range=${range}`),
  listAssessments: (projectId) => request(`/projects/${encodeURIComponent(projectId)}/assessments`),
  createAssessment: (projectId) => request(`/projects/${encodeURIComponent(projectId)}/assessments`, { method: 'POST', body: {} }),

  // --- AI assistant (Nebius via backend) ---
  aiAsk,
  aiPreset,

  // --- AI assistant (NVIDIA Build / Nemotron via backend) ---
  nvidiaAsk,
  nvidiaPreset,

  // --- reports ---
  listReports: (projectId) => request(`/projects/${projectId}/reports`),
  downloadPdf: (projectId, { includeAiSummary = false, range } = {}) =>
    download(`/projects/${projectId}/reports/pdf?range=${range || '30d'}`, {
      method: 'POST', body: { include_ai_summary: includeAiSummary },
    }),
  downloadCsv: (projectId, kind = 'readings', range) =>
    download(`/projects/${projectId}/reports/csv?range=${range || '30d'}`, {
      method: 'POST', body: { kind },
    }),

  // --- platform / marketplace / governance (demo) ---
  platformOverview: (actor={}) => request(`/platform/overview?actor_role=${encodeURIComponent(actor.actor_role||'admin')}&actor_id=${encodeURIComponent(actor.actor_id||'')}`),
  platformUsers: (actor={}) => request(`/platform/users?actor_role=${encodeURIComponent(actor.actor_role||'admin')}&actor_id=${encodeURIComponent(actor.actor_id||'')}`),
  platformAudit: (actor={}) => request(`/platform/audit?actor_role=${encodeURIComponent(actor.actor_role||'admin')}&actor_id=${encodeURIComponent(actor.actor_id||'')}`),
  setUserStatus: (id, payload) => request(`/platform/users/${encodeURIComponent(id)}/status`, { method:'PATCH', body: payload }),
  listLandRegistrations: (actor={}) => request(`/land-registrations?actor_role=${encodeURIComponent(actor.actor_role||'seller')}&actor_id=${encodeURIComponent(actor.actor_id||'')}`),
  adminLandRegistrations: (actor={}) => request(`/admin/land-registrations?actor_role=${encodeURIComponent(actor.actor_role||'admin')}&actor_id=${encodeURIComponent(actor.actor_id||'')}`),
  createLandRegistration: (payload) => request('/land-registrations', { method:'POST', body: payload }),
  listCarbonProjects: (actor={}) => request(`/carbon-projects?actor_role=${encodeURIComponent(actor.actor_role||'seller')}&actor_id=${encodeURIComponent(actor.actor_id||'')}`),
  createCarbonProject: (payload) => request('/carbon-projects', { method:'POST', body: payload }),
  reviewCarbonProject: (id, payload) => request(`/carbon-projects/${encodeURIComponent(id)}/review`, { method:'PATCH', body: payload }),
  listMarketplaceListings: (params={}) => {
    const q = new URLSearchParams(); Object.entries(params).forEach(([k,v])=>{ if(v!=null && v!=='') q.set(k,v); });
    return request(`/marketplace/listings?${q.toString()}`);
  },
  createMarketplaceListing: (payload) => request('/marketplace/listings', { method:'POST', body: payload }),
  reviewMarketplaceListing: (id, payload) => request(`/marketplace/listings/${encodeURIComponent(id)}/review`, { method:'PATCH', body: payload }),
  purchaseCredits: (payload) => request('/marketplace/purchase', { method:'POST', body: payload }),
  listTransactions: (actor={}) => request(`/marketplace/transactions?actor_role=${encodeURIComponent(actor.actor_role||'buyer')}&actor_id=${encodeURIComponent(actor.actor_id||'')}`),
  listBalances: (actor={}) => request(`/marketplace/balances?actor_role=${encodeURIComponent(actor.actor_role||'seller')}&actor_id=${encodeURIComponent(actor.actor_id||'')}`),
  listProjectDocuments: (carbonProjectId) => request(`/marketplace/documents?carbon_project_id=${encodeURIComponent(carbonProjectId||'')}`),
  reviewProjectDocuments: (payload) => request('/marketplace/documents/review', { method:'POST', body: payload }),
};

export default api;
