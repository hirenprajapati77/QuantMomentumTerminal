// API Client for backend services

const BASE_URL = (import.meta.env.VITE_API_URL as string) ?? '/api/v1';

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
      const errData = await res.json().catch(() => ({ detail: 'API request failed' }));
      const error: any = new Error(errData.detail || 'API request failed');
      error.status = res.status;
      error.detail = errData.detail;
      throw error;
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
      const errData = await res.json().catch(() => ({ detail: 'API request failed' }));
      const error: any = new Error(errData.detail || 'API request failed');
      error.status = res.status;
      error.detail = errData.detail;
      throw error;
    }
    return res.json();
  }
};
