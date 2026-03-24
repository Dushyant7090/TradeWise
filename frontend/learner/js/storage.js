/**
 * storage.js — localStorage management for TradeWise Learner
 */

const STORAGE_KEYS = {
  JWT_TOKEN: 'tw_jwt_token',
  REFRESH_TOKEN: 'tw_refresh_token',
  USER_DATA: 'tw_user_data',
  LEARNER_PROFILE: 'tw_learner_profile',
  LEARNER_DASHBOARD: 'tw_learner_dashboard',
  LEARNER_FEED: 'tw_learner_feed',
  NOTIF_PREFS: 'tw_notif_prefs',
  CACHE_TTL: 'tw_cache_ttl_',
};

const CACHE_DURATION_MS = 5 * 60 * 1000; // 5 minutes

const Storage = {
  // ===== JWT TOKEN =====
  setToken(token) {
    localStorage.setItem(STORAGE_KEYS.JWT_TOKEN, token);
  },

  getToken() {
    return localStorage.getItem(STORAGE_KEYS.JWT_TOKEN);
  },

  setRefreshToken(token) {
    localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, token);
  },

  getRefreshToken() {
    return localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);
  },

  removeTokens() {
    localStorage.removeItem(STORAGE_KEYS.JWT_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
  },

  // ===== USER DATA =====
  setUser(userData) {
    localStorage.setItem(STORAGE_KEYS.USER_DATA, JSON.stringify(userData));
  },

  getUser() {
    try {
      const data = localStorage.getItem(STORAGE_KEYS.USER_DATA);
      return data ? JSON.parse(data) : null;
    } catch {
      return null;
    }
  },

  // ===== LEARNER PROFILE =====
  setLearnerProfile(profile) {
    this._setCached(STORAGE_KEYS.LEARNER_PROFILE, profile);
  },

  getLearnerProfile() {
    return this._getCached(STORAGE_KEYS.LEARNER_PROFILE);
  },

  // ===== LEARNER DASHBOARD =====
  setDashboard(data) {
    this._setCached(STORAGE_KEYS.LEARNER_DASHBOARD, data);
  },

  getDashboard() {
    return this._getCached(STORAGE_KEYS.LEARNER_DASHBOARD);
  },

  // ===== NOTIFICATION PREFERENCES =====
  setNotifPrefs(prefs) {
    localStorage.setItem(STORAGE_KEYS.NOTIF_PREFS, JSON.stringify(prefs));
  },

  getNotifPrefs() {
    try {
      const data = localStorage.getItem(STORAGE_KEYS.NOTIF_PREFS);
      return data ? JSON.parse(data) : null;
    } catch {
      return null;
    }
  },

  // ===== CACHE HELPERS =====
  _setCached(key, data) {
    const entry = { data, timestamp: Date.now() };
    localStorage.setItem(key, JSON.stringify(entry));
  },

  _getCached(key) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return null;
      const entry = JSON.parse(raw);
      if (Date.now() - entry.timestamp > CACHE_DURATION_MS) {
        localStorage.removeItem(key);
        return null;
      }
      return entry.data;
    } catch {
      return null;
    }
  },

  // ===== CLEAR ALL =====
  clearAll() {
    Object.values(STORAGE_KEYS).forEach(key => {
      if (!key.endsWith('_')) localStorage.removeItem(key);
    });
  },
};

export default Storage;
