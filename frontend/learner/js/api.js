/**
 * api.js — Fetch wrapper, endpoint definitions, and error handling for Learner
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
    path.includes('/pro-traders') ||
    path.includes('/payments')
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
  storagePrefix: 'tw_learner_api',
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
      if (err.status === 402) {
        throw new APIError(err.data?.error || 'Payment required. Please subscribe.', 402, err.data);
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
  get:    (endpoint, opts)       => apiCall('GET',    endpoint, null, opts || {}),
  post:   (endpoint, data, opts) => apiCall('POST',   endpoint, data, opts || {}),
  put:    (endpoint, data, opts) => apiCall('PUT',    endpoint, data, opts || {}),
  patch:  (endpoint, data, opts) => apiCall('PATCH',  endpoint, data, opts || {}),
  delete: (endpoint, opts)       => apiCall('DELETE', endpoint, null, opts || {}),
  prefetch: (endpoint, opts = {}) => httpClient.prefetch(endpoint, {
    cachePolicy: resolveCachePolicy('GET', endpoint, opts),
  }),
  invalidate: (matcher) => httpClient.invalidate(matcher),
};

const LEARNER_MUTATION_INVALIDATION = ['/learner/', '/pro-traders/', '/payments/'];

// ===== ENDPOINTS =====

// Auth
export const authAPI = {
  register:       (data)  => api.post('/auth/register', data),
  login:          (data)  => api.post('/auth/login', data),
  logout:         ()      => api.post('/auth/logout'),
  refreshToken:   (token) => api.post('/auth/refresh-token', { refresh_token: token }),
  changePassword: (data)  => api.post('/auth/change-password', data),
  setup2FA:       (data)  => api.post('/auth/2fa/setup', data),
  verify2FA:      (data)  => api.post('/auth/2fa/verify', data),
  disable2FA:     (data)  => api.post('/auth/2fa/disable', data),
};

// Learner Profile & Dashboard
export const learnerProfileAPI = {
  getProfile:    ()        => api.get('/learner/profile'),
  updateProfile: (data)    => api.put('/learner/profile', data, { invalidateKeys: LEARNER_MUTATION_INVALIDATION }),
  uploadPicture: (formData)=> api.put('/learner/profile/picture', formData, { invalidateKeys: LEARNER_MUTATION_INVALIDATION }),
  getDashboard:  ()        => api.get('/learner/dashboard'),
};

// Feed & Trades
export const learnerFeedAPI = {
  getFeed:     (params = '') => api.get(`/learner/feed${params}`),
  getTrade:    (id)          => api.get(`/learner/trades/${id}`, { forceRefresh: true, cachePolicy: { ttlMs: 0, staleMs: 0 } }),
  prefetchTrade: (id)        => api.prefetch(`/learner/trades/${id}`, {
    cachePolicy: { ttlMs: 30000, staleMs: 60000, swr: true, persist: 'session' },
  }),
  unlockTrade: (id)          => api.post(`/learner/trades/${id}/unlock`, null, { invalidateKeys: LEARNER_MUTATION_INVALIDATION }),
};

// Credits
export const learnerCreditsAPI = {
  getCredits: () => api.get('/learner/credits'),
};

// History
export const learnerHistoryAPI = {
  getHistory: (params = '') => api.get(`/learner/history${params}`, { forceRefresh: true, cachePolicy: { ttlMs: 0, staleMs: 0 } }),
};

// Subscriptions
export const learnerSubscriptionsAPI = {
  getAll:          ()                  => api.get('/learner/subscriptions'),
  getStatus:       (proTraderId)       => api.get(`/learner/subscriptions/${proTraderId}`),
  subscribe:       (proTraderId, data) => api.post(`/learner/subscriptions/${proTraderId}/subscribe`, data, { invalidateKeys: LEARNER_MUTATION_INVALIDATION }),
};

// Payments (Cashfree)
export const paymentsAPI = {
  createOrder:   (data)    => api.post('/payments/create-order', data),
  verifyPayment: (orderId) => api.get(`/payments/verify/${orderId}`),
  getHistory:    ()        => api.get('/payments/history'),
};

// Comments
export const learnerCommentsAPI = {
  getComments:   (tradeId)                    => api.get(`/learner/trades/${tradeId}/comments`),
  addComment:    (tradeId, data)              => api.post(`/learner/trades/${tradeId}/comments`, data, { invalidateKeys: ['/learner/trades/', '/learner/comments'] }),
  updateComment: (tradeId, commentId, data)  => api.put(`/learner/trades/${tradeId}/comments/${commentId}`, data, { invalidateKeys: ['/learner/trades/', '/learner/comments'] }),
  deleteComment: (tradeId, commentId)        => api.delete(`/learner/trades/${tradeId}/comments/${commentId}`, { invalidateKeys: ['/learner/trades/', '/learner/comments'] }),
};

// Flags
export const learnerFlagsAPI = {
  flagTrade: (tradeId, data) => api.post(`/learner/trades/${tradeId}/flag`, data, { invalidateKeys: ['/learner/trades/', '/learner/flags'] }),
  getMyFlags: ()             => api.get('/learner/flags'),
};

// Ratings
export const learnerRatingsAPI = {
  rateTrade:    (tradeId, data) => api.post(`/learner/trades/${tradeId}/rate`, data, { invalidateKeys: ['/learner/trades/', '/learner/ratings'] }),
  updateRating: (tradeId, data) => api.put(`/learner/trades/${tradeId}/rate`, data, { invalidateKeys: ['/learner/trades/', '/learner/ratings'] }),
};

// Notifications
export const learnerNotificationsAPI = {
  getAll:            (params = '') => api.get(`/learner/notifications${params}`),
  markRead:          (id)          => api.put(`/learner/notifications/${id}/read`, null, { invalidateKeys: ['/learner/notifications'] }),
  delete:            (id)          => api.delete(`/learner/notifications/${id}`, { invalidateKeys: ['/learner/notifications'] }),
  clearAll:          ()            => api.post('/learner/notifications/clear-all', null, { invalidateKeys: ['/learner/notifications'] }),
  markAllRead:       ()            => api.post('/learner/notifications/mark-all-read', null, { invalidateKeys: ['/learner/notifications'] }),
  getPreferences:    ()            => api.get('/learner/notification-preferences'),
  updatePreferences: (data)        => api.put('/learner/notification-preferences', data, { invalidateKeys: ['/learner/notification-preferences'] }),
};

// Pro Traders (public endpoints)
export const proTradersAPI = {
  getAll:     (params = '') => api.get(`/pro-traders${params}`),
  getProfile: (id)          => api.get(`/pro-traders/${id}/profile`),
  getTrades:  (id)          => api.get(`/pro-traders/${id}/trades`),
};

const LEARNER_PAGE_PREFETCH = {
  'dashboard.html': ['/learner/dashboard', '/learner/credits'],
  'feed.html': ['/learner/feed?page=1&per_page=20', '/learner/credits'],
  'my-history.html': ['/learner/history?page=1&per_page=20'],
  'my-subscriptions.html': ['/learner/subscriptions', '/pro-traders?page=1&per_page=20'],
  'notifications.html': ['/learner/notifications?page=1&per_page=20'],
  'profile-settings.html': ['/learner/profile'],
  'notification-preferences.html': ['/learner/notification-preferences'],
  'account-settings.html': ['/auth/login-activity'],
};

let prefetchBound = false;
const prefetchedTargets = new Set();

export function setupLearnerNavigationPrefetch() {
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
    const endpoints = LEARNER_PAGE_PREFETCH[pageName];
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
  setupLearnerNavigationPrefetch();
}

export default api;
