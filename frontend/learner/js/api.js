/**
 * api.js — Fetch wrapper, endpoint definitions, and error handling for Learner
 */

import Storage from './storage.js';

// ===== CONFIG =====
const BASE_URL = window.TW_API_BASE_URL || 'http://localhost:5000/api';

// ===== API ERROR CLASS =====
export class APIError extends Error {
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

// ===== CORE FETCH WRAPPER =====
async function apiCall(method, endpoint, data = null, opts = {}) {
  const token = Storage.getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...opts.headers,
  };

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

    // 401: try refresh then retry once
    if (response.status === 401 && !opts._retried) {
      const refreshed = await tryRefreshToken();
      if (refreshed) {
        return apiCall(method, endpoint, data, { ...opts, _retried: true });
      } else {
        Storage.clearAll();
        window.location.href = '/learner/pages/auth.html';
        return;
      }
    }

    // 402: Payment Required — caller handles this
    if (response.status === 402) {
      let json = {};
      try { json = await response.json(); } catch { /* empty */ }
      throw new APIError(json.error || 'Payment required. Please subscribe.', 402, json);
    }

    // 403: Forbidden
    if (response.status === 403) {
      showToast('Access denied. You do not have permission.', 'error');
      throw new APIError('Access denied', 403);
    }

    // 409: Conflict
    if (response.status === 409) {
      let json = {};
      try { json = await response.json(); } catch { /* empty */ }
      throw new APIError(json.error || 'Conflict: already exists.', 409, json);
    }

    // 422: Validation error
    if (response.status === 422) {
      let json = {};
      try { json = await response.json(); } catch { /* empty */ }
      throw new APIError(json.error || 'Validation error.', 422, json);
    }

    // 500+: Server error
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
};

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
  updateProfile: (data)    => api.put('/learner/profile', data),
  uploadPicture: (formData)=> api.put('/learner/profile/picture', formData),
  getDashboard:  ()        => api.get('/learner/dashboard'),
};

// Feed & Trades
export const learnerFeedAPI = {
  getFeed:     (params = '') => api.get(`/learner/feed${params}`),
  getTrade:    (id)          => api.get(`/learner/trades/${id}`),
  unlockTrade: (id)          => api.post(`/learner/trades/${id}/unlock`),
};

// Credits
export const learnerCreditsAPI = {
  getCredits: () => api.get('/learner/credits'),
};

// History
export const learnerHistoryAPI = {
  getHistory: (params = '') => api.get(`/learner/history${params}`),
};

// Subscriptions
export const learnerSubscriptionsAPI = {
  getAll:          ()                  => api.get('/learner/subscriptions'),
  getStatus:       (proTraderId)       => api.get(`/learner/subscriptions/${proTraderId}`),
  subscribe:       (proTraderId, data) => api.post(`/learner/subscriptions/${proTraderId}/subscribe`, data),
  unsubscribe:     (subscriptionId)    => api.delete(`/learner/subscriptions/${subscriptionId}`),
  toggleAutoRenew: (subscriptionId, data) => api.put(`/learner/subscriptions/${subscriptionId}/auto-renew`, data),
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
  addComment:    (tradeId, data)              => api.post(`/learner/trades/${tradeId}/comments`, data),
  updateComment: (tradeId, commentId, data)  => api.put(`/learner/trades/${tradeId}/comments/${commentId}`, data),
  deleteComment: (tradeId, commentId)        => api.delete(`/learner/trades/${tradeId}/comments/${commentId}`),
};

// Flags
export const learnerFlagsAPI = {
  flagTrade: (tradeId, data) => api.post(`/learner/trades/${tradeId}/flag`, data),
  getMyFlags: ()             => api.get('/learner/flags'),
};

// Ratings
export const learnerRatingsAPI = {
  rateTrade:    (tradeId, data) => api.post(`/learner/trades/${tradeId}/rate`, data),
  updateRating: (tradeId, data) => api.put(`/learner/trades/${tradeId}/rate`, data),
};

// Notifications
export const learnerNotificationsAPI = {
  getAll:            (params = '') => api.get(`/learner/notifications${params}`),
  markRead:          (id)          => api.put(`/learner/notifications/${id}/read`),
  delete:            (id)          => api.delete(`/learner/notifications/${id}`),
  clearAll:          ()            => api.post('/learner/notifications/clear-all'),
  getPreferences:    ()            => api.get('/learner/notification-preferences'),
  updatePreferences: (data)        => api.put('/learner/notification-preferences', data),
};

// Pro Traders (public endpoints)
export const proTradersAPI = {
  getAll:     (params = '') => api.get(`/pro-traders${params}`),
  getProfile: (id)          => api.get(`/pro-traders/${id}/profile`),
  getTrades:  (id)          => api.get(`/pro-traders/${id}/trades`),
};

export default api;
