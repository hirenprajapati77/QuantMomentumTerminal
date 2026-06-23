// API Client for backend services

const BASE_URL = window.location.port === '5173' || window.location.hostname === 'localhost' && window.location.port === '3000'
  ? 'http://localhost:8000/api/v1'
  : '/api/v1';

export const apiClient = {
  async get(endpoint: string) {
    const res = await fetch(`${BASE_URL}${endpoint}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'API request failed' }));
      throw new Error(err.detail || 'API request failed');
    }
    return res.json();
  },

  async post(endpoint: string, body: any) {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'API request failed' }));
      throw new Error(err.detail || 'API request failed');
    }
    return res.json();
  }
};
