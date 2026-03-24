/**
 * auth.js — JWT authentication, login/logout, token management for Learner
 */

import Storage from './storage.js';
import { authAPI } from './api.js';

const Auth = {
  // ===== AUTH STATUS =====
  isAuthenticated() {
    return !!Storage.getToken();
  },

  /**
   * Guard: redirect to login if not authenticated.
   * Call at the top of every protected page.
   */
  requireAuth() {
    if (!this.isAuthenticated()) {
      this.redirectToLogin();
      return false;
    }
    return true;
  },

  redirectToLogin() {
    window.location.href = '/frontend/learner/pages/login.html';
  },

  redirectToDashboard() {
    window.location.href = '/frontend/learner/pages/dashboard.html';
  },

  // ===== LOGIN =====
  // Backend response: { token, user: {id, email, role}, profile: {credits, interests, experience_level} }
  async login(email, password) {
    const data = await authAPI.login({ email, password });
    this._storeSession(data);
    return data;
  },

  _storeSession(data) {
    if (data.token)         Storage.setToken(data.token);
    if (data.access_token)  Storage.setToken(data.access_token);
    if (data.refresh_token) Storage.setRefreshToken(data.refresh_token);
    if (data.user)          Storage.setUser(data.user);
    if (data.profile)       Storage.setLearnerProfile(data.profile);
  },

  // ===== REGISTER =====
  // Backend response: { user_id, token, profile: {id, credits: 7, interests: []} }
  async register(email, password) {
    const data = await authAPI.register({ email, password, role: 'public_trader' });
    if (data.token) Storage.setToken(data.token);
    if (data.profile) Storage.setLearnerProfile(data.profile);
    return data;
  },

  // ===== LOGOUT =====
  async logout() {
    try {
      await authAPI.logout();
    } catch {
      // Ignore logout API errors
    } finally {
      Storage.clearAll();
      window.location.href = '/frontend/learner/pages/login.html';
    }
  },

  // ===== CURRENT USER =====
  getCurrentUser() {
    return Storage.getUser();
  },

  getLearnerProfile() {
    return Storage.getLearnerProfile();
  },

  getCredits() {
    const profile = Storage.getLearnerProfile();
    return profile?.credits ?? 0;
  },
};

export default Auth;
