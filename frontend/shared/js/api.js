/**
 * api.js — Fetch wrapper, endpoint definitions, and error handling
 */

import Storage from './storage.js';
import { createHttpClient, HttpClientError } from './http-client.js?v=api-host-4';

// ===== CONFIG =====
// In a real environment, these would come from environment variables
const FALLBACK_LOCAL_API_BASE = 'http://localhost:5000/api';
const BASE_URL = (() => {
  const configured = window.TW_API_BASE_URL || localStorage.getItem('tw_api_base_url') || FALLBACK_LOCAL_API_BASE;
  return configured.replace(/\/$/, '').replace(/^https?:\/\/10\.25\.183\.119:5000\/api$/i, FALLBACK_LOCAL_API_BASE);
})();

// ===== API ERROR CLASS =====
export class APIError extends HttpClientError {
  constructor(message, status, data = null) {
    super(message);
    this.name = 'APIError';
    this.status = status;
    this.data = data;
  }
}

function resolveCachePolicy(method, endpoint, opts = {}) {
  if ((method || 'GET').toUpperCase() !== 'GET') return null;
  if (opts.noCache) return null;
  if (opts.cachePolicy) return opts.cachePolicy;

  const path = String(endpoint || '').toLowerCase();
  if (path.startsWith('/auth/')) return null;

  if (path.includes('/dashboard') || path.includes('/profile') || path.includes('/credits')) {
    return { ttlMs: 45000, staleMs: 90000, swr: true, persist: 'local' };
  }

  if (
    path.includes('/feed') ||
    path.includes('/history') ||
    path.includes('/subscriptions') ||
    path.includes('/trades') ||
    path.includes('/analytics') ||
    path.includes('/comments') ||
    path.includes('/notifications') ||
    path.includes('/pro-traders')
  ) {
    return { ttlMs: 15000, staleMs: 45000, swr: true, persist: 'session' };
  }

  return { ttlMs: 10000, staleMs: 20000, swr: false, persist: null };
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

const httpClient = createHttpClient({
  baseUrl: BASE_URL,
  storagePrefix: 'tw_shared_api',
  getToken: () => Storage.getToken(),
  refreshAuth: tryRefreshToken,
  onAuthFailure: () => {
    Storage.clearAll();
    window.location.href = '/learner/pages/auth.html';
  },
  defaultCachePolicy: { ttlMs: 10000, staleMs: 20000, swr: false, persist: null },
});

// ===== CORE FETCH WRAPPER =====
async function apiCall(method, endpoint, data = null, opts = {}) {
  const headers = { ...(opts.headers || {}) };
  let body;

  if (data !== null && data !== undefined) {
    if (data instanceof FormData) {
      body = data;
    } else {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(data);
    }
  }

  try {
    return await httpClient.request(endpoint, {
      method,
      headers,
      body,
      cachePolicy: resolveCachePolicy(method, endpoint, opts),
      forceRefresh: Boolean(opts.forceRefresh),
      dedupe: opts.dedupe !== false,
      invalidateKeys: opts.invalidateKeys,
    });
  } catch (err) {
    if (err instanceof HttpClientError) {
      if (err.status === 401) {
        return undefined;
      }
      if (err.status === 403) {
        showToast('Access denied. You do not have permission.', 'error');
      }
      if (err.status >= 500) {
        showToast('Server error. Please try again later.', 'error');
      }
      throw new APIError(err.message, err.status, err.data);
    }
    if (err && err.name === 'TypeError') {
      throw new APIError('Network error. Check your connection and try again.', 0);
    }
    throw err;
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
  prefetch: (endpoint, opts = {}) => httpClient.prefetch(endpoint, {
    cachePolicy: resolveCachePolicy('GET', endpoint, opts),
    forceRefresh: false,
    dedupe: true,
  }),
  invalidate: (matcher) => httpClient.invalidate(matcher),
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
  uploadDocuments: (formData) => api.post('/pro-trader/kyc/documents/upload', formData),
  submitReview: () => api.post('/pro-trader/kyc/submit-review'),
  updateBankDetails: (data) => api.put('/pro-trader/bank-details', data),
};

// Notifications
export const notificationsAPI = {
  getAll: () => api.get('/pro-trader/notifications'),
  getUnreadCount: () => api.get('/pro-trader/notifications/unread-count'),
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
