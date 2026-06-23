// API Client for backend services

const BASE_URL = window.location.port === '5173' || window.location.hostname === 'localhost' && window.location.port === '3000'
  ? 'http://localhost:8000/api/v1'
  : '/api/v1';

let sessionToken: string | null = null;

export const apiClient = {
  setToken(token: string | null) {
    sessionToken = token;
  },

  async get(endpoint: string, customHeaders: any = {}) {
    const headers: any = { ...customHeaders };
    if (sessionToken) {
      headers['Authorization'] = `Bearer ${sessionToken}`;
    }
    const res = await fetch(`${BASE_URL}${endpoint}`, {
      headers
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'API request failed' }));
      throw new Error(err.detail || 'API request failed');
    }
    return res.json();
  },

  async post(endpoint: string, body: any, customHeaders: any = {}) {
    const headers: any = {
      'Content-Type': 'application/json',
      ...customHeaders
    };
    if (sessionToken) {
      headers['Authorization'] = `Bearer ${sessionToken}`;
    }
    const res = await fetch(`${BASE_URL}${endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'API request failed' }));
      throw new Error(err.detail || 'API request failed');
    }
    return res.json();
  }
};
