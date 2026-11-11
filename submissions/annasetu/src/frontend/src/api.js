const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8010/api';

export function token() {
  return localStorage.getItem('annasetu_token');
}

export async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token()) headers.Authorization = `Bearer ${token()}`;
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch {
    throw new Error('Cannot reach the AnnaSetu API. Check that FastAPI and IBM Db2 are running.');
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail || body.message || `Request failed (${response.status})`;
    const issue = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    issue.status = response.status;
    throw issue;
  }
  return body;
}

export function post(path, data) {
  return api(path, { method: 'POST', body: JSON.stringify(data) });
}

export function patch(path, data) {
  return api(path, { method: 'PATCH', body: JSON.stringify(data) });
}
