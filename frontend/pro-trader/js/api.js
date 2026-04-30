/**
 * api.js — Fetch wrapper, endpoint definitions, and error handling for Pro-Trader
 */

import Storage from './storage.js';
import { createHttpClient, HttpClientError } from '../../shared/js/http-client.js?v=api-host-4';

// ===== CONFIG =====
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

// ===== TOAST HELPER =====
function showToast(message, type = 'info') {
  if (window.Toast) window.Toast.show(message, type);
}

function resolveCachePolicy(method, endpoint, opts = {}) {
  if ((method || 'GET').toUpperCase() !== 'GET') return null;
  if (opts.noCache) return null;
  if (opts.cachePolicy) return opts.cachePolicy;

  const path = String(endpoint || '').toLowerCase();
  if (path.startsWith('/auth/')) return null;

  if (path.includes('/notifications')) {
    return { ttlMs: 8000, staleMs: 10000, swr: true, persist: 'session' };
  }

  if (path.includes('/dashboard') || path.includes('/profile') || path.includes('/balance')) {
    return { ttlMs: 45000, staleMs: 90000, swr: true, persist: 'local' };
  }

  if (
    path.includes('/trades') ||
    path.includes('/analytics') ||
    path.includes('/earnings') ||
    path.includes('/subscribers') ||
    path.includes('/payouts') ||
    path.includes('/notifications') ||
    path.includes('/kyc') ||
    path.includes('/login-activity')
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
  storagePrefix: 'tw_pro_api',
  getToken: () => Storage.getToken(),
  refreshAuth: tryRefreshToken,
  onAuthFailure: () => {
    Storage.clearAll();
    window.location.href = '/pro-trader/pages/register.html';
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

// ===== HTTP SHORTCUTS =====
export const api = {
  get: (endpoint, opts) => apiCall('GET', endpoint, null, opts || {}),
  post: (endpoint, data, opts) => apiCall('POST', endpoint, data, opts || {}),
  put: (endpoint, data, opts) => apiCall('PUT', endpoint, data, opts || {}),
  patch: (endpoint, data, opts) => apiCall('PATCH', endpoint, data, opts || {}),
  delete: (endpoint, opts) => apiCall('DELETE', endpoint, null, opts || {}),
  prefetch: (endpoint, opts = {}) => httpClient.prefetch(endpoint, {
    cachePolicy: resolveCachePolicy('GET', endpoint, opts),
  }),
  invalidate: (matcher) => httpClient.invalidate(matcher),
};

const PRO_MUTATION_INVALIDATION = ['/pro-trader/', '/auth/'];

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
  updateProfile: (data) => api.put('/pro-trader/profile', data, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  uploadProfilePicture: (formData) => api.put('/pro-trader/profile/picture', formData, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  getDashboard: () => api.get('/pro-trader/dashboard', { forceRefresh: true, cachePolicy: { ttlMs: 0, staleMs: 0 } }),
};

// Trades
export const tradesAPI = {
  list: (params = '') => api.get(`/pro-trader/trades${params}`),
  create: (data) => api.post('/pro-trader/trades', data, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  uploadChart: (formData) => api.post('/pro-trader/uploads/chart', formData),
  updateChart: (id, formData) => api.put(`/pro-trader/trades/${id}/chart-image`, formData, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  get: (id) => api.get(`/pro-trader/trades/${id}`),
  close: (id, data) => api.put(`/pro-trader/trades/${id}/close`, data, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  getComments: (id) => api.get(`/pro-trader/trades/${id}/comments`),
  addComment: (id, data) => api.post(`/pro-trader/trades/${id}/comments`, data, { invalidateKeys: ['/pro-trader/trades/', '/pro-trader/comments'] }),
  updateComment: (tradeId, commentId, data) =>
    api.put(`/pro-trader/trades/${tradeId}/comments/${commentId}`, data, { invalidateKeys: ['/pro-trader/trades/', '/pro-trader/comments'] }),
  deleteComment: (tradeId, commentId) =>
    api.delete(`/pro-trader/trades/${tradeId}/comments/${commentId}`, { invalidateKeys: ['/pro-trader/trades/', '/pro-trader/comments'] }),
};

// Analytics
export const analyticsAPI = {
  getAccuracy: () => api.get('/pro-trader/analytics/accuracy', { forceRefresh: true, cachePolicy: { ttlMs: 0, staleMs: 0 } }),
  getPerformanceChart: () => api.get('/pro-trader/analytics/performance-chart', { forceRefresh: true, cachePolicy: { ttlMs: 0, staleMs: 0 } }),
  getWinLoss: () => api.get('/pro-trader/analytics/win-loss', { forceRefresh: true, cachePolicy: { ttlMs: 0, staleMs: 0 } }),
  getRRR: () => api.get('/pro-trader/analytics/rrr', { forceRefresh: true, cachePolicy: { ttlMs: 0, staleMs: 0 } }),
  getMonthlyStats: () => api.get('/pro-trader/analytics/monthly-stats', { forceRefresh: true, cachePolicy: { ttlMs: 0, staleMs: 0 } }),
};

// Earnings & Payouts
export const earningsAPI = {
  getEarnings: () => api.get('/pro-trader/earnings', { forceRefresh: true, cachePolicy: { ttlMs: 0, staleMs: 0 } }),
  getBalance: () => api.get('/pro-trader/balance', { forceRefresh: true, cachePolicy: { ttlMs: 0, staleMs: 0 } }),
  getPayouts: () => api.get('/pro-trader/payouts'),
  initiatePayout: (data) => api.post('/pro-trader/payouts/initiate', data, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  updateSubscriptionPrice: (data) => api.put('/pro-trader/subscription-price', data, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
};

// Subscribers
export const subscribersAPI = {
  getSubscribers: () => api.get('/pro-trader/subscribers'),
};

// KYC
export const kycAPI = {
  getStatus: () => api.get('/pro-trader/kyc/status'),
  uploadDocuments: (formData) => api.post('/pro-trader/kyc/documents/upload', formData, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  submitReview: () => api.post('/pro-trader/kyc/submit-review', null, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  updateBankDetails: (data) => api.put('/pro-trader/bank-details', data, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  getBankDetails: () => api.get('/pro-trader/bank-details'),
  savePricing: (data) => api.put('/pro-trader/onboarding/step3', data, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
};

// Onboarding
export const onboardingAPI = {
  getState: () => api.get('/pro-trader/onboarding-state'),
  step1: (data) => api.put('/pro-trader/onboarding/step1', data, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  step2: (data) => api.put('/pro-trader/onboarding/step2', data || {}, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  step3: (data) => api.put('/pro-trader/onboarding/step3', data, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
  skip: (data) => api.post('/pro-trader/onboarding/skip', data || {}, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
};

// Notifications
export const notificationsAPI = {
  getAll: () => api.get('/pro-trader/notifications'),
  getUnreadCount: () => api.get('/pro-trader/notifications/unread-count'),
  markRead: (id) => api.put(`/pro-trader/notifications/${id}/read`, null, { invalidateKeys: ['/pro-trader/notifications'] }),
  delete: (id) => api.delete(`/pro-trader/notifications/${id}`, { invalidateKeys: ['/pro-trader/notifications'] }),
  clearAll: () => api.post('/pro-trader/notifications/clear-all', null, { invalidateKeys: ['/pro-trader/notifications'] }),
  getPreferences: () => api.get('/pro-trader/notification-preferences'),
  updatePreferences: (data) => api.put('/pro-trader/notification-preferences', data, { invalidateKeys: ['/pro-trader/notification-preferences'] }),
};

// Account Settings
export const accountAPI = {
  getLoginActivity: () => api.get('/pro-trader/login-activity'),
  logoutOtherSessions: () => api.post('/pro-trader/logout-sessions', null, { invalidateKeys: PRO_MUTATION_INVALIDATION }),
};

const PRO_PAGE_PREFETCH = {
  'dashboard.html': ['/pro-trader/dashboard', '/pro-trader/trades?page=1&per_page=5', '/pro-trader/analytics/monthly-stats'],
  'analytics.html': ['/pro-trader/analytics/accuracy', '/pro-trader/analytics/performance-chart', '/pro-trader/analytics/monthly-stats'],
  'active-trades.html': ['/pro-trader/trades?page=1&per_page=20'],
  'earnings.html': ['/pro-trader/earnings', '/pro-trader/payouts', '/pro-trader/balance'],
  'subscribers.html': ['/pro-trader/subscribers'],
  'notifications.html': ['/pro-trader/notifications?page=1&per_page=20'],
  'profile-settings.html': ['/pro-trader/profile'],
  'account-settings.html': ['/pro-trader/login-activity'],
  'kyc-setup.html': ['/pro-trader/kyc/status'],
  'pro-onboarding.html': ['/pro-trader/onboarding-state'],
};

let prefetchBound = false;
const prefetchedTargets = new Set();

export function setupProNavigationPrefetch() {
  if (prefetchBound || typeof document === 'undefined') return;
  prefetchBound = true;

  const queuePrefetch = (anchorEl) => {
    if (!anchorEl || !anchorEl.href) return;
    let pageName = '';
    try {
      const url = new URL(anchorEl.href, window.location.origin);
      pageName = (url.pathname.split('/').pop() || '').toLowerCase();
    } catch {
      return;
    }
    if (!pageName || prefetchedTargets.has(pageName)) return;
    const endpoints = PRO_PAGE_PREFETCH[pageName];
    if (!Array.isArray(endpoints) || endpoints.length === 0) return;

    prefetchedTargets.add(pageName);
    endpoints.forEach((endpoint) => {
      api.prefetch(endpoint, { dedupe: true });
    });
  };

  const onHover = (event) => {
    const anchor = event.target && event.target.closest ? event.target.closest('a[href]') : null;
    if (anchor) queuePrefetch(anchor);
  };

  document.addEventListener('mouseover', onHover, { passive: true });
  document.addEventListener('focusin', onHover);
}

if (typeof window !== 'undefined') {
  setupProNavigationPrefetch();
}

export default api;
