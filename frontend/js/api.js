/**
 * api.js — Fetch wrapper, endpoint definitions, and error handling
 */

import Storage from './storage.js';

// ===== CONFIG =====
// In a real environment, these would come from environment variables
const BASE_URL = window.TW_API_BASE_URL || 'http://localhost:5000/api';

// ===== CORE FETCH WRAPPER =====
async function apiCall(method, endpoint, data = null, opts = {}) {
  const token = Storage.getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...opts.headers,
  };

  // For FormData, don't set Content-Type (let browser set it with boundary)
  if (data instanceof FormData) {
    delete headers['Content-Type'];
  }

  const options = {
    method,
    headers,
    body: data
      ? data instanceof FormData
        ? data
        : JSON.stringify(data)
      : undefined,
  };

  try {
    const response = await fetch(`${BASE_URL}${endpoint}`, options);

    // Handle 401 — try refresh then retry once
    if (response.status === 401 && !opts._retried) {
      const refreshed = await tryRefreshToken();
      if (refreshed) {
        return apiCall(method, endpoint, data, { ...opts, _retried: true });
      } else {
        Storage.clearAll();
        window.location.href = '/frontend/pages/login.html';
        return;
      }
    }

    // Handle 403
    if (response.status === 403) {
      showToast('Access denied. You do not have permission.', 'error');
      throw new APIError('Access denied', 403);
    }

    // Handle 500
    if (response.status >= 500) {
      showToast('Server error. Please try again later.', 'error');
      throw new APIError('Server error', response.status);
    }

    let json;
    try {
      json = await response.json();
    } catch {
      json = {};
    }

    if (!response.ok) {
      const message = json.message || json.error || response.statusText;
      throw new APIError(message, response.status, json);
    }

    return json;
  } catch (err) {
    if (err instanceof APIError) throw err;
    if (err.name === 'TypeError') {
      // Network error
      throw new APIError('Network error. Check your connection and try again.', 0);
    }
    throw err;
  }
}

// ===== API ERROR CLASS =====
export class APIError extends Error {
  constructor(message, status, data = null) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.data = data;
  }
}

// ===== TOKEN REFRESH =====
async function tryRefreshToken() {
  const refreshToken = Storage.getRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch(`${BASE_URL}/auth/refresh-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) return false;

    const json = await response.json();
    if (json.access_token) {
      Storage.setToken(json.access_token);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

// ===== TOAST HELPER (lazy reference to avoid circular deps) =====
function showToast(message, type = 'info') {
  if (window.Toast) window.Toast.show(message, type);
}

// ===== HTTP SHORTCUTS =====
export const api = {
  get: (endpoint, opts) => apiCall('GET', endpoint, null, opts || {}),
  post: (endpoint, data, opts) => apiCall('POST', endpoint, data, opts || {}),
  put: (endpoint, data, opts) => apiCall('PUT', endpoint, data, opts || {}),
  patch: (endpoint, data, opts) => apiCall('PATCH', endpoint, data, opts || {}),
  delete: (endpoint, opts) => apiCall('DELETE', endpoint, null, opts || {}),
};

// ===== ENDPOINTS =====

// Auth
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  logout: () => api.post('/auth/logout'),
  refreshToken: (refreshToken) => api.post('/auth/refresh-token', { refresh_token: refreshToken }),
  setup2FA: (data) => api.post('/auth/2fa-setup', data),
  verify2FA: (data) => api.post('/auth/2fa-verify', data),
  disable2FA: (data) => api.post('/auth/2fa-disable', data),
  changePassword: (data) => api.post('/pro-trader/change-password', data),
};

// Pro Trader Profile
export const profileAPI = {
  getProfile: () => api.get('/pro-trader/profile'),
  updateProfile: (data) => api.put('/pro-trader/profile', data),
  getDashboard: () => api.get('/pro-trader/dashboard'),
};

// Trades
export const tradesAPI = {
  list: (params = '') => api.get(`/pro-trader/trades${params}`),
  create: (data) => api.post('/pro-trader/trades', data),
  get: (id) => api.get(`/pro-trader/trades/${id}`),
  close: (id, data) => api.put(`/pro-trader/trades/${id}/close`, data),
  getComments: (id) => api.get(`/pro-trader/trades/${id}/comments`),
  addComment: (id, data) => api.post(`/pro-trader/trades/${id}/comments`, data),
  updateComment: (tradeId, commentId, data) =>
    api.put(`/pro-trader/trades/${tradeId}/comments/${commentId}`, data),
  deleteComment: (tradeId, commentId) =>
    api.delete(`/pro-trader/trades/${tradeId}/comments/${commentId}`),
};

// Analytics
export const analyticsAPI = {
  getAccuracy: () => api.get('/pro-trader/analytics/accuracy'),
  getPerformanceChart: () => api.get('/pro-trader/analytics/performance-chart'),
  getWinLoss: () => api.get('/pro-trader/analytics/win-loss'),
  getRRR: () => api.get('/pro-trader/analytics/rrr'),
  getMonthlyStats: () => api.get('/pro-trader/analytics/monthly-stats'),
};

// Earnings & Payouts
export const earningsAPI = {
  getEarnings: () => api.get('/pro-trader/earnings'),
  getBalance: () => api.get('/pro-trader/balance'),
  getPayouts: () => api.get('/pro-trader/payouts'),
  initiatePayout: (data) => api.post('/pro-trader/payouts/initiate', data),
  updateSubscriptionPrice: (data) => api.put('/pro-trader/subscription-price', data),
};

// Subscribers
export const subscribersAPI = {
  getSubscribers: () => api.get('/pro-trader/subscribers'),
};

// KYC
export const kycAPI = {
  getStatus: () => api.get('/pro-trader/kyc/status'),
  uploadDocuments: (formData) => api.post('/pro-trader/kyc/upload-documents', formData),
  submitReview: () => api.post('/pro-trader/kyc/submit-review'),
  updateBankDetails: (data) => api.put('/pro-trader/bank-details', data),
};

// Notifications
export const notificationsAPI = {
  getAll: () => api.get('/pro-trader/notifications'),
  markRead: (id) => api.put(`/pro-trader/notifications/${id}/read`),
  delete: (id) => api.delete(`/pro-trader/notifications/${id}`),
  clearAll: () => api.post('/pro-trader/notifications/clear-all'),
  getPreferences: () => api.get('/pro-trader/notification-preferences'),
  updatePreferences: (data) => api.put('/pro-trader/notification-preferences', data),
};

// Account Settings
export const accountAPI = {
  getLoginActivity: () => api.get('/pro-trader/login-activity'),
  logoutOtherSessions: () => api.post('/pro-trader/logout-sessions'),
};

export default api;
