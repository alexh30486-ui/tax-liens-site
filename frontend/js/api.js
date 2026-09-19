/**
 * Shared API client.
 * Behind nginx, set: window.TLF_API_BASE = ''  (same origin)
 * Dev default talks to Gunicorn/Uvicorn on :8000
 */
const API_BASE = (typeof window !== 'undefined' && window.TLF_API_BASE !== undefined)
  ? window.TLF_API_BASE
  : 'http://localhost:8000';

const TOKEN_KEY = 'tlf_access_token';

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function api(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!res.ok) {
    const detail = data && data.detail;
    const msg = typeof detail === 'string' ? detail : (detail ? JSON.stringify(detail) : `Request failed (${res.status})`);
    const err = new Error(msg);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

async function signup(email, password) {
  const data = await api('/api/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  return data;
}

async function login(email, password) {
  const data = await api('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  return data;
}

async function me() {
  return api('/api/auth/me');
}

async function fetchListings({ minRatio = 0, state = '', county = '', limit = 50 } = {}) {
  const params = new URLSearchParams();
  params.set('min_ratio', String(minRatio));
  params.set('limit', String(limit));
  if (state) params.set('state', state);
  if (county) params.set('county', county);
  return api(`/api/listings?${params.toString()}`);
}

async function searchListings({ q = '', minRatio = 0, state = '', county = '', limit = 50 } = {}) {
  const params = new URLSearchParams();
  params.set('q', q);
  params.set('min_ratio', String(minRatio));
  params.set('limit', String(limit));
  if (state) params.set('state', state);
  if (county) params.set('county', county);
  return api(`/api/search?${params.toString()}`);
}

async function enrichListing(lienId) {
  return api(`/api/listings/${encodeURIComponent(lienId)}/enrich`, { method: 'POST' });
}

export {
  API_BASE,
  getToken,
  setToken,
  clearToken,
  api,
  signup,
  login,
  me,
  fetchListings,
  searchListings,
  enrichListing,
};
